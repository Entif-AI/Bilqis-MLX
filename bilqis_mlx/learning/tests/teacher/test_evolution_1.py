"""Evolution."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, contextual_pick, decide,
    observe_context, random,
)


class Evolution1Tests(CausalTeacherExperimentTests):
    def test_rejection_pressure_stops_unseen_legacy_novelty_without_retained_winner(self):
        teacher = {
            "strategies": {
                "less_bad": {"lr": .00008},
                "worse": {"lr": .0002},
                "novel": {"lr": .00013},
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 0., "reward_ema": 0.,
                      "latest": 0.}
                for key in ("less_bad", "worse", "novel")
            },
            "grade_stats": {},
            "events": 60,
        }
        mild_reject = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())
        worse_reject = decide({
            "C.SUB": {"before": 22, "after": 18, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="less_bad", decision=mild_reject, local_gain=0.,
            curriculum_scope="scope")
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="worse", decision=worse_reject, local_gain=-.4,
            curriculum_scope="scope")

        class Legacy:
            calls = 0

            @staticmethod
            def pick(_teacher, _grade, _rng):
                Legacy.calls += 1
                return "novel", _teacher["strategies"]["novel"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_1", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "less_bad")
        self.assertEqual(Legacy.calls, 0)

        stagnation = teacher["causal_experiment"]["capability_stagnation"][
            "C.SUB|scope"]
        stagnation["rejection_streak"] = 4
        stagnation["attempts_since_retained"] = 4
        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_1", random.Random(2),
            curriculum_scope="scope")
        # Engines without the bounded knob vocabulary cannot breed a bespoke
        # challenger; under sustained pressure they stay on the best evidenced
        # incumbent rather than sampling an unseen archive policy.
        self.assertEqual(picked, "less_bad")
        self.assertEqual(Legacy.calls, 0)

    def test_plasticity_retries_preplasticity_target_gain_before_breeding_again(self):
        near_miss = {
            "contrast": 1., "depth": 1, "distill": .33,
            "lr": .000042, "old": 20, "preview": 4,
        }
        parent = {
            "contrast": 0., "depth": 1, "distill": .33,
            "lr": .0002, "old": 12, "preview": 4,
        }
        teacher = {
            "strategies": {"near_miss": near_miss, "parent": parent},
            "global_stats": {
                "near_miss": {"trials": 4, "reward_sum": -.4,
                              "reward_ema": -.1, "latest": -.1},
                "parent": {"trials": 20, "reward_sum": 2.,
                           "reward_ema": .1, "latest": .1},
            },
            "grade_stats": {"C": {
                "parent": {"trials": 20, "reward_sum": 2.,
                           "reward_ema": .1, "latest": .1},
            }},
            "events": 60,
        }
        rejected = decide({
            "C.DIV": {"before": 10, "after": 11, "total": 33},
            "C.MUL": {"before": 30, "after": 28, "total": 33},
        }, active_capability="C.DIV", phase="RECOVERY_1",
            protected=set(), settings=Settings(),
            same_grade_capabilities=("C.DIV", "C.MUL"))
        self.assertEqual(rejected["reason"], "SAME_GRADE_NET_REGRESSION")
        observe_context(
            teacher, capability="C.DIV", phase="RECOVERY_1",
            policy_key="near_miss", decision=rejected, local_gain=.1,
            curriculum_scope="scope")
        teacher["causal_experiment"]["capability_stagnation"][
            "C.DIV|scope"]["rejection_streak"] = 8

        class Legacy:
            KNOBS = {
                "contrast": (0., 1.), "depth": (1, 4),
                "distill": (0., .33), "lr": (.00004, .00008, .0002, .0003),
                "old": (4, 8, 12, 20), "preview": (0, 4),
            }

            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "parent", _teacher["strategies"]["parent"]

        picked, _policy, metadata = contextual_pick(
            Legacy, teacher, "C.DIV", "RECOVERY_1", random.Random(2),
            curriculum_scope="scope", return_metadata=True,
            plasticity_active=True)
        self.assertEqual(picked, "near_miss")
        self.assertEqual(metadata["selection_reason"], "PLASTICITY_RETRY")
