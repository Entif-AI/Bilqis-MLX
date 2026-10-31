from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
from dataclasses import replace
from pathlib import Path
import unittest

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, SKOS

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.mapping import MappingClaim
from lib.ithkuil.src.skos.mapping_admission import load_policy
from lib.ithkuil.src.skos.mapping_emit import ReviewedMappingRow, emit_admitted_mappings
from lib.ithkuil.src.skos.resolver import RecordRef


FIXTURES = FIXTURES
SOURCE_SCHEME = "https://example.org/fixture/scheme/source"
TARGET_SCHEME = "https://example.org/fixture/scheme/target"
CASES = (
    ("exactMatch", "admitted_exact_equivalence"),
    ("closeMatch", "admitted_close_match"),
    ("broadMatch", "admitted_broad_match"),
    ("narrowMatch", "admitted_narrow_match"),
    ("relatedMatch", "admitted_related_match"),
)


def fixture():
    graph, rows = Graph(), []
    for scheme in (SOURCE_SCHEME, TARGET_SCHEME):
        graph.add((URIRef(scheme), RDF.type, SKOS.ConceptScheme))
    for predicate, state in CASES:
        source = "https://example.org/fixture/source/" + predicate
        target = "https://example.org/fixture/target/" + predicate
        for iri, scheme in ((source, SOURCE_SCHEME), (target, TARGET_SCHEME)):
            graph.add((URIRef(iri), RDF.type, SKOS.Concept))
            graph.add((URIRef(iri), SKOS.inScheme, URIRef(scheme)))
        claim = MappingClaim(source, target, SOURCE_SCHEME, TARGET_SCHEME, predicate, state,
                             "synthetic:source-" + predicate, "synthetic:review-" + predicate,
                             True, "synthetic:exact-proof", "synthetic:close-proof", "synthetic:direction-proof")
        rows.append(ReviewedMappingRow(RecordRef("synthetic_reviewed_mapping", predicate), claim))
    return graph, tuple(rows)


def reviewed_row(key, source, target, source_scheme, target_scheme, predicate, state, source_ref=None):
    claim = MappingClaim(
        source, target, source_scheme, target_scheme, predicate, state,
        source_ref or 'synthetic:source-' + key, 'synthetic:review-' + key, True,
        'synthetic:exact-' + key if predicate == 'exactMatch' else None,
        'synthetic:close-' + key if predicate == 'closeMatch' else None,
        'synthetic:direction-' + key if predicate in {'broadMatch', 'narrowMatch'} else None,
    )
    return ReviewedMappingRow(RecordRef('synthetic_reviewed_mapping', key), claim)


def endpoint_graph(*bindings):
    graph = Graph()
    for iri, scheme in bindings:
        graph.add((URIRef(iri), RDF.type, SKOS.Concept))
        graph.add((URIRef(iri), SKOS.inScheme, URIRef(scheme)))
        graph.add((URIRef(scheme), RDF.type, SKOS.ConceptScheme))
    return graph


class MappingEmitterTests(unittest.TestCase):
    def setUp(self):
        self.graph, self.rows = fixture()
        self.policy = load_policy()

    def test_all_five_predicates_match_literal_output_without_identity_collapse(self):
        result = emit_admitted_mappings(self.rows, self.graph, self.policy)
        expected = Graph().parse(FIXTURES / "skos_mapping_emit_expected.nt", format="nt")
        self.assertEqual(set(result.graph), set(expected))
        self.assertEqual(len(result.graph), 10)
        self.assertEqual(result.issues, ())
        self.assertEqual(result.held_records, ())
        self.assertEqual(result.emitted_records, tuple(sorted(row.record_ref for row in self.rows)))
        self.assertNotIn(OWL.sameAs, set(result.graph.predicates()))
        self.assertEqual(set(self.graph.subjects(RDF.type, SKOS.Concept)),
                         {URIRef(row.claim.source_iri) for row in self.rows} |
                         {URIRef(row.claim.target_iri) for row in self.rows})

    def test_broad_and_narrow_preserve_direction_and_inverse(self):
        result = emit_admitted_mappings(self.rows, self.graph, self.policy)
        broad, narrow = self.rows[2].claim, self.rows[3].claim
        self.assertIn((URIRef(broad.source_iri), SKOS.broadMatch, URIRef(broad.target_iri)), result.graph)
        self.assertIn((URIRef(broad.target_iri), SKOS.narrowMatch, URIRef(broad.source_iri)), result.graph)
        self.assertIn((URIRef(narrow.target_iri), SKOS.broadMatch, URIRef(narrow.source_iri)), result.graph)
        self.assertNotIn((URIRef(broad.source_iri), SKOS.narrowMatch, URIRef(broad.target_iri)), result.graph)

    def test_duplicate_equivalent_assertions_keep_both_row_refs(self):
        first = self.rows[0]
        second = replace(first, record_ref=RecordRef("synthetic_reviewed_mapping", "second-exact"))
        result = emit_admitted_mappings((first, second), self.graph, self.policy)
        self.assertEqual(len(result.graph), 2)
        self.assertEqual(len(result.emitted_records), 2)
        self.assertEqual(len(result.assertions), 2)
        for assertion in result.assertions:
            self.assertEqual(assertion.record_refs, tuple(sorted((first.record_ref, second.record_ref))))

    def test_unadmitted_and_weaker_states_cannot_enter_exact_emitter(self):
        for state in ("proposal", "admitted_close_match", "APPROVED_QUALIFIED_RELATION", "future-state"):
            row = replace(self.rows[0], claim=replace(self.rows[0].claim, review_state=state))
            result = emit_admitted_mappings((row,), self.graph, self.policy)
            self.assertEqual(len(result.graph), 0)
            self.assertEqual(result.held_records, (row.record_ref,))
            self.assertEqual(result.issues[0].code, "MAPPING_NORMALIZED_STATE_UNSUPPORTED")

    def test_missing_endpoint_scheme_or_wrong_resource_kind_is_held(self):
        row = self.rows[0]
        for change, expected in (
            ((URIRef(row.claim.source_iri), RDF.type, SKOS.Concept), "MAPPING_SOURCE_ENDPOINT_MISSING"),
            ((URIRef(row.claim.target_iri), RDF.type, SKOS.Concept), "MAPPING_TARGET_ENDPOINT_MISSING"),
            ((URIRef(TARGET_SCHEME), RDF.type, SKOS.ConceptScheme), "MAPPING_SCHEME_NOT_ADMITTED"),
            ((URIRef(row.claim.target_iri), SKOS.inScheme, URIRef(TARGET_SCHEME)), "MAPPING_ENDPOINT_SCHEME_MISMATCH"),
        ):
            graph = Graph()
            graph += self.graph
            graph.remove(change)
            result = emit_admitted_mappings((row,), graph, self.policy)
            self.assertEqual(result.issues[0].code, expected)
            self.assertEqual(len(result.graph), 0)
        self.graph.add((URIRef(row.claim.source_iri), RDF.type, SKOS.Collection))
        result = emit_admitted_mappings((row,), self.graph, self.policy)
        self.assertEqual(result.issues[0].code, "MAPPING_ENDPOINT_AMBIGUOUS")

    def test_exactness_evidence_is_still_required_after_table_admission(self):
        row = replace(self.rows[0], claim=replace(self.rows[0].claim, exactness_proof_ref=None))
        result = emit_admitted_mappings((row,), self.graph, self.policy)
        self.assertEqual(result.issues[0].code, "EXACT_MATCH_PROOF_REQUIRED")
        self.assertEqual(len(result.graph), 0)

    def test_reordering_preserves_graph_and_row_accounting(self):
        forward = emit_admitted_mappings(self.rows, self.graph, self.policy)
        reverse = emit_admitted_mappings(reversed(self.rows), self.graph, self.policy)
        self.assertEqual(canonicalize(forward.graph), canonicalize(reverse.graph))
        self.assertEqual(forward.assertions, reverse.assertions)
        self.assertEqual(forward.emitted_records, reverse.emitted_records)

    def test_source_row_identity_cannot_be_duplicated_or_implicit(self):
        with self.assertRaises(ProfileError) as caught:
            emit_admitted_mappings((self.rows[0], self.rows[0]), self.graph, self.policy)
        self.assertEqual(caught.exception.code, "DUPLICATE_MAPPING_RECORD_ID")
        with self.assertRaises(ProfileError) as caught:
            emit_admitted_mappings((self.rows[0].claim,), self.graph, self.policy)
        self.assertEqual(caught.exception.code, "REVIEWED_MAPPING_ROW_REQUIRED")

    def test_direct_conflict_names_only_conflicting_pair_predicates_but_holds_whole_batch(self):
        a, b, c, d = (f'https://example.org/{name}' for name in 'abcd')
        s1, s2 = 'https://example.org/s1', 'https://example.org/s2'
        graph = endpoint_graph((a, s1), (b, s2), (c, s1), (d, s2))
        rows = (
            reviewed_row('exact-ab', a, b, s1, s2, 'exactMatch', 'admitted_exact_equivalence'),
            reviewed_row('related-ab', a, b, s1, s2, 'relatedMatch', 'admitted_related_match'),
            reviewed_row('close-ab', a, b, s1, s2, 'closeMatch', 'admitted_close_match'),
            reviewed_row('close-cd', c, d, s1, s2, 'closeMatch', 'admitted_close_match'),
        )
        forward = emit_admitted_mappings(rows, graph, self.policy)
        reverse = emit_admitted_mappings(reversed(rows), graph, self.policy)
        for result in (forward, reverse):
            issue = next(item for item in result.issues if item.code == 'CONFLICTING_MAPPING_PREDICATES')
            self.assertEqual(tuple(ref.key for ref in issue.record_refs), ('exact-ab', 'related-ab'))
            self.assertEqual(result.held_records, tuple(sorted(row.record_ref for row in rows)))
            self.assertEqual(len(result.graph), 0)
        self.assertEqual(forward.issues, reverse.issues)

    def test_exact_transitive_conflict_names_deterministic_path_and_duplicate_contributors(self):
        a, b, c, d, e = (f'https://example.org/{name}' for name in 'abcde')
        s1, s2, s3 = 'https://example.org/s1', 'https://example.org/s2', 'https://example.org/s3'
        graph = endpoint_graph((a, s1), (b, s2), (c, s3), (d, s1), (e, s2))
        rows = (
            reviewed_row('exact-ab-1', a, b, s1, s2, 'exactMatch', 'admitted_exact_equivalence'),
            reviewed_row('exact-ab-2', a, b, s1, s2, 'exactMatch', 'admitted_exact_equivalence', 'synthetic:source-ab-2'),
            reviewed_row('exact-bc', b, c, s2, s3, 'exactMatch', 'admitted_exact_equivalence'),
            reviewed_row('related-ac', a, c, s1, s3, 'relatedMatch', 'admitted_related_match'),
            reviewed_row('close-de', d, e, s1, s2, 'closeMatch', 'admitted_close_match'),
        )
        expected = ('exact-ab-1', 'exact-ab-2', 'exact-bc', 'related-ac')
        forward = emit_admitted_mappings(rows, graph, self.policy)
        reverse = emit_admitted_mappings(reversed(rows), graph, self.policy)
        for result in (forward, reverse):
            issue = next(item for item in result.issues if item.code == 'ENTAILED_MAPPING_CONFLICT')
            self.assertIn('EXACT_MATCH_TRANSITIVE_CLASH', issue.details)
            self.assertEqual(tuple(ref.key for ref in issue.record_refs), expected)
            self.assertEqual(result.held_records, tuple(sorted(row.record_ref for row in rows)))
            self.assertEqual(len(result.graph), 0)
        self.assertEqual(forward.issues, reverse.issues)

    def test_hierarchy_transitive_conflict_names_path_and_related_claim_only(self):
        a, b, c, d, e = (f'https://example.org/{name}' for name in 'abcde')
        s1, s2, s3 = 'https://example.org/s1', 'https://example.org/s2', 'https://example.org/s3'
        graph = endpoint_graph((a, s1), (b, s2), (c, s3), (d, s1), (e, s2))
        rows = (
            reviewed_row('broad-ab', a, b, s1, s2, 'broadMatch', 'admitted_broad_match'),
            reviewed_row('broad-bc', b, c, s2, s3, 'broadMatch', 'admitted_broad_match'),
            reviewed_row('related-ac', a, c, s1, s3, 'relatedMatch', 'admitted_related_match'),
            reviewed_row('close-de', d, e, s1, s2, 'closeMatch', 'admitted_close_match'),
        )
        expected = ('broad-ab', 'broad-bc', 'related-ac')
        forward = emit_admitted_mappings(rows, graph, self.policy)
        reverse = emit_admitted_mappings(reversed(rows), graph, self.policy)
        for result in (forward, reverse):
            issue = next(item for item in result.issues if item.code == 'ENTAILED_MAPPING_CONFLICT')
            self.assertIn('HIERARCHY_RELATED_CLASH', issue.details)
            self.assertEqual(tuple(ref.key for ref in issue.record_refs), expected)
            self.assertEqual(result.held_records, tuple(sorted(row.record_ref for row in rows)))
            self.assertEqual(len(result.graph), 0)
        self.assertEqual(forward.issues, reverse.issues)


if __name__ == "__main__":
    unittest.main()
