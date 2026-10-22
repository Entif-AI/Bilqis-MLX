"""A source/teaching revision need not change the scheduler projection."""
from dataclasses import replace
import unittest

from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.schedule import ScheduleCapability, ScheduleGrade, ScheduleProgram
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.release_adoption import _profile_transition


class TeachingOnlyTransitionTests(unittest.TestCase):
    def setUp(self):
        self.program = ScheduleProgram('a' * 64, (
            ScheduleGrade('D', (ScheduleCapability('D.EVENT_OCCURRENCE', 12),),
                          (('D.EVENT_OCCURRENCE',),), 'b' * 64),), False)
        self.school = start_new(self.program, Checkpoint('c' * 64, 'bundles/fixture', 10, True))

    def test_identical_scheduler_projection_preserves_current_work(self):
        state, revised_grade, appended = _profile_transition(
            self.program, self.program, self.school)
        self.assertIs(state, self.school)
        self.assertIsNone(revised_grade)
        self.assertFalse(appended)

    def test_changed_program_identity_still_requires_a_supported_revision(self):
        changed = replace(self.program, program_digest='d' * 64)
        with self.assertRaisesRegex(ValueError, 'FACTORY_SCHEDULE_REVISION_INVALID'):
            _profile_transition(self.program, changed, self.school)

    def test_source_revision_history_keeps_valid_epoch_custody_records(self):
        from dataclasses import asdict
        from types import SimpleNamespace
        from bilqis_mlx.learning.mentor_epoch import begin_initial_epoch, reference_checkpoints
        from bilqis_mlx.runtime.release_adoption import _profile_championship_state

        epoch = begin_initial_epoch(student=asdict(self.school.current_student),
            introduced_grade='D', source_graph_sha256='e' * 64, frontier={}, soups={})
        receipt = dict(generation=1, semantic_graph_sha256='e' * 64,
            parameter_shapes={'weight': [3, 4]}, mentor_epoch=epoch)
        successor = SimpleNamespace(release_sha256='f' * 64,
            execution_plan=SimpleNamespace(curriculum_sha256='a' * 64))
        identity, updated, history = _profile_championship_state(
            receipt, None, successor, self.school, self.school, appended=False)
        self.assertEqual(history, [epoch])
        self.assertEqual(updated['active_roles'], {})
        self.assertEqual(updated['active_grade_soups'], {})
        for item in (*history, updated):
            self.assertTrue(reference_checkpoints(item))
        unchanged = {**receipt, 'mentor_epoch': updated, 'championship_epoch_history': history}
        _, _, repeated_history = _profile_championship_state(
            unchanged, None, successor, self.school, self.school, appended=False)
        self.assertEqual(repeated_history, history)
