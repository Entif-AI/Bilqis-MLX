import unittest
from types import SimpleNamespace

from bilqis_mlx.runtime import candidate_evidence, checkpoints, visits


class RetentionFrontierTests(unittest.TestCase):
    def test_retention_support_covers_every_active_grade_surface(self):
        admitted = (
            "A.IDENTITY", "A.MAPS", "B.AND", "B.IFF", "C.COUNT",
        )

        self.assertEqual(
            candidate_evidence._retention_support_capabilities(
                admitted, ("A", "B"), "B.AND"),
            ("A.IDENTITY", "A.MAPS", "B.IFF"),
        )
        self.assertEqual(
            candidate_evidence._retention_support_capabilities(
                admitted, ("A", "B"), "A.IDENTITY"),
            ("A.MAPS", "B.AND", "B.IFF"),
        )

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


if __name__ == "__main__":
    unittest.main()
