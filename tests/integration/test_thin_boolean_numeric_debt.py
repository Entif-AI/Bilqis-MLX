"""Real-provider A→thin B→C admission preserves unfinished Boolean learning."""
from contextlib import redirect_stdout
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx import trainer
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
from bilqis_mlx.profiles.catalog import numeric_entry_transition
from bilqis_mlx.runtime.exam_execution import _measure_debt_admission_boundary
from bilqis_mlx.runtime.release_adoption import _adopt_executable_profile, _adopt_catalog_profile
from tests.system.test_grade_c_trainer import GradeCTrainerTests, SOURCE


class ThinBooleanNumericDebtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        GradeCTrainerTests.setUpClass()

    def test_unmastered_not_and_do_not_block_designed_counting_entry(self):
        fixture = GradeCTrainerTests()
        mx, params, own = fixture.toy()
        graph = fixture.parent_graph
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            run = Path(directory)
            pointer = trainer._bundle_pointer(run, 'initial', params, own, graph, reserve_gib=0.)
            base = fixture.receipt(start_new(fixture.grade_a, pointer), pointer, params)
            base.update(curriculum_mode=fixture.grade_a.version, last_exam=None)
            base = trainer._persist(run, base)
            base, release, _ = trainer._ensure_executable_release(
                run, base, fixture.grade_a, fixture.grade_a, SOURCE, graph)
            profile = CurriculumProfile('test/not-and', (
                GradeProfile('B', enabled_capabilities=('B.NOT', 'B.AND')),
                GradeProfile('C', enabled_capabilities=()),))

            def imperfect(_mx, _params, rows, *_args):
                first = {}
                for row in rows:
                    first.setdefault(row['capability'], row['id'])
                return {row['id']: ('FALSE' if row['gold'] == 'TRUE' else 'TRUE')
                        if row['id'] == first[row['capability']] else row['gold'] for row in rows}

            with patch('bilqis_mlx.learning.student_ops._predictions', side_effect=imperfect):
                measured = _measure_debt_admission_boundary(
                    mx, run, base, fixture.manifest, fixture.grade_a, SOURCE, params, graph)
                stale = {**measured, 'debt_admission_boundary_exam': {
                    **measured['debt_admission_boundary_exam'], 'optimizer_step': -1}}
                with self.assertRaisesRegex(ValueError, 'DEBT_ADMISSION_REQUIRES_EXACT_COMPLETE_BOUNDARY'):
                    _adopt_executable_profile(run, stale, fixture.grade_a, SOURCE, graph,
                                              profile, allow_mastery_debt=True)
                admitted, course, release, _ = _adopt_executable_profile(
                    run, measured, fixture.grade_a, SOURCE, graph, profile, allow_mastery_debt=True)
                self.assertEqual(admitted['school']['current_student'], base['school']['current_student'])
                self.assertIsNone(admitted['mentor_epoch']['previous_graduate'])
                self.assertFalse(admitted['school']['champions'])
                # Take the complete current exam even though B has not graduated.
                measured = _measure_debt_admission_boundary(
                    mx, run, admitted, fixture.manifest, course, SOURCE, params, graph)
                transition = replace(numeric_entry_transition(
                    release, graph, full_boolean=False, maximum=3), numeric_scope_final_maximum=4)
                _, grown_own, _, numeric, _ = _adopt_catalog_profile(
                    mx, run, measured, fixture.grade_a, SOURCE, graph, params, own,
                    transition, reserve_gib=0., allow_mastery_debt=True)

        self.assertEqual(numeric['school']['active_grades'], ['A', 'B', 'C'])
        self.assertEqual(numeric['school']['queue'], ['C.COUNT'])
        self.assertTrue({'B.NOT', 'B.AND'} <= set(numeric['school']['carried_mastery_debt']))
        self.assertFalse(numeric['school']['champions'])
        self.assertEqual(numeric['numeric_maximum'], 3)
        self.assertEqual(numeric['numeric_scope_final_maximum'], 4)
        self.assertEqual(int(grown_own.state['step'].item()), int(own.state['step'].item()))
        self.assertEqual(numeric['mentor_epoch']['previous_boundary_checkpoint'],
                         admitted['school']['current_student'])
