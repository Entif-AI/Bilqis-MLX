from dataclasses import replace
import hashlib
import unittest

from bilqis_mlx.curriculum.scheduler import (
    Assessment, Score, adopt_appended_program, adopt_revised_program,
    assess, start_new, visit,
)
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.executable_release import compile_successor_profile_release
from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.factory.tests.test_executable_consumers import _profile
from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_boolean_course
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.profiles.school import boolean_kernel_profile
from bilqis_mlx.trainer import _profile_transition


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
        state = assess(program, state, snapshot)
        while state.stage == "PROMOTION_SWEEP":
            state = visit(program, state, state.queue[0], student)
            state = assess(program, state, snapshot)
        return program, state

    def test_debt_does_not_retake_instruction_from_frontier(self):
        from bilqis_mlx.curriculum.scheduler import (
            _instructional_pool, _resume_ordinary_spiral, weakest_three,
        )
        program, state = self._finish_a(self.full)
        # A prior-grade failure remains scored while the admitted frontier
        # has outstanding instruction; it must not win the lesson queue.
        frontier = program.grades[-1].id
        caps = tuple(c.id for g in program.grades for c in g.capabilities)
        scores = {cap: Score(0, 12) for cap in caps}
        state = replace(state, grade_index=len(state.active_grades)-1,
                        carried_mastery_debt=caps)
        pool = tuple(scores)
        due = _instructional_pool(program, state, scores, pool)
        self.assertTrue(due)
        self.assertTrue(all(cap.startswith(frontier + ".") for cap in due))
        self.assertEqual(set(weakest_three(scores, due)), set(sorted(due)[:3]))
        snapshot = Assessment(state.current_student.sha256,
                              state.current_student.optimizer_step,
                              program.digest(), program.grades[-1].assessment_sha256,
                              scores, evaluation_id="frontier-debt-test")
        advanced = _resume_ordinary_spiral(program, state, snapshot)
        self.assertEqual(advanced.grade, frontier)
        self.assertTrue(all(c.startswith(frontier + ".") for c in advanced.queue))
        self.assertEqual(advanced.carried_mastery_debt, caps)

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

    def test_profile_successor_appends_grade_without_release_dispatch(self):
        curriculum, bindings = from_legacy_course(self.course)
        answers = _boolean_answers()
        a_only = compile_executable_factory_release(
            curriculum, bindings,
            CurriculumProfile(
                "a-only",
                grades=(GradeProfile("B", enabled_capabilities=()),)),
            self.providers, answers,
            source_root=None, graph=self.graph,
            verification_seed=71, legacy_course=self.course)
        a_program, state = self._finish_a(a_only)
        self.assertEqual(state.stage, "AWAITING_NEXT_GRADE")

        successor = compile_successor_profile_release(
            a_only,
            boolean_kernel_profile(),
            self.providers,
            answers,
            source_root=None,
            graph=self.graph,
            verification_seed=73,
            legacy_course=self.course)
        b_program = schedule_program_from_executable_release(successor)
        adopted = adopt_appended_program(a_program, b_program, state)

        self.assertEqual(successor.curriculum.digest(), a_only.curriculum.digest())
        self.assertEqual(
            successor.source_bindings.digest(),
            a_only.source_bindings.digest())
        self.assertEqual(successor.transition.added_grades, ("B",))
        self.assertEqual(successor.transition.semantic_geometry, "UNCHANGED")
        self.assertEqual(adopted.grade, "B")
        self.assertEqual(adopted.queue, ("B.AND", "B.IFF"))

    def test_profile_successor_appends_after_stable_mean_with_mastery_debt(self):
        curriculum, bindings = from_legacy_course(self.course)
        answers = _boolean_answers()
        a_only = compile_executable_factory_release(
            curriculum, bindings,
            CurriculumProfile(
                "a-only-debt",
                grades=(GradeProfile("B", enabled_capabilities=()),)),
            self.providers, answers,
            source_root=None, graph=self.graph,
            verification_seed=79, legacy_course=self.course)
        a_program = schedule_program_from_executable_release(a_only)
        student = _checkpoint()
        state = start_new(a_program, student)
        for capability in tuple(state.queue):
            state = visit(a_program, state, capability, student)
        grade = a_program.grades[0]
        scores = {
            capability.id: Score(capability.exam_item_count,
                                 capability.exam_item_count)
            for capability in grade.capabilities
        }
        weak = grade.capabilities[0]
        scores[weak.id] = Score(weak.exam_item_count // 2,
                                weak.exam_item_count)
        exam = Assessment(
            student.sha256, student.optimizer_step, a_program.digest(),
            grade.assessment_sha256, scores,
            evaluation_id="stable-mean-debt-boundary")
        state = assess(a_program, state, exam)
        while state.stage == "PROMOTION_SWEEP":
            state = visit(a_program, state, state.queue[0], student)
            state = assess(a_program, state, exam)
        self.assertEqual(state.stage, "AWAITING_NEXT_GRADE_WITH_DEBT")

        successor = compile_successor_profile_release(
            a_only, boolean_kernel_profile(), self.providers, answers,
            source_root=None, graph=self.graph,
            verification_seed=83, legacy_course=self.course)
        b_program = schedule_program_from_executable_release(successor)
        adopted, revised_grade, appended = _profile_transition(
            a_program, b_program, state)

        self.assertTrue(appended)
        self.assertIsNone(revised_grade)
        self.assertEqual(adopted.grade, "B")
        self.assertIn(weak.id, adopted.carried_mastery_debt)
        self.assertNotIn("A", adopted.champions)

    def test_profile_revision_rebinds_active_grade_without_release_dispatch(self):
        program = schedule_program_from_executable_release(self.full)
        student = _checkpoint()
        state = start_new(program, student)
        state = replace(
            state,
            grade_index=1,
            stage="MAIN",
            queue=program.grades[1].teaching_stages[0],
            introduction_stage=0,
        )
        revised_program = schedule_program_from_executable_release(self.reduced)
        revised, grade = adopt_revised_program(
            program, revised_program, state)

        self.assertEqual(grade, "B")
        self.assertEqual(revised.grade, "B")
        self.assertEqual(revised.queue, ("B.AND", "B.IFF"))
        self.assertEqual(revised.introduction_stage, 0)
        self.assertEqual(revised.course_digest, revised_program.digest())


if __name__ == "__main__":
    unittest.main()
