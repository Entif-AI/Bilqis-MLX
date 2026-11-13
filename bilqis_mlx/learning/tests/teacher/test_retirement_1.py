"""Retirement."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, contextual_pick, decide,
    live_scale_teacher, math, observe_context, random,
    selection_credit,
)


class Retirement1Tests(CausalTeacherExperimentTests):
    def test_capability_stagnation_spans_policy_ids_and_suppresses_novelty(self):
        teacher = {
            "strategies": {
                "winner": {"lr": .00008},
                "failed_a": {"lr": .0002},
                "failed_b": {"lr": .0003},
                "novel": {"lr": .00013},
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 2., "reward_ema": .1,
                      "latest": .1}
                for key in ("winner", "failed_a", "failed_b", "novel")
            },
            "grade_stats": {},
            "events": 80,
        }
        retained = decide({
            "C.SUB": {"before": 18, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_2",
            policy_key="winner", decision=retained, local_gain=.4,
            curriculum_scope="scope")

        no_gain = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_2",
            policy_key="failed_a", decision=no_gain, local_gain=0.,
            curriculum_scope="scope")
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="failed_b", decision=dict(no_gain, phase="RECOVERY_1"),
            local_gain=0., curriculum_scope="scope")

        capability = teacher["causal_experiment"]["capability_stagnation"][
            "C.SUB|scope"]
        self.assertEqual(capability["rejection_streak"], 2)
        self.assertEqual(capability["no_target_gain_streak"], 2)
        self.assertEqual(capability["attempts_since_retained"], 2)

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "novel", _teacher["strategies"]["novel"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "winner")

    def test_repeated_no_target_gain_demotes_policy_until_real_gain_resets_streak(self):
        teacher = live_scale_teacher()
        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "stagnant", _teacher["strategies"]["stagnant"]

        self.assertEqual(len(teacher["strategies"]), 494)
        picked, _ = contextual_pick(
            Legacy, teacher, "C.ADD", "MAIN", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "alternate")

        no_gain = decide({
            "C.ADD": {"before": 3, "after": 3, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        no_gain_credit = observe_context(
            teacher, capability="C.ADD", phase="MAIN",
            policy_key="stagnant", decision=no_gain,
            local_gain=0., curriculum_scope="scope")
        self.assertLessEqual(
            no_gain_credit["teacher_selection_reward"],
            0.-no_gain_credit["inherited_exploration_credit"])
        self.assertEqual(
            selection_credit(0., no_gain, no_gain_credit),
            no_gain_credit["teacher_selection_reward"])
        next_log = math.log(teacher["events"] + 4)
        stagnant_rank = (
            (-.7 + no_gain_credit["teacher_selection_reward"]) / 15
            + .6 * math.sqrt(next_log / 16)
        )
        productive_rank = (
            4.34 / 41 + .6 * math.sqrt(next_log / 42)
        )
        self.assertLess(stagnant_rank, productive_rank)
        self.assertEqual(
            teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"]
                   ["stagnant"]["no_target_gain_streak"], 6)
        self.assertEqual(
            teacher["causal_experiment"]["stagnation"]["C.ADD|scope"]
                   ["stagnant"]["no_target_gain_streak"], 6)

        recovery_no_gain = dict(no_gain, phase="RECOVERY_1")
        observe_context(teacher, capability="C.ADD", phase="RECOVERY_1",
                        policy_key="stagnant", decision=recovery_no_gain,
                        local_gain=0., curriculum_scope="scope")
        self.assertEqual(
            teacher["causal_experiment"]["stagnation"]["C.ADD|scope"]
                   ["stagnant"]["no_target_gain_streak"], 7)

        gain = decide({
            "C.ADD": {"before": 3, "after": 4, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        recovery_gain = dict(gain, phase="RECOVERY_2")
        observe_context(teacher, capability="C.ADD", phase="RECOVERY_2",
                        policy_key="stagnant", decision=recovery_gain,
                        local_gain=.1, curriculum_scope="scope")
        self.assertEqual(
            teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"]
                   ["stagnant"]["no_target_gain_streak"], 6)
        self.assertEqual(
            teacher["causal_experiment"]["contexts"]["C.ADD|RECOVERY_2|scope"]
                   ["stagnant"]["no_target_gain_streak"], 0)
        self.assertEqual(
            teacher["causal_experiment"]["stagnation"]["C.ADD|scope"]
                   ["stagnant"]["no_target_gain_streak"], 0)
