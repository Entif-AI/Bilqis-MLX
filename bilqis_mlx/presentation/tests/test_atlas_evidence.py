"""BAMF observation evidence stays separate, source-bound and read-only."""
import copy
import unittest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.presentation.atlas_evidence import parse_evidence, render_evidence
from bilqis_mlx.presentation.dashboard import ingest
from bilqis_mlx.presentation.tests.test_bamf_metrics import board, receipt


def evidence():
    return {
        'candidate_sha256': 'f' * 64, 'parent_sha256': '1' * 64,
        'delivered_work_sha256': '2' * 64, 'delivered_rows': 12,
        'grade_debt': {'A': 2}, 'capability_debt': {'A.IDENTITY': 1},
        'promotion_attempts': 3,
        'whole_school_fresh_retention': {'correct': 7, 'total': 8,
            'source_sha256': '3' * 64, 'rubric_sha256': '4' * 64},
        'learned_transfer': {'correct': 2, 'total': 3,
            'source_sha256': '5' * 64, 'rubric_sha256': '6' * 64},
        'historical_policies': ['bounded debt cadence 4:1'],
    }


class AtlasEvidenceTests(unittest.TestCase):
    def test_expanded_readout_separates_provenance_work_debt_and_scores(self):
        value = receipt()
        value['evidence'] = evidence()
        before = copy.deepcopy(value)
        view = board()
        ingest(view, {'event': 'BAMF_OPERATOR_STATUS_OBSERVED', 'receipt': value})
        view.atlas_expanded = True
        rendered = view.render(width=340, height=90)
        for literal in (
            'candidate ' + 'f' * 64, 'parent ' + '1' * 64,
            'delivered work ' + '2' * 64, 'delivered rows 12',
            'grade debt A=2', 'capability debt A.IDENTITY=1',
            'promotion attempts 3', 'whole-school fresh retention 7/8',
            'learned transfer 2/3', 'retention source ' + '3' * 64,
            'retention rubric ' + '4' * 64, 'transfer source ' + '5' * 64,
            'transfer rubric ' + '6' * 64,
            'historical policy (lineage only) bounded debt cadence 4:1',
            'eligible 8 | source-held 3 | uncovered 2',
        ):
            with self.subTest(literal=literal):
                self.assertIn(literal, rendered)
        self.assertEqual(value, before)
        self.assertNotIn('debt NOT MEASURED', rendered)
        self.assertNotIn('transfer NOT MEASURED', rendered)
        self.assertIn('perfect mastery NOT MEASURED', rendered)

    def test_absent_empty_and_zero_measurements_remain_distinct(self):
        missing = '\n'.join(render_evidence(parse_evidence(None)))
        self.assertIn('grade debt NOT MEASURED', missing)
        self.assertIn('promotion attempts NOT MEASURED', missing)
        value = {'grade_debt': {}, 'capability_debt': {}, 'promotion_attempts': 0,
                 'delivered_rows': 0,
                 'learned_transfer': {**evidence()['learned_transfer'], 'correct': 0, 'total': 0}}
        rendered = '\n'.join(render_evidence(parse_evidence(value)))
        self.assertIn('grade debt none', rendered)
        self.assertIn('capability debt none', rendered)
        self.assertIn('promotion attempts 0', rendered)
        self.assertIn('delivered rows 0', rendered)
        self.assertIn('learned transfer NOT MEASURED', rendered)
        self.assertNotIn('nan', rendered.lower())

    def test_mapping_is_detached_from_mutable_input(self):
        value = evidence()
        frozen = parse_evidence(value)
        value['grade_debt']['A'] = 99
        value['learned_transfer']['correct'] = 0
        value['historical_policies'].append('changed')
        rendered = '\n'.join(render_evidence(frozen))
        self.assertIn('grade debt A=2', rendered)
        self.assertIn('learned transfer 2/3', rendered)
        self.assertNotIn('changed', rendered)

    def test_bad_evidence_cannot_replace_previous_view(self):
        view = board()
        ingest(view, {'event': 'BAMF_OPERATOR_STATUS_OBSERVED', 'receipt': receipt()})
        before = view.bamf_operator_view
        variants = [[], {'unknown': 1}, {'delivered_rows': True},
                    {'grade_debt': {'A': -1}}, {'grade_debt': {chr(0xD800): 0}},
                    {'candidate_sha256': 'bad'}, {'promotion_attempts': float('nan')},
                    {'historical_policies': ['bad\npolicy']},
                    {'historical_policies': ['same', 'same']},
                    {'learned_transfer': {**evidence()['learned_transfer'], 'correct': 4}},
                    {'learned_transfer': {**evidence()['learned_transfer'], 'extra': 1}}]
        for bad in variants:
            value = receipt()
            value['evidence'] = bad
            with self.subTest(value=bad):
                with self.assertRaises(BilqisError) as caught:
                    ingest(view, {'event': 'BAMF_OPERATOR_STATUS_OBSERVED', 'receipt': value})
                self.assertIs(caught.exception.spec, SCHOOL.BAMF_OPERATOR.INVALID)
                self.assertIs(view.bamf_operator_view, before)

    def test_grade_labels_do_not_change_coverage_or_policy(self):
        panels = []
        for grade in ('A', 'Z'):
            value = receipt()
            value['evidence'] = evidence()
            value['evidence']['grade_debt'] = {grade: 2}
            value['evidence']['capability_debt'] = {grade + '.IDENTITY': 1}
            view = board()
            ingest(view, {'event': 'BAMF_OPERATOR_STATUS_OBSERVED', 'receipt': value})
            view.atlas_expanded = True
            rendered = view.render(width=340, height=90)
            panels.append(rendered.replace(grade + '.IDENTITY', 'TARGET').replace(
                'grade debt ' + grade + '=2', 'grade debt G=2'))
        self.assertEqual(panels[0], panels[1])

    def test_printable_unicode_and_partial_debt_measurement(self):
        value = receipt()
        value['evidence'] = {'grade_debt': {'語義': 0},
                             'historical_policies': ['A.ÉGALITÉ']}
        view = board()
        ingest(view, {'event': 'BAMF_OPERATOR_STATUS_OBSERVED', 'receipt': value})
        view.atlas_expanded = True
        rendered = view.render(width=340, height=90)
        self.assertIn('grade debt measured (details)', rendered)
        self.assertIn('capability debt NOT MEASURED', rendered)
        self.assertEqual(view.bamf_operator_view.evidence.grade_debt, (('語義', 0),))
        self.assertIn(r'grade debt \u8a9e\u7fa9=0', rendered)
        self.assertIn(r'historical policy (lineage only) A.\u00c9GALIT\u00c9', rendered)

    def test_control_and_oversized_policy_names_reject(self):
        for text in ('', 'x' * 97, 'bad\npolicy', chr(127), chr(0x85),
                     chr(0x2028), chr(0xD800)):
            for value in ({'historical_policies': [text]}, {'grade_debt': {text: 0}}):
                with self.subTest(value=value), self.assertRaises(BilqisError):
                    parse_evidence(value)
