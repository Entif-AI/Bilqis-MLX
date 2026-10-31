from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

from lib.ithkuil.tests.source_expectations import CORE
from pathlib import Path
import unittest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.resolver import RecordRef, resolve_identities
from lib.ithkuil.src.skos.source import SourceProjector


ROOT = ITHKUIL_ROOT
SOURCE_ROOT = ROOT / "_data/csv"
FIXTURE_ROOT = FIXTURES


class SourceProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(SOURCE_ROOT).require_valid()
        cls.resolution = resolve_identities(cls.closure)
        cls.projector = SourceProjector(cls.closure)

    def mutate_row(self, row, **changes):
        values = dict(row.values)
        values.update(changes)
        return FrozenRow(tuple((key, values[key]) for key, _ in row.values))

    def replace_table(self, closure, table_name, transform):
        tables = []
        for table in closure.tables:
            if table.name == table_name:
                rows = tuple(transform(row) for row in table.rows)
                tables.append(LoadedTable(table.name, table.columns, rows))
            else:
                tables.append(table)
        return CompilerClosure(closure.manifest_version, tuple(tables))

    def resource(self, iri):
        return next(
            resource
            for resource in self.resolution.resources
            if resource.identity.iri == iri
        )

    def test_one_locus_matches_exact_rdf_fixture_and_standard_predicates_only(self):
        resource = self.resource(
            "https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CONFIGURATION/MFF"
        )
        projection = self.projector.project_resource(
            resource.identity, resource.source_records
        )
        self.assertEqual(projection.issues, ())
        self.assertEqual(projection.held, ())
        expected = Graph().parse(FIXTURE_ROOT / "skos_source_mff.ttl", format="turtle")
        self.assertEqual(set(projection.source_graph), set(expected))
        reparsed = Graph().parse(
            data=projection.source_graph.serialize(format="nt"), format="nt"
        )
        self.assertEqual(set(reparsed), set(expected))
        self.assertEqual(len(projection.source_graph), 6)
        self.assertEqual(
            {predicate for _, predicate, _ in projection.source_graph},
            {DCTERMS.source, DCTERMS.identifier, DCTERMS.bibliographicCitation},
        )
        resource_iri = URIRef(resource.identity.iri)
        loci = list(projection.source_graph.objects(resource_iri, DCTERMS.source))
        self.assertEqual(
            loci,
            [
                URIRef(
                    "https://github.com/Entif-AI/Bilqis-MLX/source/locus/"
                    "9f390b250fdced5e651cb9c136d2b4c1b20947f3cb5b6ce15c70f2e549b4dfba"
                )
            ],
        )

    def test_atom_primary_and_secondary_assertions_preserve_multiple_loci(self):
        resource = self.resource(
            "https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CASE/ABS"
        )
        self.assertEqual(
            resource.source_records,
            (RecordRef("morphemes_atomic", "ATOM-7a69c1aeac9192"),),
        )
        projection = self.projector.project_resource(
            resource.identity, resource.source_records
        )
        self.assertEqual(projection.issues, ())
        self.assertEqual(projection.held, ())
        resource_iri = URIRef(resource.identity.iri)
        loci = set(projection.source_graph.objects(resource_iri, DCTERMS.source))
        self.assertEqual(len(loci), 2)
        citations = {
            str(value)
            for locus in loci
            for value in projection.source_graph.objects(
                locus, DCTERMS.bibliographicCitation
            )
        }
        self.assertTrue(any("source NI-WEB-CH04" in text for text in citations))
        self.assertTrue(any("source NI-WEB-CH07" in text for text in citations))
        self.assertEqual(
            {subject for subject, _, _ in projection.source_graph if subject == resource_iri},
            {resource_iri},
        )

    def test_duplicate_primary_and_assertion_locus_collapses(self):
        identity = Identity("grammar", ("CONFIGURATION", "MFF"))
        projection = self.projector.project_resource(
            identity, (RecordRef("morphemes_atomic", "ATOM-5ea26e72589ea3"),)
        )
        self.assertEqual(
            len(list(projection.source_graph.objects(URIRef(identity.iri), DCTERMS.source))),
            1,
        )

    def test_lexicon_sense_citation_uses_exact_split_and_printed_pages_without_page_fragment(self):
        resource = next(
            resource
            for resource in self.resolution.resources
            if RecordRef(
                "lexicon_root_senses", "LEXSENSE-e3f64d03c6f6ec"
            )
            in resource.source_records
        )
        projection = self.projector.project_resource(
            resource.identity, resource.source_records
        )
        self.assertEqual(projection.issues, ())
        resource_iri = URIRef(resource.identity.iri)
        locus = next(projection.source_graph.objects(resource_iri, DCTERMS.source))
        citation = str(
            next(
                projection.source_graph.objects(
                    locus, DCTERMS.bibliographicCitation
                )
            )
        )
        self.assertEqual(
            citation,
            "New Ithkuil lexicon (Curriculum Registry URL variant); "
            "source NI-LEXICON-CURRICULUM; chapter 2; section 2.1.1; root -SČ-; "
            "stem STEM 1; specification BSC; printed page 63; "
            "tracked chapter PDF page 57.",
        )
        source_url = next(projection.source_graph.objects(locus, DCTERMS.source))
        self.assertEqual(
            str(source_url), "https://ithkuil.net/New_Ithkuil_Lexicon.pdf"
        )
        self.assertNotIn("#page=", str(source_url))
        self.assertNotIn("canonical PDF page", citation)

    def test_lexicon_root_uses_its_exact_root_locus(self):
        resource = self.resource(
            "https://github.com/Entif-AI/Bilqis-MLX/id/root/"
            "NI-LEXICON-CURRICULUM/LEXROOT-c38edca4b6c30c"
        )
        projection = self.projector.project_resource(
            resource.identity, resource.source_records
        )
        self.assertEqual(projection.issues, ())
        locus = next(
            projection.source_graph.objects(
                URIRef(resource.identity.iri), DCTERMS.source
            )
        )
        citation = str(
            next(
                projection.source_graph.objects(
                    locus, DCTERMS.bibliographicCitation
                )
            )
        )
        self.assertIn("root -S-", citation)
        self.assertIn("printed page", citation)
        self.assertIn("tracked chapter PDF page", citation)

    def test_missing_record_is_held_and_emits_no_source_assertion(self):
        identity = Identity("grammar", ("CONFIGURATION", "MFF"))
        missing = RecordRef("morphemes_atomic", "ATOM-NOT-REAL")
        projection = self.projector.project_resource(identity, (missing,))
        self.assertEqual(len(projection.source_graph), 0)
        self.assertEqual(projection.held, (missing,))
        self.assertEqual(
            [issue.code for issue in projection.issues],
            ["SOURCE_RECORD_BINDING_MISMATCH"],
        )

    def test_valid_source_ref_cannot_support_unrelated_or_arbitrary_identity(self):
        mff_ref = RecordRef("morphemes_atomic", "ATOM-5ea26e72589ea3")
        unrelated = self.projector.project_resource(
            Identity("grammar", ("PHASE", "FLC")), (mff_ref,)
        )
        self.assertEqual(len(unrelated.source_graph), 0)
        self.assertEqual(
            [issue.code for issue in unrelated.issues],
            ["SOURCE_RECORD_BINDING_MISMATCH"],
        )
        arbitrary = self.projector.project_resource(
            Identity("grammar", ("CONFIGURATION", "SYNTHETIC")), (mff_ref,)
        )
        self.assertEqual(len(arbitrary.source_graph), 0)
        self.assertEqual(
            [issue.code for issue in arbitrary.issues],
            ["SOURCE_IDENTITY_NOT_RESOLVED"],
        )

    def mutate_mff_url(self, value, *, registry=True, atom=True):
        closure = self.closure
        if registry:
            closure = self.replace_table(
                closure,
                "source_manifest",
                lambda row: self.mutate_row(row, final_url=value)
                if row["source_id"] == "NI-WEB-CH03"
                else row,
            )
        if atom:
            closure = self.replace_table(
                closure,
                "morphemes_atomic",
                lambda row: self.mutate_row(row, primary_source_url=value)
                if row["atomic_id"] == "ATOM-5ea26e72589ea3"
                else row,
            )
            closure = self.replace_table(
                closure,
                "source_assertions",
                lambda row: self.mutate_row(row, source_url=value)
                if row["entity_id"] == "ATOM-5ea26e72589ea3"
                else row,
            )
        return closure

    def test_strict_public_url_allowlist_rejects_private_local_credentials_and_query(self):
        values = (
            "file:///Users/example/private/source.htm",
            "http://localhost/source.htm",
            "https://127.0.0.1/source.htm",
            "https://user:pass@www.ithkuil.net/source.htm",
            "https://www.ithkuil.net/source.htm?token=secret",
            "https://www.ithkuil.net/source%0A.htm",
            "https://syntheticprivate.example/source.htm",
        )
        identity = Identity("grammar", ("CONFIGURATION", "MFF"))
        ref = RecordRef("morphemes_atomic", "ATOM-5ea26e72589ea3")
        for value in values:
            with self.subTest(value=value):
                projection = SourceProjector(
                    self.mutate_mff_url(value)
                ).project_resource(identity, (ref,))
                self.assertEqual(len(projection.source_graph), 0)
                self.assertIn("SOURCE_URL_NOT_PUBLIC", {i.code for i in projection.issues})
                serialized = projection.source_graph.serialize(format="nt")
                self.assertNotIn(value, serialized)

    def test_public_but_out_of_registry_url_is_held(self):
        closure = self.mutate_mff_url(
            "https://www.ithkuil.net/newithkuil_05_verbs.htm",
            registry=False,
            atom=True,
        )
        identity = Identity("grammar", ("CONFIGURATION", "MFF"))
        projection = SourceProjector(closure).project_resource(
            identity, (RecordRef("morphemes_atomic", "ATOM-5ea26e72589ea3"),)
        )
        self.assertEqual(len(projection.source_graph), 0)
        self.assertIn(
            "SOURCE_URL_REGISTRY_MISMATCH", {issue.code for issue in projection.issues}
        )

    def test_public_literal_sanitization_prevents_private_path_disclosure(self):
        closure = self.replace_table(
            self.closure,
            "source_manifest",
            lambda row: self.mutate_row(row, title="/Users/example/private/source")
            if row["source_id"] == "NI-WEB-CH03"
            else row,
        )
        identity = Identity("grammar", ("CONFIGURATION", "MFF"))
        projection = SourceProjector(closure).project_resource(
            identity, (RecordRef("morphemes_atomic", "ATOM-5ea26e72589ea3"),)
        )
        self.assertEqual(len(projection.source_graph), 0)
        self.assertIn(
            "SOURCE_PUBLIC_LITERAL_REJECTED", {issue.code for issue in projection.issues}
        )

    def test_shuffled_closure_is_projection_invariant(self):
        resource = self.resource(
            "https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CASE/ABS"
        )
        expected = self.projector.project_resource(
            resource.identity, resource.source_records
        )
        shuffled = CompilerClosure(
            self.closure.manifest_version,
            tuple(
                LoadedTable(table.name, table.columns, tuple(reversed(table.rows)))
                for table in reversed(self.closure.tables)
            ),
        )
        actual = SourceProjector(shuffled).project_resource(
            resource.identity, resource.source_records
        )
        self.assertEqual(set(actual.source_graph), set(expected.source_graph))
        self.assertEqual(actual.issues, expected.issues)
        self.assertEqual(actual.held, expected.held)

    def test_constructed_scheme_can_use_union_of_resolved_member_loci_only(self):
        mff = self.resource(
            "https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CONFIGURATION/MFF"
        )
        lex = self.resource(
            "https://github.com/Entif-AI/Bilqis-MLX/id/root/"
            "NI-LEXICON-CURRICULUM/LEXROOT-c38edca4b6c30c"
        )
        scheme = Identity("scheme", ("new-ithkuil",))
        refs = tuple(sorted(set(mff.source_records + lex.source_records)))
        projection = self.projector.project_group(scheme, refs)
        self.assertEqual(projection.issues, ())
        self.assertEqual(projection.held, ())
        loci = set(
            projection.source_graph.objects(URIRef(scheme.iri), DCTERMS.source)
        )
        self.assertEqual(len(loci), 2)
        predicates = {predicate for _, predicate, _ in projection.source_graph}
        self.assertEqual(
            predicates,
            {DCTERMS.source, DCTERMS.identifier, DCTERMS.bibliographicCitation},
        )

    def test_current_resolution_all_resources_have_public_source_traceability(self):
        projected = 0
        for resource in self.resolution.resources:
            projection = self.projector.project_resource(
                resource.identity, resource.source_records
            )
            self.assertGreater(len(projection.source_graph), 0, resource.identity.iri)
            self.assertEqual(projection.issues, (), resource.identity.iri)
            self.assertEqual(projection.held, (), resource.identity.iri)
            projected += 1
        self.assertEqual(projected, CORE["resolved_resources"])


if __name__ == "__main__":
    unittest.main()
