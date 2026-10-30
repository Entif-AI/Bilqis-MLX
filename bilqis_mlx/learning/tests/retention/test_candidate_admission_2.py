"""Candidate admission."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, decide, observe_context,
    whole_grade_protection,
)


class CandidateAdmission2Tests(CausalTeacherExperimentTests):
    def test_late_stage_allows_other_grade_gain_when_active_grade_is_flat(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.NOT": {"before": 10, "after": 9, "total": 12},
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
                "rows": 291, "before_correct": 287, "after_correct": 288,
                "regressions": [],
                "repaired": [{"id": "b1", "capability": "B.IFF"}],
                "grades": {
                    "B": {"before": 68, "after": 69, "total": 72,
                          "net_correct_delta": 1},
                    "C": {"before": 146, "after": 146, "total": 147,
                          "net_correct_delta": 0},
                },
            },
            protected_frontier_grade="C")
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")

    def test_late_stage_rejects_if_active_school_grade_regresses(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.NOT": {"before": 10, "after": 10, "total": 12},
        }
        result = decide(
            paired, active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.NOT"}, settings=Settings(),
            same_grade_capabilities=("B.IFF", "B.NOT"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 68, "after": 70, "total": 72,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay={
                "status": "MEASURED", "cohort_sha256": "a" * 64,
                "rows": 291, "before_correct": 287, "after_correct": 288,
                "regressions": [{"id": "c1", "capability": "C.DIV"}],
                "repaired": [
                    {"id": "b1", "capability": "B.IFF"},
                    {"id": "b2", "capability": "B.NOT"},
                ],
                "grades": {
                    "B": {"before": 68, "after": 70, "total": 72,
                          "net_correct_delta": 2},
                    "C": {"before": 146, "after": 145, "total": 147,
                          "net_correct_delta": -1},
                },
            },
            protected_frontier_grade="C")
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "ACTIVE_SCHOOL_GRADE_REGRESSION")

    def test_frontier_allows_item_flux_when_frontier_aggregate_holds(self):
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
                "rows": 291, "before_correct": 287, "after_correct": 288,
                "regressions": [{"id": "c-old-right-now-wrong",
                                 "capability": "C.DIV"}],
                "repaired": [{"id": "c-old-wrong-now-right",
                              "capability": "C.MUL"},
                             {"id": "b-target-repair",
                              "capability": "B.IFF"}],
                "grades": {
                    "B": {"before": 68, "after": 69, "total": 72,
                          "net_correct_delta": 1},
                    "C": {"before": 146, "after": 146, "total": 147,
                          "net_correct_delta": 0},
                },
            },
            protected_frontier_grade="C")
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")
        self.assertEqual(result["protected_frontier_grade"], "C")
        self.assertEqual(result["protected_frontier_grade_net_correct_delta"], 0)

    def test_late_stage_allows_frontier_without_fully_withheld_logical_grade(self):
        paired = {
            "C.MUL": {"before": 17, "after": 18, "total": 21},
            "C.DIV": {"before": 18, "after": 18, "total": 21},
        }
        result = decide(
            paired, active_capability="C.MUL", phase="RECOVERY_2",
            protected={"C.DIV"}, settings=Settings(),
            same_grade_capabilities=("C.MUL", "C.DIV"),
            fixed_grade_replay={"status": "MEASURED", "grade": "C",
                                "before": 139, "after": 140, "total": 147,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay={
                "status": "MEASURED", "cohort_sha256": "a" * 64,
                "rows": 219, "before_correct": 209, "after_correct": 210,
                "regressions": [],
                "repaired": [{"id": "c1", "capability": "C.MUL"}],
                "grades": {
                    "A": {"before": 70, "after": 70, "total": 72,
                          "net_correct_delta": 0},
                    "C": {"before": 139, "after": 140, "total": 147,
                          "net_correct_delta": 1},
                },
            },
            protected_frontier_grade="B")
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")

    def test_all_target_grade_capabilities_must_be_measured(self):
        paired = {"B.XOR": {"before": 7, "after": 8, "total": 12}}
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_SAME_GRADE_PROBE"):
            decide(paired, active_capability="B.XOR", phase="MAIN",
                   protected=set(), settings=Settings(),
                   same_grade_capabilities=("B.IFF", "B.XOR"))

    def test_six_b_capabilities_all_scored_with_bounded_cross_grade_probes(self):
        admitted = {f"B.{name}" for name in (
            "AND", "IFF", "IMPLIES", "NOT", "OR", "XOR")}
        admitted.update({f"A.{i}" for i in range(6)})
        admitted.update({f"C.{i}" for i in range(7)})
        selected = whole_grade_protection(
            admitted, "B.XOR", {}, cap_limit=8, rotation=11)
        self.assertEqual(len(selected), 8)
        self.assertEqual({cap for cap in selected if cap.startswith("B.")},
                         admitted.intersection({cap for cap in admitted
                                                if cap.startswith("B.")}) - {"B.XOR"})
        self.assertEqual({cap.split(".")[0] for cap in selected}, {"A", "B", "C"})
        too_many = {f"B.{i}" for i in range(10)}
        too_many.update({f"A.{i}" for i in range(6)})
        large_grade = whole_grade_protection(
            too_many, "B.0", {}, cap_limit=8, rotation=0)
        self.assertEqual({cap for cap in large_grade if cap.startswith("B.")},
                         {f"B.{i}" for i in range(1, 10)})
        self.assertEqual(len(large_grade), 11)

    def test_vulnerable_boolean_anchor_flip_is_diagnostic_not_an_item_veto(self):
        paired = {"C.SUCCESSOR": {"before": 20, "after": 21, "total": 21},
                  "B.XOR": {"before": 6, "after": 6, "total": 6}}
        replay = {"status": "MEASURED", "cohort_sha256": "a" * 64,
                  "rows": 24, "regressions": [{"id": "xor_true_case", "capability": "B.XOR"}],
                  "repaired": 1}
        trial = decide(paired, active_capability="C.SUCCESSOR", phase="MAIN",
                       protected={"B.XOR"}, settings=Settings(),
                       mature_grades=frozenset({"A", "B"}), fragile_replay=replay)
        self.assertEqual(trial["decision"], "REJECT")
        self.assertEqual(trial["reason"], "FRAGILE_COMPOSITION_REPLAY_REGRESSION")
        self.assertEqual(trial["fragile_replay"]["regressions"], replay["regressions"])
        teacher = {"strategies": {"p": {"lr": 0.0001}}}
        observe_context(teacher, capability="C.SUCCESSOR", phase="MAIN",
                        policy_key="p", decision=trial, local_gain=0.03)
        strategy = teacher["causal_experiment"]["contexts"]["C.SUCCESSOR|MAIN|"]["p"]
        self.assertEqual(strategy["unsafe"], 1)
        self.assertEqual(strategy["latest_fragile_replay"]["regressions"], 1)
        replay["regressions"] = []
        safe = decide(paired, active_capability="C.SUCCESSOR", phase="MAIN",
                      protected={"B.XOR"}, settings=Settings(), fragile_replay=replay)
        self.assertEqual(safe["decision"], "PROVISIONAL")
