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

    def test_retention_support_schedule_prioritizes_hard_gated_surfaces(self):
        admitted = (
            "A.IDENTITY", "A.MAPS",
            "B.AND", "B.IFF", "B.OR", "B.XOR",
            "C.ADD", "C.COUNT", "C.SUB",
        )

        schedule = candidate_evidence._retention_support_schedule(
            admitted, ("A", "B", "C"), "B.AND",
            steps=8, rotation=0,
            already_preserved=("B.OR", "B.XOR"),
        )

        # B peers are needed for the lesson-grade gate; C is the active
        # progression frontier.  Dedicated fragile preservation already owns
        # OR/XOR, so generic support must not spend another slot on them.
        self.assertEqual(len(schedule), 8)
        self.assertEqual(
            set(schedule),
            {"B.IFF", "C.ADD", "C.COUNT", "C.SUB"},
        )
        self.assertNotIn("A.IDENTITY", schedule)
        self.assertNotIn("A.MAPS", schedule)
        self.assertNotIn("B.OR", schedule)
        self.assertNotIn("B.XOR", schedule)

    def test_retention_support_schedule_rotates_short_budget_across_priority(self):
        admitted = (
            "A.IDENTITY", "A.MAPS", "B.AND", "B.IFF",
            "C.ADD", "C.COUNT", "C.DIV", "C.MUL", "C.SUB",
        )
        first = candidate_evidence._retention_support_schedule(
            admitted, ("A", "B", "C"), "B.AND", steps=4, rotation=0)
        second = candidate_evidence._retention_support_schedule(
            admitted, ("A", "B", "C"), "B.AND", steps=4, rotation=1)

        self.assertEqual(len(first), 4)
        self.assertEqual(len(second), 4)
        self.assertNotEqual(first, second)
        self.assertTrue(set(first + second) <= {
            "B.IFF", "C.ADD", "C.COUNT", "C.DIV", "C.MUL", "C.SUB",
        })

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
