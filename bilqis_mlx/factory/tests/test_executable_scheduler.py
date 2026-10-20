from dataclasses import replace
import hashlib
import unittest

from bilqis_mlx.curriculum.scheduler import (
    Assessment, Score, assess, start_new, visit,
)
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.factory.tests.test_executable_consumers import _profile
from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_boolean_course
from bilqis_mlx.learning.champions import Checkpoint


def _checkpoint():
    return Checkpoint(
        hashlib.sha256(b"schedule-program-student").hexdigest(),
        "bundles/schedule-program-student",
        7,
        True,
    )


class ExecutableSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.course, self.providers = _synthetic_boolean_course()
        curriculum, bindings = from_legacy_course(self.course)
        self.graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
                "cogal.operator.NOT",
                "cogal.operator.AND",
                "cogal.operator.OR",
                "cogal.operator.XOR",
                "cogal.operator.IMPLIES",
                "cogal.operator.IFF",
            ],
        }
        answers = _boolean_answers()
        self.full = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(),
            self.providers, answers, source_root=None, graph=self.graph,
            verification_seed=61, legacy_course=self.course)
        self.reduced = compile_executable_factory_release(
            curriculum, bindings, _profile(),
            self.providers, answers, source_root=None, graph=self.graph,
            verification_seed=61, legacy_course=self.course,
            predecessor=self.full)

    def _finish_a(self, release):
        program = schedule_program_from_executable_release(release)
        student = _checkpoint()
        state = start_new(program, student)
        for capability in tuple(state.queue):
            state = visit(program, state, capability, student)
        self.assertEqual(state.stage, "ASSESS_MAIN")
        grade = program.grades[0]
        snapshot = Assessment(
            student.sha256,
            student.optimizer_step,
            program.digest(),
            grade.assessment_sha256,
            {
                capability.id: Score(capability.exam_item_count,
                                     capability.exam_item_count)
                for capability in grade.capabilities
            },
            evaluation_id="v2-scheduler-fixture",
        )
        return program, assess(program, state, snapshot)

    def test_same_scheduler_obeys_full_and_reduced_v2_rosters(self):
        full_program, full_state = self._finish_a(self.full)
        reduced_program, reduced_state = self._finish_a(self.reduced)

        self.assertEqual((full_state.grade, reduced_state.grade), ("B", "B"))
        self.assertEqual(
            full_program.grades[1].capabilities[0].id,
            "B.NOT")
        self.assertEqual(
            tuple(item.id for item in reduced_program.grades[1].capabilities),
            ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"))
        self.assertEqual(
            reduced_state.queue,
            ("B.AND", "B.IFF"))
        self.assertEqual(
            reduced_program.grades[1].teaching_stages,
            (("B.AND", "B.IFF"), ("B.COMPOSITE",), ("B.IDBOOLOPS",)))

    def test_b_only_profile_change_preserves_a_scheduler_measurement_identity(self):
        full_program = schedule_program_from_executable_release(self.full)
        reduced_program = schedule_program_from_executable_release(self.reduced)

        self.assertNotEqual(full_program.digest(), reduced_program.digest())
        self.assertEqual(
            full_program.grades[0],
            reduced_program.grades[0])
        self.assertEqual(
            full_program.grades[0].assessment_sha256,
            reduced_program.grades[0].assessment_sha256)

    def test_schedule_program_is_not_the_whole_release_identity(self):
        program = schedule_program_from_executable_release(self.reduced)
        self.assertNotEqual(program.digest(), self.reduced.release_sha256)
        self.assertNotEqual(
            program.digest(),
            self.reduced.execution_plan.projection_digests.source)

    def test_disabled_future_grade_is_not_terminal_program(self):
        curriculum, bindings = from_legacy_course(self.course)
        a_only = compile_executable_factory_release(
            curriculum, bindings,
            CurriculumProfile(
                "a-only",
                grades=(GradeProfile("B", enabled_capabilities=()),)),
            self.providers, _boolean_answers(),
            source_root=None, graph=self.graph,
            verification_seed=67, legacy_course=self.course)
        program = schedule_program_from_executable_release(a_only)

        self.assertEqual(
            tuple(grade.id for grade in program.grades),
            ("A",))
        self.assertFalse(program.program_complete)


if __name__ == "__main__":
    unittest.main()
