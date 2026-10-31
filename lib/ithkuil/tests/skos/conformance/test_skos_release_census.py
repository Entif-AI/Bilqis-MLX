"""Release aggregation preserves owner receipts and rejects omitted accounting."""
from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

from copy import deepcopy
import json
from pathlib import Path
import unittest

from lib.ithkuil.src.release_census import aggregate, render_markdown
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.no_omission import SourceRowIdentity

FIXTURES = FIXTURES
VALID = json.loads((FIXTURES / 'no_omission_valid_receipt.json').read_text())
ROWS = tuple(SourceRowIdentity(**row) for row in
             json.loads((FIXTURES / 'no_omission_source_rows.json').read_text())['rows'])
FRONTIER = {'claims': {'full_new_ithkuil_coverage': False}, 'aggregates': {
    'unparsed_artifact_ids': ['UNPARSED-TEST-SOURCE'], 'debt': {'by_reason': {'TEST_DEBT': 2}}}}
REFS = {'coverage': {'file': 'coverage.json', 'sha256': 'a' * 64},
        'canonical_rdf': VALID['canonical_rdf'], 'frontier': {'receipt_sha256': 'b' * 64}}


def census(receipt=VALID, rows=ROWS):
    return aggregate('c' * 40, receipt, rows, FRONTIER, REFS)


class ReleaseCensusTests(unittest.TestCase):
    def test_complete_accounting_preserves_partial_coverage_and_named_debt(self):
        value = census()
        self.assertTrue(value['accounting_complete'])
        self.assertEqual(value['totals']['source_rows'], 10)
        self.assertEqual(value['totals']['dispositions'],
                         {'EMITTED': 5, 'HELD': 2, 'REJECTED': 1, 'UNSUPPORTED': 1, 'IR_ONLY': 1})
        self.assertEqual(value['remaining_frontier']['unparsed_artifact_ids'], ['UNPARSED-TEST-SOURCE'])
        self.assertFalse(value['full_new_ithkuil_coverage'])
        self.assertEqual(value['canonical_rdf'], VALID['canonical_rdf'])
        for name, domain in value['domains'].items():
            self.assertNotIn('rows', domain)
            self.assertEqual(domain['receipt']['pointer'], '/domains/' + name)
        self.assertIn('UNPARSED-TEST-SOURCE', render_markdown(value))
        self.assertIn('IR_ONLY', render_markdown(value))

    def test_missing_domain_cannot_report_complete(self):
        receipt = deepcopy(VALID)
        del receipt['domains']['mapping']
        with self.assertRaises(ProfileError) as caught:
            census(receipt)
        self.assertEqual(caught.exception.code, 'RELEASE_CENSUS_DOMAIN_SET_MISMATCH')

    def test_each_domain_row_omission_names_its_stable_id(self):
        for domain in VALID['domains']:
            with self.subTest(domain=domain):
                receipt = deepcopy(VALID)
                removed = receipt['domains'][domain]['rows'].pop()
                with self.assertRaises(ProfileError) as caught:
                    census(receipt)
                self.assertEqual(caught.exception.code, 'NO_OMISSION_MISMATCH')
                self.assertIn('missing=' + ':'.join((domain, removed['table'], removed['key'])),
                              caught.exception.details)

    def test_row_overlap_across_domains_is_not_counted_twice(self):
        row = ROWS[0]
        other_domain = next(name for name in VALID['domains'] if name != row.domain)
        with self.assertRaises(ProfileError) as caught:
            census(rows=(*ROWS, SourceRowIdentity(other_domain, row.table, row.key)))
        self.assertEqual(caught.exception.code, 'RELEASE_CENSUS_DOMAIN_OVERLAP')

    def test_wrong_canonical_digest_cannot_bind_the_receipt(self):
        refs = deepcopy(REFS)
        refs['canonical_rdf']['sha256'] = 'd' * 64
        with self.assertRaises(ProfileError) as caught:
            aggregate('c' * 40, VALID, ROWS, FRONTIER, refs)
        self.assertEqual(caught.exception.code, 'RELEASE_CENSUS_CANONICAL_MISMATCH')


if __name__ == '__main__':
    unittest.main()
