"""Selection."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, contextual_pick, decide,
    observe_context, random,
)


class SelectionTests(CausalTeacherExperimentTests):
    def test_single_retained_context_success_is_immediately_exploitable(self):
        teacher = {
            "strategies": {
                "legacy": {"lr": .0002},
                "retained": {"lr": .00008},
            },
            "global_stats": {
                "legacy": {"trials": 20, "reward_sum": 2., "reward_ema": .1,
                           "latest": .1},
                "retained": {"trials": 20, "reward_sum": 2., "reward_ema": .1,
                             "latest": .1},
            },
            "grade_stats": {},
            "events": 40,
        }

        rejected = decide({
            "C.ADD": {"before": 3, "after": 3, "total": 6},
        }, active_capability="C.ADD", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.ADD", phase="RECOVERY_2",
            policy_key="legacy", decision=rejected, local_gain=0.,
            curriculum_scope="scope")

        retained = decide({
            "C.ADD": {"before": 3, "after": 5, "total": 6},
        }, active_capability="C.ADD", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        self.assertEqual(retained["decision"], "PROVISIONAL")
        observe_context(
            teacher, capability="C.ADD", phase="RECOVERY_2",
            policy_key="retained", decision=retained, local_gain=.4,
            curriculum_scope="scope")

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "legacy", _teacher["strategies"]["legacy"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.ADD", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "retained")

    def test_diagnostic_context_prefers_policy_proven_under_current_signal(self):
        teacher = {
            "strategies": {
                "diagnostic": {"lr": .00008},
                "legacy": {"lr": .00013},
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 0., "reward_ema": 0.,
                      "latest": 0.}
                for key in ("diagnostic", "legacy")
            },
            "grade_stats": {},
            "events": 40,
        }
        retained = decide({
            "C.SUB": {"before": 20, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        matching = {
            "warnings": ("CHANCE_LEVEL_OR_LAGGING",),
            "unresolved_miss_count": 12,
            "champion_candidate_count": 3,
        }
        other = {
            "warnings": (),
            "unresolved_miss_count": 0,
            "champion_candidate_count": 0,
        }
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_2",
            policy_key="diagnostic", decision=retained, local_gain=.2,
            curriculum_scope="scope", diagnostics=matching)
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_2",
            policy_key="legacy", decision=retained, local_gain=.8,
            curriculum_scope="scope", diagnostics=other)

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "legacy", _teacher["strategies"]["legacy"]

        picked, _policy, selection = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope", diagnostics=matching,
            return_metadata=True)
        self.assertEqual(picked, "diagnostic")
        self.assertTrue(selection["diagnostic_context_consumed"])
        self.assertIsInstance(selection["diagnostic_context_key"], str)
