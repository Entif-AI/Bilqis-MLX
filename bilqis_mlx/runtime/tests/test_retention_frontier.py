import unittest
from types import SimpleNamespace

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
