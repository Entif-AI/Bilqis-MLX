"""Plasticity."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, decide,
)


class Plasticity2Tests(CausalTeacherExperimentTests):
    def test_starvation_plasticity_uses_frontier_mastery_debt_not_raw_slack(self):
        paired = {
            "C.COUNT": {"before": 4, "after": 5, "total": 6},
            "C.ORDER": {"before": 6, "after": 6, "total": 6},
        }
        fixed = {"status": "MEASURED", "grade": "C",
                 "before": 60, "after": 61, "total": 72,
                 "cohort_sha256": "a" * 64}
        base_frontier = {
            "status": "MEASURED", "cohort_sha256": "b" * 64,
            "rows": 144, "before_correct": 130, "after_correct": 129,
            "regressions": [{"id": "c-loss", "capability": "C.ORDER"}],
            "repaired": [],
            "grades": {"C": {"before": 61, "after": 60, "total": 72,
                              "net_correct_delta": -1}},
            "capabilities": {
                "C.COUNT": {"before": 25, "after": 27, "total": 36,
                            "net_correct_delta": 2},
                "C.ORDER": {"before": 36, "after": 33, "total": 36,
                            "net_correct_delta": -3},
            },
        }
        allowed = decide(
            paired, active_capability="C.COUNT", phase="MAIN",
            protected={"C.ORDER"}, settings=Settings(),
            same_grade_capabilities=("C.COUNT", "C.ORDER"),
            fixed_grade_replay=fixed, fixed_frontier_replay=base_frontier,
            protected_frontier_grade="C", plasticity_escape={"active": True})
        self.assertEqual(allowed["decision"], "PROVISIONAL")
        self.assertEqual(allowed["plasticity_escape"]["waived_reason"],
                         "ACTIVE_SCHOOL_GRADE_REGRESSION")

        bad_trade = decide(
            paired, active_capability="C.COUNT", phase="MAIN",
            protected={"C.ORDER"}, settings=Settings(),
            same_grade_capabilities=("C.COUNT", "C.ORDER"),
            fixed_grade_replay=fixed,
            fixed_frontier_replay={**base_frontier,
                "before_correct": 55, "after_correct": 52,
                "grades": {"C": {"before": 55, "after": 52, "total": 72,
                                  "net_correct_delta": -3}},
                "capabilities": {
                    "C.COUNT": {"before": 25, "after": 27, "total": 36,
                                "net_correct_delta": 2},
                    "C.ORDER": {"before": 30, "after": 25, "total": 36,
                                "net_correct_delta": -5},
                }},
            protected_frontier_grade="C", plasticity_escape={"active": True})
        self.assertEqual(bad_trade["decision"], "REJECT")
        self.assertEqual(bad_trade["reason"], "ACTIVE_SCHOOL_GRADE_REGRESSION")

    def test_plasticity_activation_is_starvation_local_and_closes_after_retention(self):
        from types import SimpleNamespace
        from bilqis_mlx.learning.plasticity_escape import activation, record_school_visit

        program = SimpleNamespace(grades=(
            SimpleNamespace(id="A", teaching_stages=()),
            SimpleNamespace(id="C", teaching_stages=(("C.COUNT",), ("C.ORDER",))),
        ))
        school = SimpleNamespace(
            active_grades=("A", "C"), grade="C", stage="MAIN",
            introduction_stage=0)
        scope = "fixture/4"
        teacher = {"causal_experiment": {"capability_stagnation": {
            "C.COUNT|" + scope: {"attempts_since_retained": 16},
        }}}
        frontier = activation(teacher, "C.COUNT", scope, school, program)
        self.assertTrue(frontier["active"])
        self.assertEqual(frontier["activation_threshold"], 16)
        self.assertTrue(frontier["frontier_priority"])

        teacher["causal_experiment"]["capability_stagnation"][
            "C.COUNT|" + scope]["attempts_since_retained"] = 0
        self.assertFalse(activation(
            teacher, "C.COUNT", scope, school, program)["active"])
        teacher["causal_experiment"]["capability_stagnation"]["A.MAPS|" + scope] = {
            "attempts_since_retained": 31}
        self.assertFalse(activation(teacher, "A.MAPS", scope, school, program)["active"])
        teacher["causal_experiment"]["capability_stagnation"]["A.MAPS|" + scope][
            "attempts_since_retained"] = 32
        self.assertTrue(activation(teacher, "A.MAPS", scope, school, program)["active"])
        sweep = SimpleNamespace(**{**school.__dict__, "stage": "PROMOTION_SWEEP"})
        teacher["causal_experiment"]["capability_stagnation"][
            "C.COUNT|" + scope]["attempts_since_retained"] = 100
        self.assertFalse(activation(
            teacher, "C.COUNT", scope, sweep, program)["active"])

        # School-wide drought is a second trigger that does not require this
        # capability to have accumulated its own local starvation count.
        teacher["causal_experiment"]["school_attempts_since_retained"] = 24
        receipt = {"last_exam": {"scores": {
            "A.MAPS": {"correct": 6, "total": 12},
            "C.COUNT": {"correct": 20, "total": 33},
            "C.ORDER": {"correct": 33, "total": 33},
        }}}
        teacher["causal_experiment"]["capability_stagnation"][
            "C.COUNT|" + scope]["attempts_since_retained"] = 0
        drought = activation(
            teacher, "C.COUNT", scope, school, program, receipt=receipt)
        self.assertTrue(drought["active"])
        self.assertEqual(drought["activation_triggers"],
                         ["SCHOOL_RETENTION_DROUGHT_BELOW_MEAN"])
        self.assertEqual(drought["school_attempts_since_retained"], 24)
        self.assertEqual(drought["school_drought_threshold"], 24)
        self.assertEqual(drought["current_capability_score"],
                         {"correct": 20, "total": 33})
        self.assertLess(drought["current_capability_accuracy"],
                        drought["school_mean_accuracy"])

        # Equal/above-mean capabilities do not receive drought plasticity.
        self.assertFalse(activation(
            teacher, "C.ORDER", scope, school, program, receipt=receipt)["active"])
        self.assertFalse(activation(
            teacher, "C.MISSING", scope, school, program, receipt=receipt)["active"])

        # A single retention anywhere in the school closes the global path.
        record_school_visit(teacher, retained=True)
        self.assertEqual(
            teacher["causal_experiment"]["school_attempts_since_retained"], 0)
        self.assertFalse(activation(
            teacher, "C.COUNT", scope, school, program, receipt=receipt)["active"])

    def test_school_drought_counter_counts_committed_nonretentions(self):
        from bilqis_mlx.learning.plasticity_escape import record_school_visit

        teacher = {"causal_experiment": {}}
        for _ in range(24):
            record_school_visit(teacher, retained=False)
        self.assertEqual(
            teacher["causal_experiment"]["school_attempts_since_retained"], 24)
        record_school_visit(teacher, retained=True)
        self.assertEqual(
            teacher["causal_experiment"]["school_attempts_since_retained"], 0)
