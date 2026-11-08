"""Accepted late contracts retain provenance and exact direct-child dispatch."""
from copy import deepcopy
import hashlib
import json
import subprocess
import sys
import unittest

from scripts import verify_bamf_0_2_contracts as contracts
from scripts.bamf.workstack_dependencies import load_dependency_sources, pinned_dependency_keys
from bamf02_groom_contracts import plan_for


class IssueContractRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((contracts.TASKS / 'children/registry.json').read_text())
        cls.entries = cls.registry['entries']
        cls.issue_map = json.loads((contracts.TASKS / 'issue-map.json').read_text())
        cls.sources = load_dependency_sources(contracts.TASKS, cls.registry)
        cls.pinned = pinned_dependency_keys(cls.sources)

    def entry(self, key):
        return deepcopy(next(row for row in self.entries if row['key'] == key))

    def body(self, key):
        return (contracts.TASKS / 'children' / (key + '.md')).read_text()

    def test_actual_cli_accepts_registered_contracts_and_retains_all_holds(self):
        result = subprocess.run(
            [sys.executable, '-B', str(contracts.ROOT / 'scripts/verify_bamf_0_2_contracts.py')],
            cwd=contracts.ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('214 BAMF owner/child specs', result.stdout)
        self.assertIn('171 total indexed recursive child mirrors', result.stdout)
        self.assertIn('8 dependency normalization holds retained; no executable order', result.stdout)

    def test_actual_late_packets_have_source_provenance_without_generated_markers(self):
        for key in ('A08.1b.1', 'A08.1b.2', 'A08.1b.3', 'A08.1b.4',
                    'A08.1b.5', 'A05.5', 'B10.5'):
            with self.subTest(key=key):
                self.assertTrue(contracts.child_has_provenance(
                    self.entry(key), self.body(key), self.issue_map, self.sources))

    def test_missing_or_changed_source_cannot_replace_the_marker(self):
        entry = self.entry('A05.5')
        body = self.body('A05.5')
        for field, value in (('parent_number', 999), ('number', 999),
                             ('key', 'A05.99')):
            forged = deepcopy(entry)
            forged[field] = value
            with self.subTest(field=field):
                self.assertFalse(contracts.child_has_provenance(
                    forged, body, self.issue_map, self.sources))
        self.assertFalse(contracts.child_has_provenance(
            entry, body, self.issue_map, {}))
        changed = body + '\nUnapproved instruction.\n'
        entry['body_sha256'] = hashlib.sha256(changed.encode()).hexdigest()
        entry['dependency_evidence']['body_sha256'] = entry['body_sha256']
        self.assertFalse(contracts.child_has_provenance(
            entry, changed, self.issue_map, self.sources))

    def test_generated_packet_still_requires_its_exact_marker(self):
        entry = self.entry('A01.1')
        self.assertTrue(contracts.child_has_provenance(
            entry, self.body('A01.1'), self.issue_map, self.sources))
        self.assertFalse(contracts.child_has_provenance(
            entry, '<!-- BAMF02:WORK-PACKET:A01.2 -->', self.issue_map, self.sources))

    def test_registered_late_children_extend_the_historical_partition(self):
        for key in ('A03', 'A05', 'B02', 'B05', 'B10', 'C08', 'C14'):
            item = deepcopy(next(row for row in contracts.ITEMS if row['key'] == key))
            body = (contracts.TASKS / 'issues' / (key + '.md')).read_text()
            original = [row['key'] for row in plan_for(
                key, body, item['number'], item['deps']) if row['parent'] == key]
            with self.subTest(key=key):
                self.assertTrue(contracts.direct_dispatch_matches(
                    item, original, self.entries, self.pinned))

    def test_dispatch_rejects_missing_reordered_duplicate_and_unreviewed_children(self):
        item = deepcopy(next(row for row in contracts.ITEMS if row['key'] == 'B05'))
        original = item['children'][:-1]
        for children in (item['children'][:-1], item['children'][::-1],
                         [*item['children'], item['children'][-1]]):
            with self.subTest(children=children):
                self.assertFalse(contracts.direct_dispatch_matches(
                    {**item, 'children': children}, original, self.entries, self.pinned))
        self.assertFalse(contracts.direct_dispatch_matches(
            item, original, self.entries, self.pinned - {'B05.4'}))
        changed = deepcopy(self.entries)
        next(row for row in changed if row['key'] == 'B05.4')['parent_key'] = 'B04'
        self.assertFalse(contracts.direct_dispatch_matches(
            item, original, changed, self.pinned))
        missing = [row for row in self.entries if row['key'] != 'B05.1']
        self.assertFalse(contracts.direct_dispatch_matches(
            {**item, 'children': item['children'][1:]}, original, missing, self.pinned))


    def test_egm_policy_is_design_first_and_lanes_delegate_to_canonical_lifecycle(self):
        marker = "<!-- BAMF02:DESIGN-VERIFY-DRIFT-LIFECYCLE:20261108 -->"
        self.assertEqual(contracts.EGM_POLICY_MARKER, marker)
        agents = (contracts.ROOT / "AGENTS.md").read_text()
        egm = (contracts.TASKS / "EGM_EXECUTION.md").read_text()
        self.assertIn(marker, agents)
        self.assertIn("EGM review occurs before implementation.", egm)
        self.assertIn("minimum sufficient evidence set", egm)
        for filename in contracts.EGM_OPERATIONAL_DOCS[1:]:
            lane = (contracts.ROOT / filename).read_text()
            self.assertIn("docs/tasks/bamf-0.2/EGM_EXECUTION.md", lane)
            self.assertIn("before substantive implementation", lane.lower())


if __name__ == '__main__':
    unittest.main()
