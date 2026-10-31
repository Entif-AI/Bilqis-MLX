"""Candidate admission."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, decide, missing_grade_capabilities,
)


class CandidateAdmission1Tests(CausalTeacherExperimentTests):
    def test_missing_only_grade_completion_uses_checkpoint_existing_scores(self):
        grade = ("B.AND", "B.IFF", "B.NOT", "B.XOR")
        self.assertEqual(
            missing_grade_capabilities(grade, {"B.XOR": {"before": 8,
                                                       "after": 9, "total": 12},
                                               "B.AND": {"before": 6,
                                                       "after": 6, "total": 12}}),
            ("B.IFF", "B.NOT"))
        self.assertEqual(missing_grade_capabilities(
            grade, {cap: {"before": 0, "after": 0, "total": 1}
                    for cap in grade}), ())

    def test_actual_b_xor_gain_does_not_justify_larger_b_grade_loss(self):
        # Reproduces committed experiment generation 11566: B.XOR +1,
        # B.IFF -1, B.IMPLIES -1, 16 steps incorrectly retained.
        paired = {
            "B.AND": {"before": 6, "after": 6, "total": 6},
            "B.IFF": {"before": 6, "after": 5, "total": 6},
            "B.IMPLIES": {"before": 6, "after": 5, "total": 6},
            "B.NOT": {"before": 6, "after": 6, "total": 6},
            "B.OR": {"before": 6, "after": 6, "total": 6},
            "B.XOR": {"before": 7, "after": 8, "total": 12},
        }
        result = decide(paired, active_capability="B.XOR", phase="RECOVERY_2",
                        protected=set(paired) - {"B.XOR"}, settings=Settings(),
                        mature_grades=frozenset({"A", "B"}),
                        same_grade_capabilities=tuple(paired))
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "SAME_GRADE_NET_REGRESSION")
        self.assertEqual(result["local_correct_delta"], 1)
        self.assertEqual(result["same_grade_net_correct_delta"], -1)

    def test_target_only_gain_with_same_grade_tie_is_not_progress(self):
        paired = {
            "B.XOR": {"before": 7, "after": 8, "total": 12},
            "B.IFF": {"before": 6, "after": 5, "total": 6},
        }
        result = decide(paired, active_capability="B.XOR", phase="RECOVERY_1",
                        protected={"B.IFF"}, settings=Settings(),
                        same_grade_capabilities=("B.IFF", "B.XOR"))
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "NO_POSITIVE_SAME_GRADE_GAIN")
        self.assertEqual(result["same_grade_net_correct_delta"], 0)

    def test_positive_fresh_grade_probe_cannot_hide_fixed_cohort_regression(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.AND": {"before": 6, "after": 6, "total": 6},
        }
        result = decide(
            paired, active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.AND"}, settings=Settings(),
            same_grade_capabilities=("B.AND", "B.IFF"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 59, "after": 56, "total": 72,
                                "cohort_sha256": "a" * 64})
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "FIXED_GRADE_COHORT_REGRESSION")
        self.assertEqual(result["fixed_grade_replay"]["net_correct_delta"], -3)

    def test_fixed_frontier_allows_item_trade_when_grade_improves_and_school_ties(self):
        paired = {
            "C.DIV": {"before": 18, "after": 19, "total": 21},
            "C.MUL": {"before": 21, "after": 21, "total": 21},
        }
        frontier = {
            "status": "MEASURED",
            "cohort_sha256": "a" * 64,
            "rows": 291,
            "before_correct": 287,
            "after_correct": 287,
            "regressions": [{"id": "new_div_error", "capability": "C.DIV"}],
            "repaired": [{"id": "old_div_error", "capability": "C.DIV"}],
            "grades": {
                "C": {"before": 146, "after": 147, "total": 147,
                      "net_correct_delta": 1},
                "B": {"before": 69, "after": 68, "total": 72,
                      "net_correct_delta": -1},
            },
        }
        result = decide(
            paired, active_capability="C.DIV", phase="RECOVERY_1",
            protected={"C.MUL"}, settings=Settings(),
            same_grade_capabilities=("C.DIV", "C.MUL"),
            fixed_grade_replay={"status": "MEASURED", "grade": "C",
                                "before": 146, "after": 147, "total": 147,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay=frontier)
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")
        self.assertEqual(result["fixed_frontier_replay"]["regressions"],
                         frontier["regressions"])
        self.assertEqual(result["fixed_whole_school_net_correct_delta"], 0)

    def test_fixed_frontier_rejects_when_school_loses_more_than_grade_gains(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.NOT": {"before": 10, "after": 10, "total": 12},
        }
        result = decide(
            paired, active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.NOT"}, settings=Settings(),
            same_grade_capabilities=("B.IFF", "B.NOT"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 68, "after": 69, "total": 72,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay={
                "status": "MEASURED", "cohort_sha256": "a" * 64,
                "rows": 291, "before_correct": 287, "after_correct": 286,
                "regressions": [
                    {"id": "c1", "capability": "C.DIV"},
                    {"id": "c2", "capability": "C.DIV"},
                ],
                "repaired": [{"id": "b1", "capability": "B.IFF"}],
                "grades": {
                    "B": {"before": 68, "after": 69, "total": 72,
                          "net_correct_delta": 1},
                    "C": {"before": 147, "after": 145, "total": 147,
                          "net_correct_delta": -2},
                },
            })
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "WHOLE_SCHOOL_NET_REGRESSION")
        self.assertEqual(result["fixed_whole_school_net_correct_delta"], -1)

    def test_fixed_frontier_allows_other_grade_repair_when_current_grade_ties(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.NOT": {"before": 10, "after": 10, "total": 12},
        }
        result = decide(
            paired, active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.NOT"}, settings=Settings(),
            same_grade_capabilities=("B.IFF", "B.NOT"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 68, "after": 68, "total": 72,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay={
                "status": "MEASURED", "cohort_sha256": "a" * 64,
                "rows": 291, "before_correct": 287, "after_correct": 288,
                "regressions": [],
                "repaired": [{"id": "c1", "capability": "C.DIV"}],
                "grades": {
                    "B": {"before": 68, "after": 68, "total": 72,
                          "net_correct_delta": 0},
                    "C": {"before": 146, "after": 147, "total": 147,
                          "net_correct_delta": 1},
                },
            },
            protected_frontier_grade="B")
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")
