"""Disposable matrix geometry tests; no live model or optimizer writes."""
import unittest

from bilqis_mlx.matrix_strain import references, score


class MatrixStrainTests(unittest.TestCase):
    def test_reference_follows_only_the_persisted_comparable_peak(self):
        first = {"filename": "bundles/epoch", "sha256": "origin"}
        best = {"filename": "bundles/best", "sha256": "best", "optimizer_step": 30}
        tied = {"filename": "bundles/tied", "sha256": "tied", "optimizer_step": 40}
        state = {"curriculum_parent": first,
                 "last_exam": {"whole_student_retention": {"scope_sha256": "scope"}},
                 "whole_student_peaks": [{"scope_sha256": "scope", "checkpoint": best}],
                 "grade_soups": {"A": {"filename": "soups/other"}},
                 "last_local_candidate": tied}
        self.assertEqual(references(None, state), ((first, best), None))
        state["last_exam"]["whole_student_retention"]["scope_sha256"] = "changed"
        self.assertEqual(references(None, state)[1], "MISSING_COMPARABLE_REFERENCE")

    def test_matrix_motion_and_shape_guard(self):
        import mlx.core as mx
        p = {"layer": mx.array([1.0, 2.0], dtype=mx.float32)}
        c = {"layer": mx.array([2.0, 3.0], dtype=mx.float32)}
        start = {"layer": mx.array([0.0, 0.0], dtype=mx.float32)}
        best = {"layer": mx.array([3.0, 3.0], dtype=mx.float32)}
        result = score(mx, p, c, start, best)
        self.assertAlmostEqual(result["matrices"]["layer"]["delta_start_mean_sq"], 4.0)
        self.assertAlmostEqual(result["matrices"]["layer"]["delta_best_mean_sq"], -2.0)
        self.assertAlmostEqual(result["matrices"]["layer"]["candidate_shift_mean_sq"], 1.0)
        with self.assertRaisesRegex(ValueError, "SHAPE"):
            score(mx, p, c, {"layer": mx.zeros((3,), dtype=mx.float32)}, best)


if __name__ == "__main__":
    unittest.main()
