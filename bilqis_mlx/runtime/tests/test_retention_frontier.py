import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx import fixed_frontier
from bilqis_mlx.runtime import candidate_evidence, checkpoints
from bilqis_mlx.runtime import visits


class RetentionFrontierTests(unittest.TestCase):
    def test_earlier_debt_visit_protects_latest_admitted_frontier_grade(self):
        school = SimpleNamespace(
            grade="B",
            active_grades=("A", "B", "C"),
        )

        self.assertEqual(visits._retention_frontier_grade(school), "C")

    def test_frontier_visit_protects_itself(self):
        school = SimpleNamespace(
            grade="C",
            active_grades=("A", "B", "C"),
        )

        self.assertEqual(visits._retention_frontier_grade(school), "C")

    def test_prepare_visit_feedback_dedupes_identical_champion_rows(self):
        row = {
            "id": "same", "source_id": "source", "capability": "B.COMPOSITE",
            "gold": "FALSE", "tokens": [1, 2, 3], "record": {"task": "evaluate"},
        }
        priority, *_ = visits._prepare_visit_feedback(
            {"teacher_misses": [], "teacher_miss_exposures": {}},
            "B.COMPOSITE", (row, dict(row)), {"same"})
        self.assertEqual(priority, [row])

    def test_prepare_visit_feedback_rejects_conflicting_champion_identity(self):
        first = {
            "id": "same", "source_id": "source", "capability": "B.COMPOSITE",
            "gold": "FALSE", "tokens": [1, 2, 3], "record": {"task": "evaluate"},
        }
        second = {**first, "gold": "TRUE"}
        with self.assertRaisesRegex(
                ValueError, "TEACHER_WEAKNESS_TARGET_IDENTITY_CONFLICT"):
            visits._prepare_visit_feedback(
                {"teacher_misses": [], "teacher_miss_exposures": {}},
                "B.COMPOSITE", (first, second), {"same"})

    def test_retention_frontier_survives_new_last_exam(self):
        anchor = {"cohort_sha256": "a" * 64, "student_sha256": "old"}
        receipt = {
            "retention_frontier_exam": anchor,
            "last_exam": {"cohort_sha256": "b" * 64, "student_sha256": "new"},
        }
        self.assertEqual(fixed_frontier.retention_frontier_exam(receipt), anchor)

    def test_candidate_frontier_uses_anchor_predictions_not_current_parent(self):
        row = {"id": "r1", "capability": "A.IDENTITY", "gold": "TRUE"}
        exam = {
            "cohort_sha256": "a" * 64, "student_sha256": "anchor",
            "optimizer_step": 10,
        }
        school = SimpleNamespace(
            current_student=SimpleNamespace(sha256="current", optimizer_step=20))
        candidate = object()
        parent = object()

        with patch("bilqis_mlx.fixed_frontier.retention_frontier_exam",
                   return_value=exam), \
             patch("bilqis_mlx.fixed_frontier.load_frontier",
                   return_value=((row,), {"r1": "TRUE"})) as load_frontier, \
             patch("bilqis_mlx.learning.student_ops._predictions",
                   return_value={"r1": "TRUE"}) as predictions:
            rows, fixed, frontier, anchor_predictions, candidate_predictions = (
                candidate_evidence._frontier_fixed_evidence(
                    None, None, {}, school, "A.IDENTITY", parent, candidate,
                    {}, (0, 1)))

        self.assertEqual(rows, (row,))
        self.assertEqual(anchor_predictions, {"r1": "TRUE"})
        self.assertEqual(candidate_predictions, {"r1": "TRUE"})
        self.assertEqual(frontier["status"], "MEASURED")
        self.assertEqual(fixed["before"], 1)
        self.assertEqual(fixed["after"], 1)
        self.assertEqual(load_frontier.call_args.args[1], {"last_exam": exam})
        self.assertEqual(predictions.call_count, 1)
        self.assertIs(predictions.call_args.args[1], candidate)

    def test_regression_recovery_preserves_abandoned_terminal_checkpoint(self):
        abandoned = {
            "filename": "bundles/damaged-terminal", "sha256": "d" * 64,
            "optimizer_step": 127056, "model_and_native_adamw": True,
        }
        self.assertEqual(
            checkpoints._regression_recovery_checkpoint({
                "student_regression_recovery": {"abandoned_student": abandoned},
            }),
            abandoned)
