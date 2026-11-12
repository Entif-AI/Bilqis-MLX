"""Final C01 authority amendments resolve the last two dependency holds."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from scripts.bamf.workstack_dependencies import (
    EvidenceStatus,
    check_dependency_evidence,
    load_dependency_sources,
)
from scripts.tests.bamf.test_workstack_dependencies import pinned_matrix


class FinalAuthorityNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[3] / 'docs/tasks/bamf-0.2'
        cls.registry = json.loads((cls.root / 'children/registry.json').read_text())
        cls.numbers = json.loads((cls.root / 'issue-map.json').read_text())
        cls.sources = load_dependency_sources(cls.root, cls.registry)

    def entry(self, key):
        return deepcopy(next(row for row in self.registry['entries'] if row['key'] == key))

    def assert_amendment_is_gating(self, key, source_id):
        entry = self.entry(key)
        body = self.sources[key + '.body']
        sources = dict(self.sources)
        self.assertIs(check_dependency_evidence(entry, body, self.numbers, sources).status,
                      EvidenceStatus.RESOLVED)

        missing = deepcopy(entry)
        missing['dependency_evidence']['source_records'] = [
            row for row in missing['dependency_evidence']['source_records']
            if row['source_id'] != source_id
        ]
        missing_sources = dict(sources)
        missing_sources.pop(source_id)
        missing_sources['reviewed-packets'] = pinned_matrix(missing)
        self.assertIs(check_dependency_evidence(missing, body, self.numbers, missing_sources).status,
                      EvidenceStatus.INVALID)

        forged = deepcopy(entry)
        forged_sources = dict(sources)
        forged_bytes = b'forged authority amendment'
        forged_sources[source_id] = forged_bytes
        record = next(row for row in forged['dependency_evidence']['source_records']
                      if row['source_id'] == source_id)
        record['sha256'] = hashlib.sha256(forged_bytes).hexdigest()
        record['excerpt'] = forged_bytes.decode()
        forged_sources['reviewed-packets'] = pinned_matrix(forged)
        self.assertIs(check_dependency_evidence(forged, body, self.numbers, forged_sources).status,
                      EvidenceStatus.INVALID)

        missing_receipt = deepcopy(entry)
        missing_receipt['dependency_evidence']['external_receipts'] = []
        receipt_sources = dict(sources)
        receipt_sources['reviewed-packets'] = pinned_matrix(missing_receipt)
        self.assertIs(check_dependency_evidence(
            missing_receipt, body, self.numbers, receipt_sources).status,
            EvidenceStatus.INVALID)

    def test_a05_5_authority_amendment_resolves_exact_a01_a13_edges(self):
        entry = self.entry('A05.5')
        self.assertEqual(entry['deps'], ['A01', 'A13'])
        self.assert_amendment_is_gating('A05.5', 'A05.5.comment-6838106985')

    def test_a08_1b_5_authority_amendment_resolves_census_and_sibling_edges(self):
        entry = self.entry('A08.1b.5')
        self.assertEqual(entry['deps'], [
            'A08.1a', 'A08.1b.1', 'A08.1b.2', 'A08.1b.3', 'A08.1b.4'])
        self.assert_amendment_is_gating('A08.1b.5', 'A08.1b.5.comment-6838107336')
