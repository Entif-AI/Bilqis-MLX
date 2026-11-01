"""Plasticity."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, decide, patch,
    predicted, rows, schedule_program,
)


class Plasticity1Tests(CausalTeacherExperimentTests):
    def test_starvation_plasticity_rejects_raw_small_loss_when_mastery_debt_grows(self):
        from pathlib import Path
        from bilqis_mlx import trainer as trainer
        grade = ("B.IFF", "B.NOT", "B.XOR")
        rows = [{"id": cap + str(i), "capability": cap,
                 "gold": "TRUE"} for cap in (*grade, "A.EDGE") for i in range(2)]
        parent = predicted(rows, {"B.XOR0", "B.NOT0"})
        candidate = dict(parent)
        candidate["B.XOR0"] = "TRUE"
        candidate["B.IFF0"] = "FALSE"
        candidate["B.NOT0"] = "FALSE"
        candidate["B.NOT1"] = "FALSE"
        with (patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                           return_value=(*grade, "A.EDGE")),
              patch('bilqis_mlx.learning.student_ops._predictions',
                           side_effect=lambda _mx, identity, selected, *_:
                           {row["id"]: (parent if identity == "parent"
                                        else candidate)[row["id"]]
                            for row in selected}),
              patch('bilqis_mlx.runtime.candidate_evidence._fixed_same_grade_rows',
                    return_value=())):
            program = schedule_program(("A", ("A.EDGE",)), ("B", grade))
            _, _, _, fixed, _, _, stage = trainer._candidate_grade_evidence(
                None, Path("/not-used"), {"config": {}, "answer_ids": []},
                program, object(), "B.XOR", "parent", "candidate", rows,
                {"B.XOR0": parent["B.XOR0"], "B.XOR1": parent["B.XOR1"]},
                Settings(), plasticity_escape={"active": True})
        # The historical rule allowed any raw -1 grade trade under plasticity.
        # Quadratic mastery debt correctly rejects this one: the +1 XOR repair
        # is outweighed by damage to already-weaker NOT plus perfect IFF.
        self.assertEqual(stage, "GRADE_NET_REJECTED")
        self.assertEqual(fixed["status"], "NOT_MEASURED")

    def test_starvation_plasticity_can_temporarily_accept_bounded_same_grade_loss(self):
        paired = {
            "C.COUNT": {"before": 4, "after": 5, "total": 6},
            "C.NUMBER": {"before": 6, "after": 5, "total": 6},
            "C.ORDER": {"before": 6, "after": 6, "total": 6},
        }
        result = decide(
            paired, active_capability="C.COUNT", phase="MAIN",
            protected={"C.NUMBER", "C.ORDER"}, settings=Settings(),
            same_grade_capabilities=("C.COUNT", "C.NUMBER", "C.ORDER"),
            plasticity_escape={
                "active": True, "attempts_since_retained": 94,
                "activation_threshold": 16, "frontier_priority": True,
            })
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")
        self.assertEqual(result["plasticity_escape"]["waived_reason"],
                         "NO_POSITIVE_SAME_GRADE_GAIN")
        self.assertTrue(result["plasticity_escape"]["applied"])

    def test_starvation_plasticity_still_rejects_no_gain_or_excessive_regression(self):
        escape = {
            "active": True, "attempts_since_retained": 94,
            "activation_threshold": 16, "frontier_priority": True,
        }
        no_gain = decide(
            {
                "C.COUNT": {"before": 4, "after": 4, "total": 6},
                "C.NUMBER": {"before": 6, "after": 6, "total": 6},
            }, active_capability="C.COUNT", phase="MAIN",
            protected={"C.NUMBER"}, settings=Settings(),
            same_grade_capabilities=("C.COUNT", "C.NUMBER"),
            plasticity_escape=escape)
        self.assertEqual(no_gain["reason"], "NO_MEASURABLE_TARGET_GAIN")

        excessive = decide(
            {
                "C.COUNT": {"before": 3, "after": 5, "total": 6},
                "C.NUMBER": {"before": 6, "after": 3, "total": 6},
            }, active_capability="C.COUNT", phase="RECOVERY_1",
            protected={"C.NUMBER"}, settings=Settings(),
            same_grade_capabilities=("C.COUNT", "C.NUMBER"),
            plasticity_escape=escape)
        self.assertEqual(excessive["decision"], "REJECT")
        self.assertEqual(excessive["same_grade_net_correct_delta"], -1)
        self.assertEqual(excessive["reason"], "PROTECTED_CAPABILITY_REGRESSION")

    def test_starvation_plasticity_allows_one_extra_protected_loss(self):
        result = decide(
            {
                "C.COUNT": {"before": 3, "after": 5, "total": 6},
                "B.IFF": {"before": 6, "after": 4, "total": 6},
            }, active_capability="C.COUNT", phase="RECOVERY_1",
            protected={"B.IFF"}, settings=Settings(),
            mature_grades=frozenset({"B"}),
            same_grade_capabilities=("C.COUNT",),
            plasticity_escape={"active": True})
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["plasticity_escape"]["waived_reason"],
                         "PROTECTED_CAPABILITY_REGRESSION")
        self.assertEqual(result["worst_protected_loss"], 2)

    def test_plasticity_values_frontier_gain_by_normalized_mastery_debt(self):
        # SUB gains four percentage points while a mastered COUNT gives back six.
        # Raw answer accounting is -2, but normalized quadratic mastery debt says
        # the weak capability's repair is substantially more valuable.
        result = decide(
            {
                "C.SUB": {"before": 56, "after": 60, "total": 100},
                "C.COUNT": {"before": 100, "after": 94, "total": 100},
            }, active_capability="C.SUB", phase="RECOVERY_1",
            protected={"C.COUNT"}, settings=Settings(),
            same_grade_capabilities=("C.SUB", "C.COUNT"),
            plasticity_escape={"active": True})
        self.assertEqual(result["same_grade_net_correct_delta"], -2)
        self.assertEqual(result["decision"], "PROVISIONAL")
        utility = result["plasticity_escape"]["mastery_debt_utility"]
        self.assertEqual(utility["power"], 2)
        self.assertGreater(utility["same_grade"]["net"], 0)
        self.assertAlmostEqual(
            utility["same_grade"]["capabilities"]["C.SUB"]["utility_delta"],
            .0336)
        self.assertAlmostEqual(
            utility["same_grade"]["capabilities"]["C.COUNT"]["utility_delta"],
            -.0036)

    def test_plasticity_can_waive_six_answer_protected_loss_when_debt_trade_wins(self):
        paired = {
            "C.SUB": {"before": 18, "after": 22, "total": 33},
            "C.COUNT": {"before": 33, "after": 27, "total": 33},
        }
        ordinary = decide(
            paired, active_capability="C.SUB", phase="RECOVERY_1",
            protected={"C.COUNT"}, settings=Settings(),
            same_grade_capabilities=("C.SUB", "C.COUNT"))
        self.assertEqual(ordinary["decision"], "REJECT")
        self.assertEqual(ordinary["reason"], "PROTECTED_CAPABILITY_REGRESSION")
        self.assertEqual(ordinary["exceeded"], {"C.COUNT": 6})

        plastic = decide(
            paired, active_capability="C.SUB", phase="RECOVERY_1",
            protected={"C.COUNT"}, settings=Settings(),
            same_grade_capabilities=("C.SUB", "C.COUNT"),
            plasticity_escape={"active": True})
        self.assertEqual(plastic["decision"], "PROVISIONAL")
        self.assertEqual(plastic["plasticity_escape"]["waived_reason"],
                         "PROTECTED_CAPABILITY_REGRESSION")
        self.assertGreater(
            plastic["plasticity_escape"]["mastery_debt_utility"]
                   ["same_grade"]["net"], 0)

    def test_plasticity_rejects_trade_when_normalized_mastery_debt_grows(self):
        # The same +4/-6 raw trade is bad when the sacrificed capability is
        # already materially weak rather than sitting at mastery surplus.
        result = decide(
            {
                "C.SUB": {"before": 60, "after": 64, "total": 100},
                "C.COUNT": {"before": 70, "after": 64, "total": 100},
            }, active_capability="C.SUB", phase="RECOVERY_1",
            protected={"C.COUNT"}, settings=Settings(),
            same_grade_capabilities=("C.SUB", "C.COUNT"),
            plasticity_escape={"active": True})
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "SAME_GRADE_NET_REGRESSION")
        self.assertLess(
            result["plasticity_escape"]["mastery_debt_utility"]
                  ["same_grade"]["net"], 0)

    def test_mastery_debt_utility_gives_each_capability_one_normalized_vote(self):
        from bilqis_mlx.learning.plasticity_escape import mastery_debt_utility
        utility = mastery_debt_utility({
            "C.SMALL_PANEL": {"before": 6, "after": 9, "total": 12},
            "C.LARGE_PANEL": {"before": 30, "after": 45, "total": 60},
        })
        small = utility["capabilities"]["C.SMALL_PANEL"]["utility_delta"]
        large = utility["capabilities"]["C.LARGE_PANEL"]["utility_delta"]
        self.assertAlmostEqual(small, large)
        self.assertAlmostEqual(utility["net"], small + large)
