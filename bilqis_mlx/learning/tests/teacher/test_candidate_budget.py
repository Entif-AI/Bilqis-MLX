"""Candidate budget."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, candidate_step_budget, decide,
    observe_context,
)


class CandidateBudgetTests(CausalTeacherExperimentTests):
    def test_candidate_step_budget_shrinks_only_for_interference_pressure(self):
        teacher = {
            "strategies": {"policy": {"lr": .00013}},
            "global_stats": {
                "policy": {"trials": 20, "reward_sum": 0.,
                           "reward_ema": 0., "latest": 0.},
            },
            "grade_stats": {},
            "events": 20,
        }
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 16)

        no_gain = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())
        for _ in range(4):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_1",
                policy_key="policy", decision=no_gain, local_gain=0.,
                curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 16)

        interference = decide({
            "C.SUB": {"before": 22, "after": 23, "total": 33},
            "A.EDGE": {"before": 6, "after": 4, "total": 6},
        }, active_capability="C.SUB", phase="RECOVERY_1",
            protected={"A.EDGE"}, settings=Settings())
        for _ in range(2):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_1",
                policy_key="policy", decision=interference, local_gain=.03,
                curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 8)
        for _ in range(2):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_1",
                policy_key="policy", decision=interference, local_gain=.03,
                curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 4)

        retained = decide({
            "C.SUB": {"before": 22, "after": 23, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="policy", decision=retained, local_gain=.03,
            curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 16)

    def test_candidate_step_budget_recovers_when_interference_streak_breaks(self):
        teacher = {
            "strategies": {"policy": {"lr": .00013}},
            "global_stats": {
                "policy": {"trials": 20, "reward_sum": 0.,
                           "reward_ema": 0., "latest": 0.},
            },
            "grade_stats": {}, "events": 20,
        }
        interference = decide({
            "C.SUB": {"before": 22, "after": 23, "total": 33},
            "A.EDGE": {"before": 6, "after": 4, "total": 6},
        }, active_capability="C.SUB", phase="RECOVERY_1",
            protected={"A.EDGE"}, settings=Settings())
        no_gain = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())

        for _ in range(4):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_1",
                policy_key="policy", decision=interference, local_gain=.03,
                curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 4)

        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="policy", decision=no_gain, local_gain=0.,
            curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 16)
