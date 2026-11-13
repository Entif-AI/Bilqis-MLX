"""Mature debt."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, decide, rows,
)


class MatureDebtTests(CausalTeacherExperimentTests):
    def test_mature_debt_budget_blocks_only_new_loss_beyond_hard_limit(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.NOT": {"before": 10, "after": 10, "total": 12},
        }
        frontier = {
            "status": "MEASURED", "cohort_sha256": "a" * 64,
            "rows": 144, "before_correct": 120, "after_correct": 121,
            "regressions": [{"id": "a-loss", "capability": "A.MAPS"}],
            "repaired": [
                {"id": "b-gain-1", "capability": "B.IFF"},
                {"id": "b-gain-2", "capability": "B.IFF"},
            ],
            "grades": {
                "A": {"before": 58, "after": 57, "total": 72,
                      "net_correct_delta": -1},
                "B": {"before": 62, "after": 64, "total": 72,
                      "net_correct_delta": 2},
            },
        }
        common = dict(
            active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.NOT"}, settings=Settings(),
            mature_grades=frozenset({"A"}),
            same_grade_capabilities=("B.IFF", "B.NOT"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 62, "after": 64, "total": 72,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay=frontier,
            protected_frontier_grade="B",
        )

        improving = dict(common)
        improving["fixed_frontier_replay"] = {
            **frontier,
            "grades": {
                "A": {"before": 58, "after": 60, "total": 72,
                      "net_correct_delta": 2},
                "B": {"before": 62, "after": 63, "total": 72,
                      "net_correct_delta": 1},
            },
            "before_correct": 120, "after_correct": 123,
            "regressions": [], "repaired": [],
        }
        within_budget = decide(
            paired, mature_grade_debt={"A": 4}, **improving)
        self.assertEqual(within_budget["decision"], "PROVISIONAL")
        self.assertEqual(within_budget["projected_mature_grade_debt"], {"A": 2})

        blocked = decide(
            paired, mature_grade_debt={"A": 4},
            plasticity_escape={"active": True}, **common)
        self.assertEqual(blocked["decision"], "REJECT")
        self.assertEqual(blocked["reason"], "MATURE_GRADE_DEBT_LIMIT")
        self.assertEqual(blocked["projected_mature_grade_debt"], {"A": 5})

    def test_mature_grades_never_inherit_developmental_loss_budget(self):
        rows = {
            "C.ADD": {"before": 3, "after": 4, "total": 6},
            "B.XOR": {"before": 6, "after": 4, "total": 6},
            "C.SUB": {"before": 6, "after": 4, "total": 6},
        }
        settings = Settings(probe_each=6, mature_max_loss=1,
                            introduction_extra_loss=2)
        result = decide(rows, active_capability="C.ADD", phase="MAIN",
                        protected={"B.XOR", "C.SUB"}, settings=settings,
                        mature_grades=frozenset({"A", "B"}))
        self.assertEqual(result["local_correct_delta"], 1)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "PROTECTED_CAPABILITY_REGRESSION")
        self.assertEqual(result["exceeded"], {"B.XOR": 2})
        self.assertEqual(result["protected_tolerances"], {"B.XOR": 1, "C.SUB": 3})
        self.assertEqual(result["mature_protected_capabilities"], ["B.XOR"])
        rows["B.XOR"] = {"before": 6, "after": 5, "total": 6}
        passing = decide(rows, active_capability="C.ADD", phase="MAIN",
                         protected={"B.XOR", "C.SUB"}, settings=settings,
                         mature_grades=frozenset({"A", "B"}))
        self.assertEqual(passing["decision"], "REJECT")
        self.assertEqual(passing["reason"], "SAME_GRADE_NET_REGRESSION")
        self.assertEqual(passing["same_grade_net_correct_delta"], -1)
        rows["C.SUB"] = {"before": 6, "after": 6, "total": 6}
        passing = decide(rows, active_capability="C.ADD", phase="MAIN",
                         protected={"B.XOR", "C.SUB"}, settings=settings,
                         mature_grades=frozenset({"A", "B"}))
        self.assertEqual(passing["decision"], "PROVISIONAL")
