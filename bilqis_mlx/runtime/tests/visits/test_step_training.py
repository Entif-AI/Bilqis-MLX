"""Regression coverage for lesson-methodology evidence at the visit boundary."""
import unittest

from bilqis_mlx.runtime import visits


class VisitMethodologyEvidenceTests(unittest.TestCase):
    def test_target_evidence_excludes_injected_support_and_includes_replayed_misses(self):
        fresh = [
            {"id": "fresh", "capability": "C.DIV"},
        ]
        replayed = {"id": "miss", "capability": "C.DIV"}
        support = {"id": "support", "capability": "A.PARENT"}
        prior = {"id": "prior", "capability": "B.OR"}

        offered, delivered = visits._methodology_lesson_rows(
            "C.DIV", fresh, [replayed], [support, replayed, prior, fresh[0]])

        self.assertEqual([row["id"] for row in offered], ["fresh", "miss"])
        self.assertEqual([row["id"] for row in delivered], ["miss", "fresh"])


if __name__ == "__main__":
    unittest.main()
