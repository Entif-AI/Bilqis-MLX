"""Small, state-observable checks for the next curriculum admission.

This suite is intentionally independent of the ordinary trainer unit-suite.
It cannot establish neural retention. Every test targets a distinct control
that must still work when the curriculum adds another grade.
"""
from dataclasses import replace
import unittest

from bilqis_mlx.champions import Checkpoint
from bilqis_mlx.curriculum import (AnswerFamily, Capability, Course, ExamItem,
                                   Grade, validate, validate_exam_item)
from bilqis_mlx.grade_transition import (next_grade_readiness,
                                          require_complete_cumulative_prior_exam)
from bilqis_mlx.learning_experiment import Settings, decide, selection_credit
from bilqis_mlx.school import (Assessment, Score, start_new, weakest_three,
                               choose_best_whole_student)
from bilqis_mlx.school_telemetry import _candidate_admission_text
from bilqis_mlx.whole_student_retention import advance_peaks


def _course(letters):
    """Synthetic admitted-shape source declarations, never a real new grade."""
    grades = []
    for grade in letters:
        capabilities = []
        for index in range(6):
            name = f"{grade}.{index}"
            predecessor = chr(ord(grade) - 1)
            dependencies = ((f"{predecessor}.0",) if grade != "A" and index == 0
                            else ())
            families = [AnswerFamily("binary", ("FALSE", "TRUE"))]
            if grade == "D":
                families.append(AnswerFamily("integer_0_3", ("0", "1", "2", "3")))
            capabilities.append(Capability(
                name, "synthetic-level", f"repo:fixture/{name}",
                (f"root:{name}",), (f"root:{name}",),
                dependencies, (), tuple(families),
                "fixture:source-valid-example", "fixture:independent-gold"))
        grades.append(Grade(grade, tuple(capabilities), grade.lower() * 64,
                            tuple((cap.id, 2) for cap in capabilities)))
    last = letters[-1].lower() * 64
    return Course(tuple(grades), "synthetic-admission/" + "".join(letters),
                  "a" * 64, last)


def _state_and_exam(course):
    pointer = Checkpoint("f" * 64, "fixture-bundle", 42, True)
    state = start_new(course, pointer)
    state = replace(state, grade_index=len(course.grades) - 1,
                    stage="AWAITING_NEXT_GRADE", queue=(),
                    champions={g.id: pointer for g in course.grades},
                    latest_rubric_digest=course.assessment_manifest_sha256)
    exam = Assessment(pointer.sha256, pointer.optimizer_step, course.digest(),
                      course.assessment_manifest_sha256,
                      {cap.id: Score(2, 2) for grade in course.grades
                       for cap in grade.capabilities}, "one-intact-model-exam")
    return pointer, state, exam


def _paired(target_gain, *, protected_loss=0):
    return {
        "C.ADD": {"before": 3, "after": 3 + target_gain, "total": 6},
        "A.IDENTITY": {"before": 6, "after": 6 - protected_loss, "total": 6},
    }


class AdmissionInheritanceChecks(unittest.TestCase):
    def test_target_requires_strictly_positive_paired_gain(self):
        for gain in (-1, 0, 1):
            with self.subTest(gain=gain):
                decision = decide(
                    _paired(gain), active_capability="C.ADD", phase="MAIN",
                    protected={"A.IDENTITY"}, settings=Settings(),
                    mature_grades=frozenset({"A"}))
                self.assertEqual(
                    decision["decision"], "PROVISIONAL" if gain == 1 else "REJECT")
                self.assertEqual(decision["local_correct_delta"], gain)

    def test_mature_prior_grade_is_protected_in_all_scheduling_phases(self):
        for phase in ("MAIN", "RECOVERY_1", "RECOVERY_2"):
            with self.subTest(phase=phase):
                decision = decide(
                    _paired(1, protected_loss=2),
                    active_capability="C.ADD", phase=phase,
                    protected={"A.IDENTITY"}, settings=Settings(),
                    mature_grades=frozenset({"A"}))
                self.assertEqual(decision["decision"], "REJECT")
                self.assertEqual(decision["reason"],
                                 "PROTECTED_CAPABILITY_REGRESSION")
                self.assertEqual(decision["protected_tolerances"]["A.IDENTITY"], 1)

    def test_fixed_or_xor_replay_rejects_newly_wrong_prior_answer(self):
        decision = decide(
            _paired(1), active_capability="C.ADD", phase="MAIN",
            protected={"A.IDENTITY"}, settings=Settings(),
            mature_grades=frozenset({"A", "B"}),
            fragile_replay={"status": "MEASURED",
                            "regressions": ["B.XOR/fixture-paired-row"]})
        self.assertEqual(decision["decision"], "REJECT")
        self.assertEqual(decision["reason"], "FRAGILE_COMPOSITION_REPLAY_REGRESSION")

    def test_rejected_trial_gives_non_neutral_primary_teacher_credit(self):
        self.assertEqual(selection_credit(
            0.0, {"decision": "REJECT"},
            {"teacher_context_reward": -0.05}), -0.05)
        with self.assertRaisesRegex(ValueError, "INVALID_SELECTION_CREDIT"):
            selection_credit(0.0, {"decision": "REJECT"},
                             {"teacher_context_reward": 0.0})

    def test_cumulative_weakest_never_pads_with_perfect_capabilities(self):
        scores = {
            "A.0": Score(2, 2), "A.1": Score(1, 2),
            "B.0": Score(2, 2), "B.1": Score(0, 2),
            "C.0": Score(2, 2), "C.1": Score(2, 2),
            "D.0": Score(1, 2),
        }
        pool = tuple(scores)
        self.assertEqual(weakest_three(scores, pool),
                         ("B.1", "A.1", "D.0"))
        self.assertEqual(weakest_three(
            {**scores, "D.0": Score(2, 2)}, pool),
            ("B.1", "A.1"))

    def test_whole_student_reference_ratchets_only_strictly_within_scope(self):
        base = {
            "curriculum_mode": "synthetic-staircase",
            "numeric_maximum": 6, "rubric_sha256": "rubric-a",
            "cohort_sha256": "cohort-a",
            "assessment_scope_sha256": "A-B-C",
        }
        def read(peaks, a, step, **changes):
            scope = {**base, **changes}
            return advance_peaks(
                peaks, **scope,
                scores={"A.0": {"correct": a, "total": 12},
                        "C.0": {"correct": 11, "total": 12}},
                checkpoint={"filename": f"whole-bundle-{step}",
                            "sha256": f"student-{step}",
                            "optimizer_step": step})
        peaks, high = read([], 10, 10)
        peaks, tied = read(peaks, 10, 20)
        self.assertTrue(high["promoted"])
        self.assertFalse(tied["promoted"])
        self.assertEqual(tied["best_optimizer_step"], 10)
        peaks, better = read(peaks, 11, 30)
        self.assertTrue(better["promoted"])
        self.assertEqual(better["best_optimizer_step"], 30)
        peaks, changed = read(peaks, 2, 40, numeric_maximum=7)
        self.assertTrue(changed["promoted"])
        self.assertEqual(len(peaks), 2)
        self.assertEqual(peaks[0]["checkpoint"]["optimizer_step"], 30)

    def test_one_intact_checkpoint_not_sum_of_historical_champions(self):
        course = _course("ABC")
        pointer, _, exam = _state_and_exam(course)
        require_complete_cumulative_prior_exam(course, _state_and_exam(course)[1], exam)
        other = Checkpoint("e" * 64, "different-student-bundle", 41, True)
        with self.assertRaisesRegex(ValueError, "SAME_CHECKPOINT"):
            choose_best_whole_student(
                course, ((pointer, exam),
                         (other, replace(exam, optimizer_step=42))),
                ("A", "B", "C"))

    def test_future_grade_D_without_release_evidence_fails_closed(self):
        previous, successor = _course("ABC"), _course("ABCD")
        validate(successor)
        pointer, state, exam = _state_and_exam(previous)
        before = (state, pointer, exam)
        result = next_grade_readiness(
            previous, successor, state, exam,
            parent_release=previous.version, candidate_package=None,
            candidate_semantic_release=None, semantic_release="synthetic-D/v1",
            approved_release_receipt=None, source_operations={})
        self.assertEqual(result["planned_grade"], "D")
        self.assertEqual(len(result["planned_capabilities"]), 6)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("GRADE_ADMISSION_SOURCE_CANDIDATE_MISSING", result["blockers"])
        self.assertFalse(result["training_authorized"])
        self.assertEqual(result["actual_neural_updates"], 0)
        self.assertEqual((state, pointer, exam), before)

    def test_future_D_numeric_answer_preserves_type_and_independent_oracle(self):
        candidate = _course("ABCD")
        item = ExamItem("D.0", "integer_0_3", "2",
                        ("root:D.0",), (), "fixture:independent-gold",
                        "synthetic-D-typed-answer")
        validate_exam_item(candidate, "D", item,
                           mastered_grade_ids=("A", "B", "C"))
        with self.assertRaisesRegex(ValueError, "ANSWER"):
            validate_exam_item(candidate, "D", replace(item, answer_kind="binary"),
                               mastered_grade_ids=("A", "B", "C"))
        with self.assertRaisesRegex(ValueError, "ORACLE"):
            validate_exam_item(candidate, "D", replace(item, oracle_ref="invented"),
                               mastered_grade_ids=("A", "B", "C"))

    def test_rejected_visit_is_reported_as_rejection_not_training_commit(self):
        rejected = _candidate_admission_text({
            "candidate_retention": {"decision": "REJECT",
                                    "reason": "NO_MEASURABLE_TARGET_GAIN"},
            "retained_optimizer_updates": 0,
            "teacher_decision": {},
        })
        retained = _candidate_admission_text({
            "candidate_retention": {"decision": "PROVISIONAL"},
            "retained_optimizer_updates": 2,
            "teacher_decision": {},
        })
        self.assertEqual(rejected, "REJECT NO TARGET GAIN")
        self.assertEqual(retained, "RETAIN 2")


if __name__ == "__main__":
    unittest.main()
