"""Literal registry census behavior: missing, duplicates and owner exclusions."""
from __future__ import annotations

import unittest

from scripts.bamf.audit_child_registry import audit


class ChildRegistryAuditTests(unittest.TestCase):
    def setUp(self):
        self.registry = {'entries': [
            {'key': 'A08.1b', 'number': 418},
            {'key': 'B11.1', 'number': 471},
            {'key': 'B11.1a', 'number': 586},
        ]}
        self.workstack = {'items': [{'key': 'A08', 'number': 364}]}
        self.issues = [
            {'number': 364, 'title': 'BAMF-0.2 A08 owner', 'state': 'OPEN'},
            {'number': 418, 'title': 'BAMF-0.2 A08.1b parent', 'state': 'OPEN'},
            {'number': 471, 'title': 'BAMF-0.2 B11.1 parent', 'state': 'OPEN'},
            {'number': 586, 'title': 'BAMF-0.2 B11.1a producer', 'state': 'OPEN'},
            {'number': 587, 'title': 'BAMF-0.2 B11.1a duplicate', 'state': 'CLOSED'},
            {'number': 556, 'title': 'BAMF-0.2 A08.1b.4 scope', 'state': 'OPEN'},
        ]

    def test_missing_and_duplicate_are_distinct(self):
        result = audit(self.registry, self.workstack, self.issues)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['missing_issue_count'], 2)
        self.assertEqual(result['missing_unique_keys'], 2)
        self.assertEqual([x['number'] for x in result['missing']], [556, 587])
        self.assertEqual(result['duplicates'][0]['key'], 'B11.1a')
        self.assertEqual([x['number'] for x in result['duplicates'][0]['issues']],
                         [586, 587])
        self.assertEqual(result['owner_count'], 1)

    def test_complete_when_all_registered_and_no_duplicates(self):
        issues=[x for x in self.issues if x['number'] not in (556,587)]
        result=audit(self.registry,self.workstack,issues)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['missing'],[])
        self.assertEqual(result['duplicates'],[])

    def test_wrong_number_detects_stale_registered_identity(self):
        registry={'entries':[{'key':'A08.1b.4','number':999}]}
        result=audit(registry,{'items':[]},[self.issues[-1]])
        self.assertEqual(result['wrong_number'][0]['live_numbers'],[556])
        self.assertEqual(result['missing_issue_count'],1)

    def test_non_bamf_title_is_not_admitted(self):
        result=audit({'entries':[]},{'items':[]},[
            {'number':123,'title':'Another project A08.1b.4','state':'OPEN'}])
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['matched_live_count'],0)


if __name__ == '__main__':
    unittest.main()
