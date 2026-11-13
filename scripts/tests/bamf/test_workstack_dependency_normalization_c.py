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
        self.assertEqual(
            [row['role'] for row in entry['dependency_evidence']['external_receipts']],
            ['implementation'],
        )
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

        wrong_role = deepcopy(entry)
        wrong_role['dependency_evidence']['external_receipts'][0]['role'] = 'prerequisite'
        wrong_role_sources = dict(sources)
        wrong_role_sources['reviewed-packets'] = pinned_matrix(wrong_role)
        self.assertIs(check_dependency_evidence(
            wrong_role, body, self.numbers, wrong_role_sources).status,
            EvidenceStatus.INVALID)

        split_source = deepcopy(entry)
        original_receipt = split_source['dependency_evidence']['external_receipts'][0]
        forged_source_id = key + '.pr-9999'
        forged_pr = json.dumps({
            'number': original_receipt['number'],
            'state': 'MERGED',
            'url': original_receipt['url'],
            'headRefOid': 'c' * 40,
            'mergeCommit': {'oid': 'd' * 40},
        }, sort_keys=True).encode()
        split_source_sources = dict(sources)
        split_source_sources[forged_source_id] = forged_pr
        split_source['dependency_evidence']['source_records'].append({
            'source_id': forged_source_id,
            'kind': 'pull_request',
            'locator': original_receipt['url'],
            'sha256': hashlib.sha256(forged_pr).hexdigest(),
            'excerpt': 'd' * 40,
        })
        original_receipt['source_id'] = forged_source_id
        original_receipt['head_sha'] = 'c' * 40
        original_receipt['merge_sha'] = 'd' * 40
        split_source_sources['reviewed-packets'] = pinned_matrix(split_source)
        self.assertIs(check_dependency_evidence(
            split_source, body, self.numbers, split_source_sources).status,
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

        narrowed = deepcopy(entry)
        narrowed_edges = ['A08.1b.1', 'A08.1b.2', 'A08.1b.3', 'A08.1b.4']
        narrowed['deps'] = narrowed_edges
        narrowed['dependency_evidence']['known_edges'] = narrowed_edges
        narrowed['dependency_evidence']['clause'] = (
            '**Direct prerequisites:** A08.1b.1 through A08.1b.4.')
        narrowed['dependency_evidence']['external_receipts'] = []
        narrowed_sources = dict(self.sources)
        narrowed_sources['reviewed-packets'] = pinned_matrix(narrowed)
        self.assertIs(check_dependency_evidence(
            narrowed,
            narrowed_sources['A08.1b.5.body'],
            self.numbers,
            narrowed_sources,
        ).status, EvidenceStatus.INVALID)
