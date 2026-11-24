"""Retirement."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, contextual_pick, decide,
    observe_context, random, strategy_population_teacher,
)


class Retirement2Tests(CausalTeacherExperimentTests):
    def test_same_student_target_failure_retires_but_target_gain_reopens_policy(self):
        import bilqis_mlx.compatibility.historical_teacher_policy as policy_engine

        teacher = strategy_population_teacher(count=17)
        policy = "policy-000"
        teacher["global_stats"][policy].update(
            trials=10, reward_sum=2., reward_ema=.2, latest=.2)
        teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"] = {
            policy: {"trials": 5, "reward_sum": 2., "unsafe": 0,
                     "retained": 5, "latest": .4, "no_target_gain_streak": 0},
        }
        checkpoint_a = "a" * 64
        checkpoint_b = "b" * 64
        no_gain = decide({
            "C.ADD": {"before": 5, "after": 4, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        interference = decide({
            "C.ADD": {"before": 3, "after": 4, "total": 6},
            "B.XOR": {"before": 6, "after": 4, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected={"B.XOR"},
            settings=Settings(), mature_grades=frozenset({"B"}))

        observe_context(
            teacher, capability="C.ADD", phase="MAIN",
            policy_key=policy, decision=no_gain, local_gain=-.2,
            curriculum_scope="scope",
            student_checkpoint_sha256=checkpoint_a)
        still_active = contextual_pick(
            policy_engine, teacher, "C.ADD", "MAIN", random.Random(3),
            curriculum_scope="scope", student_checkpoint_sha256=checkpoint_a,
            return_metadata=True)
        self.assertEqual(
            still_active[2]["checkpoint_retired_effective_strategy_count"], 0)

        observe_context(
            teacher, capability="C.ADD", phase="MAIN",
            policy_key=policy, decision=no_gain, local_gain=-.2,
            curriculum_scope="scope",
            student_checkpoint_sha256=checkpoint_a)
        retired = contextual_pick(
            policy_engine, teacher, "C.ADD", "MAIN", random.Random(3),
            curriculum_scope="scope", student_checkpoint_sha256=checkpoint_a,
            return_metadata=True)
        self.assertEqual(
            retired[2]["checkpoint_retired_effective_strategy_count"], 1)
        self.assertNotEqual(retired[0], policy)

        observe_context(
            teacher, capability="C.ADD", phase="MAIN",
            policy_key=policy, decision=interference, local_gain=.2,
            curriculum_scope="scope", student_checkpoint_sha256=checkpoint_a)
        self.assertEqual(
            teacher["causal_experiment"]["stagnation"]["C.ADD|scope"]
                   [policy]["no_target_gain_streak"], 0)
        reopened = contextual_pick(
            policy_engine, teacher, "C.ADD", "MAIN", random.Random(3),
            curriculum_scope="scope", student_checkpoint_sha256=checkpoint_a,
            return_metadata=True)
        self.assertEqual(
            reopened[2]["checkpoint_retired_effective_strategy_count"], 0)

        new_student = contextual_pick(
            policy_engine, teacher, "C.ADD", "MAIN", random.Random(3),
            curriculum_scope="scope", student_checkpoint_sha256=checkpoint_b,
            return_metadata=True)
        self.assertEqual(
            new_student[2]["checkpoint_retired_effective_strategy_count"], 0)
