from bilqis_mlx.runtime.tests._executable_assessment_fixtures import *  # noqa: F403

class ExecutableAssessmentTests(BaseExecutableAssessmentTests):
    def test_routine_scope_is_fresh_at_each_boundary(self):
        receipt = self.receipt()
        scope = (*self.a_scope, "B.AND", "B.IFF")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, first_pointer = _routine_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=3)
            receipt["generation"] += 1
            second, second_pointer = _routine_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=4)
            self.assertNotEqual(first.digest, second.digest)
            self.assertNotEqual(
                first_pointer["cohort_sha256"],
                second_pointer["cohort_sha256"])
            self.assertEqual(first_pointer["policy"], "bilqis.grade-test.fresh-routine/v2")

    def test_promotion_scope_is_fixed_within_attempt_but_rotates_next_epoch(self):
        receipt = self.receipt()
        scope = (*self.a_scope, "B.AND", "B.IFF")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=7)
            receipt["qualification_cohort_v2"] = pointer
            receipt["generation"] += 10
            retry, retry_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=7)
            self.assertEqual(retry.digest, first.digest)
            self.assertEqual(retry_pointer, pointer)

            second, second_pointer = _promotion_executable_cohort(
                root, receipt, self.manifest, self.reduced, self.registry,
                None, self.graph, capabilities=scope, assessment_epoch=8)
            self.assertNotEqual(second.digest, first.digest)
            self.assertNotEqual(second_pointer, pointer)

    def test_fixed_frontier_reads_v2_cohort_without_using_schema_as_rubric(self):
        from bilqis_mlx.fixed_frontier import load_frontier_cohort
        cohort, contract = self.draw(self.full, self.a_scope)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pointer = _persist_executable_cohort(root, self.manifest, contract, cohort)
            self.assertEqual(load_frontier_cohort(root, pointer).digest, cohort.digest)

    def test_scheduler_accepts_verified_exact_scope_when_whole_later_grade_withheld(self):
        from dataclasses import replace
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.curriculum.scheduler import Assessment, Score, start_new, assess_withheld
        from bilqis_mlx.learning.champions import Checkpoint
        cohort, contract = self.draw(self.full, self.a_scope)
        program = schedule_program_from_executable_release(self.full)
        student = Checkpoint("a" * 64, "bundles/fixture", 10, True)
        school = replace(start_new(program, student), grade_index=1,
                         stage="ASSESS_MAIN", queue=(), champions={"A": student},
                         introduction_stage=max(0, len(program.grades[1].teaching_stages)-1))
        exam = Assessment(student.sha256, 10, program.digest(), contract.rubric_sha256,
                          {cap: Score(12, 12) for cap in self.a_scope}, "fixture")
        blocked = tuple(cap.id for cap in program.grades[1].capabilities)
        completed = assess_withheld(program, school, exam, blocked)
        self.assertEqual(completed.stage, "DEFERRED_STAGNATION")
        self.assertNotIn("B", completed.champions)

    def test_quarantine_after_exam_keeps_the_measured_rubric_scope(self):
        from dataclasses import replace
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.curriculum.scheduler import Assessment, Score, start_new, assess_withheld
        from bilqis_mlx.learning.champions import Checkpoint
        program = schedule_program_from_executable_release(self.full)
        student = Checkpoint("a" * 64, "bundles/fixture", 10, True)
        school = replace(start_new(program, student), grade_index=1,
                         stage="ASSESS_RECOVERY_2", queue=(),
                         first_recovery=("B.AND",), champions={"A": student},
                         introduction_stage=max(0, len(program.grades[1].teaching_stages)-1))
        measured_scope = tuple(item.capability_id
                               for item in self.full.execution_plan.capabilities)
        contract = assessment_scope_contract(self.full, measured_scope)
        blocked_after = ("B.IFF",)
        counts = {cap.id: cap.exam_item_count for grade in program.grades
                  for cap in grade.capabilities}
        filtered_scores = {cap: Score(counts[cap] - 1, counts[cap])
                           for cap in measured_scope if cap not in blocked_after}
        filtered = Assessment(student.sha256, student.optimizer_step,
                              program.digest(), contract.rubric_sha256,
                              filtered_scores, "measured-before-quarantine")
        next_state = assess_withheld(
            program, school, filtered, blocked_after,
            rubric_capabilities=measured_scope)
        self.assertNotIn("B", next_state.champions)
        self.assertNotEqual(next_state.stage, "AWAITING_NEXT_GRADE")
        with self.assertRaisesRegex(ValueError, "ASSESSMENT_NOT_GRADE_SEALED_RUBRIC"):
            assess_withheld(program, school, replace(filtered, rubric_digest="f" * 64),
                            blocked_after, rubric_capabilities=measured_scope)
