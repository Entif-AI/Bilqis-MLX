import csv
from collections import Counter
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.composition import (
    DERIVATION_BASE, TYPE_BASE, composition_iri, load_composition_profile, project_compositions,
)
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.notation import NEW_ITHKUIL_DATATYPE_IRI
from lib.ithkuil.src.skos.preflight import preflight


ITHKUIL = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ.get("BILQIS_COMPOSITION_SOURCE_ROOT", ITHKUIL / "_data" / "csv"))
PROFILE = ITHKUIL / "src" / "skos" / "composition_profile.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class ClosureView:
    def __init__(self, base, replacements):
        self.base = base
        self.replacements = replacements

    def table(self, name):
        if name in self.replacements:
            return SimpleNamespace(rows=tuple(self.replacements[name]))
        return self.base.table(name)


class CompositionProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(SOURCE_ROOT).require_valid()
        cls.profile = load_composition_profile(
            PROFILE, cls.closure, FIXTURES / "skos_composition_negative.ttl"
        )
        cls.result = project_compositions(cls.closure, cls.profile)

    def test_current_corpus_is_fully_accounted_without_component_order_emission(self):
        self.assertEqual(len(self.closure.table("morpheme_compositions").rows), 1917)
        self.assertEqual(len(self.result.emitted_ids), 1917)
        self.assertEqual(self.result.held_ids, ())
        self.assertEqual(self.result.issues, ())
        self.assertFalse(any(predicate in {SKOS.broader, SKOS.narrower, SKOS.related, SKOS.notation}
                             for _, predicate, _ in self.result.graph))
        self.assertFalse(any(obj == SKOS.Concept for _, _, obj in self.result.graph))

        with (SOURCE_ROOT / "composition_components.csv").open(newline="", encoding="utf-8") as handle:
            components = list(csv.DictReader(handle))
        counts = Counter(row["composition_id"] for row in components)
        self.assertEqual(len(components), 3855)
        for row in self.closure.table("morpheme_compositions").rows:
            self.assertEqual(counts[row["composition_id"]], int(row["component_count"]))

    def test_profile_admits_only_source_codes_and_three_proven_metadata_terms(self):
        self.assertEqual(len(self.profile.admitted_types), 9)
        self.assertEqual(self.profile.admitted_derivations, frozenset({"source_join", "source_template"}))
        self.assertEqual({item.key for item in self.profile.properties},
                         {"surfacePattern", "condition", "componentCount"})
        vocab_predicates = {predicate for _, predicate, _ in self.result.graph
                            if str(predicate).startswith("https://github.com/Entif-AI/Bilqis-MLX/vocab/")}
        self.assertEqual(vocab_predicates, {self.profile.property(key) for key in
                                            ("surfacePattern", "condition", "componentCount")})

    def test_real_varied_rows_match_literal_golden_resource_graph(self):
        ids = ("COMP-0060583f4d9807", "COMP-037dfa8bbd64d2", "COMP-044604fe8e62d7")
        actual = Graph()
        for cid in ids:
            subject = URIRef(composition_iri(cid))
            for triple in self.result.graph.triples((subject, None, None)):
                actual.add(triple)
        expected = Graph().parse(FIXTURES / "skos_composition_expected.nt", format="nt")
        self.assertTrue(isomorphic(actual, expected))

        raw = URIRef(composition_iri("COMP-037dfa8bbd64d2"))
        exact = Literal("hmo’e", datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI), normalize=False)
        normalized = Literal("hmo'e", datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI), normalize=False)
        self.assertIn((raw, RDF.value, exact), actual)
        self.assertNotIn((raw, RDF.value, normalized), actual)

        template = URIRef(composition_iri("COMP-044604fe8e62d7"))
        self.assertIn((template, RDF.type, URIRef(DERIVATION_BASE + "source_template")), actual)
        self.assertEqual(list(actual.objects(template, RDF.value)), [])

    def test_source_join_and_template_loci_are_public_and_complete(self):
        expected = {
            "COMP-0060583f4d9807": {
                "https://www.ithkuil.net/newithkuil_04_case.htm",
                "https://www.ithkuil.net/newithkuil_07_affixes.htm",
            },
            "COMP-037dfa8bbd64d2": {
                "https://www.ithkuil.net/newithkuil_04_case.htm",
                "https://www.ithkuil.net/newithkuil_08_adjuncts.htm",
            },
            "COMP-044604fe8e62d7": {"https://www.ithkuil.net/newithkuil_08_adjuncts.htm"},
        }
        for cid, urls in expected.items():
            subject = URIRef(composition_iri(cid))
            loci = set(self.result.graph.objects(subject, DCTERMS.source))
            found = {str(url) for locus in loci for url in self.result.graph.objects(locus, DCTERMS.source)}
            self.assertEqual(found, urls)
            for locus in loci:
                self.assertTrue(list(self.result.graph.objects(locus, DCTERMS.identifier)))
                self.assertTrue(list(self.result.graph.objects(locus, DCTERMS.bibliographicCitation)))

    def test_reordering_source_rows_does_not_change_canonical_graph(self):
        shuffled = ClosureView(self.closure, {
            "morpheme_compositions": reversed(self.closure.table("morpheme_compositions").rows),
            "source_assertions": reversed(self.closure.table("source_assertions").rows),
        })
        other = project_compositions(shuffled, self.profile)
        self.assertEqual(canonicalize(other.graph), canonicalize(self.result.graph))
        self.assertEqual(other.emitted_ids, self.result.emitted_ids)

    def test_same_surface_on_two_ids_does_not_merge_identity(self):
        rows = [dict(row.values) for row in self.closure.table("morpheme_compositions").rows]
        first = next(row for row in rows if row["composition_id"] == "COMP-0060583f4d9807")
        second = next(row for row in rows if row["composition_id"] == "COMP-00a333ae83ae02")
        second["surface_form_raw"] = first["surface_form_raw"]
        synthetic = project_compositions(ClosureView(self.closure, {"morpheme_compositions": rows}), self.profile)
        left, right = URIRef(composition_iri(first["composition_id"])), URIRef(composition_iri(second["composition_id"]))
        lexical = Literal(first["surface_form_raw"], datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI), normalize=False)
        self.assertNotEqual(left, right)
        self.assertIn((left, RDF.value, lexical), synthetic.graph)
        self.assertIn((right, RDF.value, lexical), synthetic.graph)

    def test_unknown_type_holds_whole_resource_without_guessing_from_shape(self):
        rows = [dict(row.values) for row in self.closure.table("morpheme_compositions").rows]
        target = next(row for row in rows if row["composition_id"] == "COMP-0060583f4d9807")
        target["composition_type"] = "future_unreviewed_kind"
        projected = project_compositions(ClosureView(self.closure, {"morpheme_compositions": rows}), self.profile)
        self.assertEqual(len(projected.emitted_ids), 1916)
        self.assertEqual(projected.held_ids, (target["composition_id"],))
        self.assertTrue(any(issue.code == "UNKNOWN_COMPOSITION_TYPE" for issue in projected.issues))
        resource = URIRef(composition_iri(target["composition_id"]))
        self.assertFalse(any(True for _ in projected.graph.triples((resource, None, None))))
        self.assertFalse(any(True for _ in projected.graph.triples((None, None, resource))))

    def test_bad_source_or_component_count_holds_instead_of_partial_emission(self):
        for field, value, code in (
            ("primary_source_url", "https://www.ithkuil.net/not-the-registry-url", "SOURCE_URL_REGISTRY_MISMATCH"),
            ("component_count", "not-an-integer", "INVALID_COMPONENT_COUNT"),
            ("surface_form_raw", " bad ", "NOTATION_SURROUNDING_WHITESPACE"),
        ):
            with self.subTest(field=field):
                rows = [dict(row.values) for row in self.closure.table("morpheme_compositions").rows]
                target = next(row for row in rows if row["composition_id"] == "COMP-0060583f4d9807")
                target[field] = value
                projected = project_compositions(ClosureView(self.closure, {"morpheme_compositions": rows}), self.profile)
                self.assertIn(target["composition_id"], projected.held_ids)
                self.assertTrue(any(issue.code == code for issue in projected.issues))
                resource = URIRef(composition_iri(target["composition_id"]))
                self.assertFalse(any(True for _ in projected.graph.triples((resource, None, None))))

    def test_source_kind_classes_are_explicit_codes_not_text_guesses(self):
        join = URIRef(composition_iri("COMP-0060583f4d9807"))
        template = URIRef(composition_iri("COMP-044604fe8e62d7"))
        self.assertIn((join, RDF.type, URIRef(TYPE_BASE + "VXCS_affix")), self.result.graph)
        self.assertIn((join, RDF.type, URIRef(DERIVATION_BASE + "source_join")), self.result.graph)
        self.assertIn((template, RDF.type, URIRef(TYPE_BASE + "construction_template")), self.result.graph)
        self.assertIn((template, RDF.type, URIRef(DERIVATION_BASE + "source_template")), self.result.graph)
        for class_iri in (URIRef(TYPE_BASE + "VXCS_affix"), URIRef(DERIVATION_BASE + "source_template")):
            self.assertIn((class_iri, RDF.type, RDFS.Class), self.result.graph)

    def test_explicit_source_type_not_surface_shape_controls_template_class(self):
        rows = [dict(row.values) for row in self.closure.table("morpheme_compositions").rows]
        target = next(row for row in rows if row["composition_id"] == "COMP-044604fe8e62d7")
        target["surface_form_raw"] = "iařš"
        projected = project_compositions(ClosureView(self.closure, {"morpheme_compositions": rows}), self.profile)
        resource = URIRef(composition_iri(target["composition_id"]))
        self.assertIn((resource, RDF.type, URIRef(TYPE_BASE + "construction_template")), projected.graph)
        self.assertIn((resource, RDF.type, URIRef(DERIVATION_BASE + "source_template")), projected.graph)
        self.assertIn((resource, RDF.value,
                       Literal("iařš", datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI), normalize=False)),
                      projected.graph)

    def test_private_metadata_cannot_enter_the_public_composition_graph(self):
        for field in ("construction_name", "semantic_summary", "surface_pattern",
                      "condition", "surface_form_raw"):
            with self.subTest(field=field):
                rows = [dict(row.values) for row in self.closure.table("morpheme_compositions").rows]
                target = next(row for row in rows if row["composition_id"] == "COMP-0060583f4d9807")
                target[field] = "file:///home/example/private-source"
                projected = project_compositions(ClosureView(self.closure, {"morpheme_compositions": rows}), self.profile)
                self.assertIn(target["composition_id"], projected.held_ids)
                self.assertTrue(any(issue.code == "SOURCE_PUBLIC_LITERAL_REJECTED" for issue in projected.issues))
                resource = URIRef(composition_iri(target["composition_id"]))
                self.assertEqual(list(projected.graph.triples((resource, None, None))), [])
                self.assertFalse(any("private-source" in str(value) for triple in projected.graph for value in triple))

    def test_machine_profile_rejects_unproven_term_iri(self):
        data = json.loads(PROFILE.read_text(encoding="utf-8"))
        data["extension_terms"][0]["iri"] = "https://example.invalid/not-the-canonical-term"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ProfileError) as caught:
                load_composition_profile(path, self.closure, FIXTURES / "skos_composition_negative.ttl")
        self.assertEqual(caught.exception.code, "COMPOSITION_EXTENSION_IRI_INVALID")


if __name__ == "__main__":
    unittest.main()
