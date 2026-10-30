"""Scope-qualified whole-student peaks never substitute for a live student."""
import unittest

from bilqis_mlx.learning.whole_student_retention import advance_peaks, MAX_SCOPE_PEAKS


def exam(peaks, correct, step, *, maximum=6, cohort="cohort-a"):
    return advance_peaks(
        peaks, curriculum_mode="staircase", numeric_maximum=maximum,
        rubric_sha256="rubric", cohort_sha256=cohort,
        assessment_scope_sha256="all-admitted-capabilities",
        scores={"A.EDGE": {"correct": correct, "total": 12},
                "C.ADD": {"correct": 12, "total": 12}},
        checkpoint={"filename": f"bundles/step-{step}",
                    "sha256": f"hash-{step}", "optimizer_step": step})


class WholeStudentRetentionTests(unittest.TestCase):
    def test_regression_keeps_complete_best_checkpoint_and_own_adamw_pointer(self):
        peaks, first = exam([], 11, 100)
        peaks, second = exam(peaks, 8, 120)
        self.assertTrue(first["promoted"])
        self.assertFalse(second["promoted"])
        self.assertEqual(second["best_correct"], 23)
        self.assertEqual(peaks[0]["checkpoint"]["optimizer_step"], 100)
        self.assertEqual(peaks[0]["checkpoint"]["filename"], "bundles/step-100")
        self.assertTrue(second["live_student_unchanged"])
        peaks, third = exam(peaks, 12, 140)
        self.assertTrue(third["promoted"])
        self.assertEqual(peaks[0]["checkpoint"]["optimizer_step"], 140)

    def test_expanding_numeric_scope_never_compares_incompatible_examinations(self):
        peaks, _ = exam([], 12, 100, maximum=5)
        peaks, next_scope = exam(peaks, 4, 200, maximum=6)
        self.assertTrue(next_scope["promoted"])
        self.assertEqual(len(peaks), 2)
        self.assertEqual([p["numeric_maximum"] for p in peaks], [5, 6])
        self.assertEqual(peaks[0]["checkpoint"]["optimizer_step"], 100)

    def test_different_cohorts_never_claim_to_be_equivalent(self):
        peaks, _ = exam([], 12, 100)
        peaks, out = exam(peaks, 1, 200, cohort="fresh-exam")
        self.assertTrue(out["promoted"])
        self.assertEqual(len(peaks), 2)

    def test_history_is_bounded_without_dropping_active_scope(self):
        peaks = []
        for step in range(1, MAX_SCOPE_PEAKS + 3):
            peaks, _ = exam(peaks, 10, step, cohort=f"cohort-{step}")
        self.assertEqual(len(peaks), MAX_SCOPE_PEAKS)
        self.assertEqual(peaks[-1]["checkpoint"]["optimizer_step"], MAX_SCOPE_PEAKS + 2)

    def test_incomplete_or_malformed_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SCORE"):
            advance_peaks([], curriculum_mode="staircase", numeric_maximum=6,
                rubric_sha256="rubric", cohort_sha256="cohort", assessment_scope_sha256="all",
                scores={"A.EDGE": {"correct": 13, "total": 12}},
                checkpoint={"filename": "x", "sha256": "y", "optimizer_step": 1})


if __name__ == "__main__":
    unittest.main()
