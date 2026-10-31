from dataclasses import replace
import unittest

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from lib.ithkuil.src.skos.mapping import MappingClaim
from lib.ithkuil.src.skos.mapping_admission import load_policy
from lib.ithkuil.src.skos.mapping_emit import ReviewedMappingRow
from lib.ithkuil.src.skos.mapping_validate import validate_mapping_batch
from lib.ithkuil.src.skos.resolver import RecordRef


class MappingConflictTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()
        self.source, self.target = 'https://example.org/a', 'https://example.org/b'
        self.left, self.right = 'https://example.org/scheme-a', 'https://example.org/scheme-b'
        self.graph = Graph()
        for iri, scheme in ((self.source, self.left), (self.target, self.right)):
            self.graph.add((URIRef(iri), RDF.type, SKOS.Concept))
            self.graph.add((URIRef(iri), SKOS.inScheme, URIRef(scheme)))
            self.graph.add((URIRef(scheme), RDF.type, SKOS.ConceptScheme))
        self.claim = MappingClaim(self.source, self.target, self.left, self.right,
                                  'exactMatch', 'admitted_exact_equivalence',
                                  'synthetic:source', 'synthetic:review', True,
                                  'synthetic:proof', 'synthetic:qualification', 'synthetic:direction')

    def row(self, key, **changes):
        return ReviewedMappingRow(RecordRef('synthetic_reviewed_mapping', key), replace(self.claim, **changes))

    def assert_blocked(self, rows, code):
        result = validate_mapping_batch(rows, self.graph, self.policy)
        self.assertFalse(result.complete)
        self.assertEqual(len(result.graph), 0)
        self.assertIn(code, {issue.code for issue in result.issues})
        self.assertEqual(result.held_records, tuple(sorted(row.record_ref for row in rows)))
        return result

    def test_exact_and_rejected_equivalence_name_both_input_rows(self):
        rows = (self.row('accepted'), self.row('rejected', review_state='rejected_equivalence', evidence_ref='synthetic:other'))
        result = self.assert_blocked(rows, 'MAPPING_REJECTED_EQUIVALENCE_CONFLICT')
        problem = next(issue for issue in result.issues if issue.code == 'MAPPING_REJECTED_EQUIVALENCE_CONFLICT')
        self.assertEqual(problem.record_refs, tuple(sorted(row.record_ref for row in rows)))
        self.assertEqual(problem.details, (self.source, self.target))

    def test_opposite_direction_from_one_source_review_is_not_arbitrated(self):
        rows = (self.row('broad', predicate='broadMatch', review_state='admitted_broad_match'),
                self.row('narrow', predicate='narrowMatch', review_state='admitted_narrow_match'))
        self.assert_blocked(rows, 'MAPPING_DIRECTION_CONFLICT')

    def test_independently_qualified_hierarchy_cycle_is_not_automatically_forbidden(self):
        rows = (self.row('broad', predicate='broadMatch', review_state='admitted_broad_match'),
                self.row('narrow', predicate='narrowMatch', review_state='admitted_narrow_match',
                         source_ref='synthetic:other-source', evidence_ref='synthetic:other-review'))
        result = validate_mapping_batch(rows, self.graph, self.policy)
        self.assertTrue(result.complete)
        self.assertEqual(len(result.graph), 4)

    def test_missing_source_and_target_endpoints_have_exact_codes(self):
        for field, code in (('source_iri', 'MAPPING_SOURCE_ENDPOINT_MISSING'),
                            ('target_iri', 'MAPPING_TARGET_ENDPOINT_MISSING')):
            self.assert_blocked((self.row(field, **{field: 'https://example.org/missing'}),), code)

    def test_ambiguous_and_unsupported_endpoint_kinds_fail(self):
        self.graph.add((URIRef(self.target), RDF.type, SKOS.Collection))
        self.assert_blocked((self.row('ambiguous'),), 'MAPPING_ENDPOINT_AMBIGUOUS')
        self.graph.remove((URIRef(self.target), RDF.type, None))
        self.graph.add((URIRef(self.target), RDF.type, RDFS.Resource))
        self.assert_blocked((self.row('generic'),), 'MAPPING_ENDPOINT_KIND_UNSUPPORTED')

    def test_unknown_future_state_prevents_complete_batch_output(self):
        rows = (self.row('valid'), self.row('unknown', review_state='future-unreviewed'))
        self.assert_blocked(rows, 'MAPPING_NORMALIZED_STATE_UNSUPPORTED')

    def test_duplicate_equivalent_rows_keep_accounting_without_conflict(self):
        rows = (self.row('a'), self.row('b'))
        result = validate_mapping_batch(rows, self.graph, self.policy)
        self.assertTrue(result.complete)
        self.assertEqual(len(result.graph), 2)
        self.assertEqual(result.emitted_records, tuple(row.record_ref for row in rows))
        self.assertEqual(result.assertions[0].record_refs, tuple(row.record_ref for row in rows))

    def test_conflicting_strengths_under_same_review_are_not_first_row_wins(self):
        rows = (self.row('exact'), self.row('close', predicate='closeMatch', review_state='admitted_close_match'))
        forward = self.assert_blocked(rows, 'MAPPING_CONFLICTING_SOURCE_ASSERTIONS')
        reverse = self.assert_blocked(tuple(reversed(rows)), 'MAPPING_CONFLICTING_SOURCE_ASSERTIONS')
        self.assertEqual(forward.issues, reverse.issues)

    def test_held_proposal_remains_visible_without_creating_an_assertion(self):
        row = self.row('proposal', review_state='proposal')
        result = validate_mapping_batch((row,), self.graph, self.policy)
        self.assertTrue(result.complete)
        self.assertEqual(result.held_records, (row.record_ref,))
        self.assertEqual(len(result.graph), 0)


if __name__ == '__main__':
    unittest.main()
