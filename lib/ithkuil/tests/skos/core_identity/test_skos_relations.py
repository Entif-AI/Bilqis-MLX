from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import csv
from dataclasses import replace
import inspect
import json
from pathlib import Path
import tempfile
import unittest

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDFS, SKOS

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos import relations as relation_module
from lib.ithkuil.src.skos.relations import (
    ExtensionTerm, RelationDisposition, admit_extension, decide_relation, qualify_extension,
    validate_predicate,
)


ROOT = ITHKUIL_ROOT
FIXTURES = ROOT / "tests/fixtures"


class RelationAdmissionTests(unittest.TestCase):
    def code(self, expected, function, *args, **kwargs):
        with self.assertRaises(ProfileError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, expected)

    def fixture_term(self):
        data = json.loads((FIXTURES / "skos_extension_example.json").read_text())
        self.assertEqual(data["scope"], "admission-fixture-only")
        return ExtensionTerm(**data["terms"][0])

    def evidence(self, *, negative_fixture=None, specialization_fixture=None):
        with (ROOT / "_data/csv/allomorph_rules.csv").open(newline="", encoding="utf-8") as handle:
            row = next(row for row in csv.DictReader(handle) if row["allomorph_rule_id"] == "ALLO-08d9bb00e7a0dd")
        self.assertEqual((row["input_pattern"], row["intermediate_pattern"], row["output_pattern"]), ("fbm", "fv", "vw"))
        evidence = {
            "source_csv_root": ROOT / "_data/csv",
            "negative_fixture_path": negative_fixture or FIXTURES / "skos_relations_negative.ttl",
        }
        if specialization_fixture is not None:
            evidence["specialization_fixture_path"] = specialization_fixture
        return evidence

    def test_decision_matrix_has_literal_expected_dispositions(self):
        expected = {
            "subsumption": ("SKOS_SEMANTIC_RELATION", str(SKOS.broader)),
            "inverse_subsumption": ("SKOS_SEMANTIC_RELATION", str(SKOS.narrower)),
            "association": ("SKOS_SEMANTIC_RELATION", str(SKOS.related)),
            "family_membership": ("SKOS_MEMBERSHIP", str(SKOS.member)),
            "root_sense": ("RELATIONAL_IR_ONLY", None),
            "composition_membership": ("RELATIONAL_IR_ONLY", None),
            "ordered_component": ("RELATIONAL_IR_ONLY", None),
            "allomorph": ("RELATIONAL_IR_ONLY", None),
            "contrast": ("SKOS_SEMANTIC_RELATION", str(SKOS.related)),
            "unknown": ("HELD", None),
        }
        for kind, pair in expected.items():
            with self.subTest(kind=kind):
                decision = decide_relation(kind, source_attested=True, semantic_proof=True)
                self.assertEqual((decision.disposition.value, decision.predicate), pair)
                self.assertNotEqual(decision.disposition, RelationDisposition.BILQIS_EXTENSION)
        self.assertNotIn("extension", inspect.signature(decide_relation).parameters)

    def test_missing_evidence_never_falls_back_to_related(self):
        for kind in ("association", "subsumption", "contrast"):
            self.assertEqual(decide_relation(kind, source_attested=True).disposition, RelationDisposition.HELD)
        self.assertEqual(decide_relation("family_membership", source_attested=False).predicate, None)
        self.assertEqual(decide_relation("unknown", source_attested=True).reason, "UNKNOWN_RELATION_KIND")

    def test_positive_rdf_fixture_obeys_admission(self):
        graph = Graph().parse(FIXTURES / "skos_relations_positive.ttl")
        kinds = {"specific": "subsumption", "general": "inverse_subsumption",
                 "associated": "association", "family": "family_membership"}
        for subject, kind in kinds.items():
            decision = decide_relation(kind, source_attested=True, semantic_proof=True)
            triples = list(graph.triples((URIRef("urn:fixture:" + subject), URIRef(decision.predicate), None)))
            self.assertEqual(len(triples), 1)
            validate_predicate(kind, str(triples[0][1]), source_attested=True, semantic_proof=True)

    def test_negative_rdf_fixture_rejects_false_taxonomy_and_graph_glue(self):
        graph = Graph().parse(FIXTURES / "skos_relations_negative.ttl")
        cases = {
            "family": ("family_membership", SKOS.broader),
            "allomorph": ("allomorph", SKOS.related),
            "composition": ("composition_membership", SKOS.narrower),
            "root": ("root_sense", SKOS.broader),
        }
        for subject, (kind, predicate) in cases.items():
            self.assertTrue(list(graph.triples((URIRef("urn:fixture:" + subject), predicate, None))))
            self.code("RELATION_PREDICATE_NOT_ADMITTED", validate_predicate,
                      kind, str(predicate), source_attested=True, semantic_proof=True)

    def test_real_source_residue_can_pass_fixture_admission_without_skos_subproperty(self):
        term = self.fixture_term()
        self.assertEqual(admit_extension(term, **self.evidence()), term)
        self.assertIsNone(term.subproperty_of)
        decision = qualify_extension("allomorph", term, **self.evidence())
        self.assertEqual(decision.disposition, RelationDisposition.BILQIS_EXTENSION)
        self.assertEqual(decision.predicate, "https://github.com/Entif-AI/Bilqis-MLX/vocab/surfaceReplacement")
        self.assertIn(
            (URIRef("urn:source:ALLO-08d9bb00e7a0dd"), SKOS.related,
             URIRef("urn:negative:allomorph-is-not-related")),
            Graph().parse(FIXTURES / "skos_relations_negative.ttl"),
        )

    def test_forged_admitted_wrapper_cannot_bypass_raw_term_gate(self):
        self.assertFalse(hasattr(relation_module, "AdmittedExtension"))
        parameters = inspect.signature(admit_extension).parameters
        self.assertNotIn("source_fixtures", parameters)
        self.assertNotIn("negative_fixtures", parameters)
        self.assertNotIn("specialization_proofs", parameters)

        class ForgedWrapper:
            def __init__(self, term):
                self.term = term

        self.code("EXTENSION_TERM_REQUIRED", qualify_extension, "allomorph",
                  ForgedWrapper(self.fixture_term()), **self.evidence())

    def test_fake_source_identifier_cannot_self_attest(self):
        term = replace(self.fixture_term(), source_fixture="ALLO-NOT-A-REAL-RULE")
        self.code("EXTENSION_SOURCE_PROOF_MISSING", admit_extension, term, **self.evidence())

    def test_fake_negative_fixture_cannot_self_attest(self):
        term = self.fixture_term()
        with tempfile.TemporaryDirectory() as tempdir:
            fake = Path(tempdir) / "negative.ttl"
            fake.write_text(
                "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
                "<urn:source:ALLO-08d9bb00e7a0dd> skos:related <urn:negative:not-the-registry-key> .\n",
                encoding="utf-8",
            )
            self.code("EXTENSION_NEGATIVE_PROOF_MISSING", admit_extension, term,
                      **self.evidence(negative_fixture=fake))

    def test_malformed_negative_rdf_has_stable_failure(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "negative.ttl"
            path.write_text("not { valid turtle", encoding="utf-8")
            self.code("EXTENSION_NEGATIVE_PROOF_MISSING", admit_extension, self.fixture_term(),
                      **self.evidence(negative_fixture=path))

    def test_duplicate_source_identifier_cannot_select_first_row(self):
        with (ROOT / "_data/csv/allomorph_rules.csv").open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields, rows = reader.fieldnames, list(reader)
        chosen = next(row for row in rows if row["allomorph_rule_id"] == self.fixture_term().source_fixture)
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "allomorph_rules.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows([*rows, {**chosen, "output_pattern": "wrong"}])
            evidence = {**self.evidence(), "source_csv_root": tempdir}
            self.code("EXTENSION_SOURCE_PROOF_AMBIGUOUS", admit_extension, self.fixture_term(), **evidence)

    def test_string_flags_cannot_assert_reviewed_semantics(self):
        self.code("INVALID_RELATION_REVIEW_PREMISE", decide_relation, "subsumption",
                  source_attested="false", semantic_proof=True)

    def test_custom_term_requires_all_necessity_and_proof_fields(self):
        term = self.fixture_term()
        self.code("EXTENSION_NOT_NECESSARY", admit_extension, replace(term, recurring=False), **self.evidence())
        self.code("EXTENSION_NOT_NECESSARY", admit_extension, replace(term, machine_required=False), **self.evidence())
        self.code("EXTENSION_CONTRACT_INCOMPLETE", admit_extension, replace(term, rdf_gap=""), **self.evidence())
        self.code("EXISTING_SKOS_PRIMITIVE_SUFFICES", admit_extension,
                  replace(term, relation_kind="family_membership"), **self.evidence())

    def test_structural_relation_cannot_become_skos_subproperty(self):
        term = replace(self.fixture_term(), subproperty_of=str(SKOS.related), specialization_proof="invented")
        self.code("UNPROVEN_SKOS_SPECIALIZATION", admit_extension, term, **self.evidence(),
                  specialization_fixture_path=FIXTURES / "skos_relations_positive.ttl")

    def test_fabricated_semantic_specialization_requires_bound_graph_and_source_evidence(self):
        term = replace(self.fixture_term(), key="sourceContrast", relation_kind="contrast",
                       domain=str(SKOS.Concept), range=str(SKOS.Concept),
                       subproperty_of=str(SKOS.related), specialization_proof="contrast-specializes-association")
        with tempfile.TemporaryDirectory() as tempdir:
            fake = Path(tempdir) / "specialization.ttl"
            fake.write_text(
                "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
                "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
                f"<{term.iri}> rdfs:subPropertyOf skos:related .\n",
                encoding="utf-8",
            )
            graph = Graph().parse(fake)
            self.assertIn((URIRef(term.iri), RDFS.subPropertyOf, SKOS.related), graph)
            self.assertNotIn((URIRef(term.iri), DCTERMS.source,
                              URIRef(f"urn:source:{term.source_fixture}")), graph)
            self.code("UNPROVEN_SKOS_SPECIALIZATION", admit_extension, term,
                      **self.evidence(specialization_fixture=fake))
            held = qualify_extension("contrast", term, **self.evidence(specialization_fixture=fake))
            self.assertEqual((held.disposition, held.predicate, held.reason),
                             (RelationDisposition.HELD, None, "UNPROVEN_SKOS_SPECIALIZATION"))


if __name__ == "__main__":
    unittest.main()
