"""Literal prerequisite amendments preserve their positive and negative boundaries."""
import json
from pathlib import Path
import unittest

from scripts.bamf.workstack_clause_formats import parse_clause

ROOT = Path(__file__).resolve().parents[3] / 'docs/tasks/bamf-0.2'


class ClauseFormatTests(unittest.TestCase):
    def setUp(self):
        self.numbers = json.loads((ROOT / 'issue-map.json').read_text())
        self.producer = (ROOT / 'children/B05.4.md').read_text()
        self.parent = (ROOT / 'children/B11.1.md').read_text()

    def test_selector_consumes_only_original_inputs_and_canonical_producer(self):
        self.assertEqual(parse_clause(self.producer, self.numbers),
                         (('B01', 'B04', 'B11.1a'), ()))

    def test_parent_keeps_all_seven_inputs_and_adds_its_required_child(self):
        self.assertEqual(parse_clause(self.parent, self.numbers),
                         (('B03', 'B04', 'B05', 'B06', 'B08', 'B09', 'B10', 'B11.1a'), ()))

    def test_both_selector_declarations_and_repeated_producer_number_are_required(self):
        for old, new in (
                ('Consumes B01', 'Historical B01'),
                ('The missing producer authority is now owned by', 'Historical producer context:'),
                ('Until #586 is implemented', 'Until #587 is implemented')):
            with self.subTest(old=old):
                self.assertIsNone(parse_clause(self.producer.replace(old, new), self.numbers))

    def test_parent_requires_its_own_mandatory_acceptance_statement(self):
        for new in ('B11.1 may inspect historical #586 producer',
                    'B11.2 must consume the accepted #586 producer'):
            with self.subTest(new=new):
                body = self.parent.replace('B11.1 must consume the accepted #586 producer', new)
                self.assertIsNone(parse_clause(body, self.numbers))

    def test_foreign_child_link_is_refused_in_both_formats(self):
        for body in (self.producer, self.parent):
            changed = body.replace('/issues/586)', '/issues/587)')
            self.assertIsNone(parse_clause(changed, self.numbers))

    def test_multiple_parent_child_declarations_are_not_silently_truncated(self):
        line = next(line for line in self.parent.splitlines()
                    if line.startswith('B11.1 now has a prerequisite implementation child:'))
        self.assertIsNone(parse_clause(self.parent + '\n' + line, self.numbers))
