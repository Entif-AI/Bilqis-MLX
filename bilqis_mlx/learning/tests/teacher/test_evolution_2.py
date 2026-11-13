"""Evolution."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, _effective_policy_key, contextual_pick, random,
    strategy_population_teacher,
)


class Evolution2Tests(CausalTeacherExperimentTests):
    def test_rejection_pressure_pools_learning_rate_evidence_across_phases(self):
        teacher = {
            "strategies": {
                "low": {
                    "contrast": .5, "depth": 2, "distill": .15,
                    "lr": .00008, "old": 12, "preview": 0,
                },
                "high": {
                    "contrast": .5, "depth": 2, "distill": .15,
                    "lr": .0003, "old": 12, "preview": 0,
                },
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 0., "reward_ema": 0.,
                      "latest": 0.}
                for key in ("low", "high")
            },
            "grade_stats": {},
            "events": 80,
            "causal_experiment": {
                "version": "bilqis.mlx.causal-teacher-experiment/v1",
                "contexts": {
                    "C.SUB|MAIN|scope": {
                        "low": {
                            "trials": 4, "reward_sum": 2.,
                            "unsafe": 0, "retained": 4,
                            "latest": .5, "no_target_gain_streak": 0,
                        },
                        "high": {
                            "trials": 4, "reward_sum": -2.,
                            "unsafe": 4, "retained": 0,
                            "latest": -.5, "no_target_gain_streak": 4,
                        },
                    },
                    "C.SUB|RECOVERY_2|scope": {
                        "low": {
                            "trials": 2, "reward_sum": .1,
                            "unsafe": 1, "retained": 1,
                            "latest": .05, "no_target_gain_streak": 0,
                        },
                        "high": {
                            "trials": 2, "reward_sum": .2,
                            "unsafe": 1, "retained": 1,
                            "latest": .1, "no_target_gain_streak": 0,
                        },
                    },
                },
                "capability_stagnation": {
                    "C.SUB|scope": {
                        "rejection_streak": 6,
                        "no_target_gain_streak": 3,
                        "attempts_since_retained": 6,
                        "total_rejections": 8,
                        "total_retained": 2,
                    },
                },
            },
        }

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "high", _teacher["strategies"]["high"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "low")

    def test_rejection_pressure_exploration_mints_novel_effective_strategy(self):
        import bilqis_mlx.compatibility.historical_teacher_policy as policy_engine
        teacher = strategy_population_teacher(count=24)
        teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"] = {
            "policy-000": {
                "trials": 4, "reward_sum": 0., "unsafe": 4, "retained": 0,
                "latest": -.1, "no_target_gain_streak": 4,
            },
        }
        teacher["causal_experiment"]["capability_stagnation"] = {
            "C.ADD|scope": {
                "rejection_streak": 4, "no_target_gain_streak": 2,
                "attempts_since_retained": 4, "total_rejections": 4,
                "total_retained": 0, "current_rejection_reasons": {},
            },
        }
        before_effective = {
            _effective_policy_key(policy)
            for policy in teacher["strategies"].values()
        }
        before_count = len(teacher["strategies"])

        key, policy, metadata = contextual_pick(
            policy_engine, teacher, "C.ADD", "MAIN", random.Random(9),
            curriculum_scope="scope", return_metadata=True)

        self.assertEqual(metadata["selection_reason"], "FRESH_MUTATED_CHALLENGER")
        self.assertEqual(len(teacher["strategies"]), before_count + 1)
        self.assertNotIn(_effective_policy_key(policy), before_effective)
        self.assertEqual(teacher["strategies"][key], policy)

    def test_rejection_pressure_exploits_active_retained_context_before_breeding(self):
        import bilqis_mlx.compatibility.historical_teacher_policy as policy_engine
        teacher = strategy_population_teacher(count=24)
        winner = "policy-007"
        channel = teacher["causal_experiment"]
        channel["contexts"]["C.ADD|MAIN|scope"] = {
            winner: {
                "trials": 1, "reward_sum": -.06, "unsafe": 0,
                "retained": 1, "latest": -.06, "no_target_gain_streak": 0,
            },
            "policy-008": {
                "trials": 4, "reward_sum": .8, "unsafe": 4,
                "retained": 0, "latest": .2, "no_target_gain_streak": 0,
            },
        }
        channel["capability_stagnation"] = {
            "C.ADD|scope": {
                "rejection_streak": 8, "no_target_gain_streak": 0,
                "attempts_since_retained": 8, "total_rejections": 8,
                "total_retained": 1, "current_rejection_reasons": {},
            },
        }
        before = set(teacher["strategies"])

        key, policy, metadata = contextual_pick(
            policy_engine, teacher, "C.ADD", "MAIN", random.Random(13),
            curriculum_scope="scope", return_metadata=True)

        self.assertEqual(key, winner)
        self.assertEqual(policy, teacher["strategies"][winner])
        self.assertEqual(metadata["selection_reason"], "PROVEN_RETAINED_CONTEXT")
        self.assertEqual(set(teacher["strategies"]), before)

    def test_rejection_pressure_resumes_breeding_after_retained_policy_is_checkpoint_retired(self):
        import bilqis_mlx.compatibility.historical_teacher_policy as policy_engine
        teacher = strategy_population_teacher(count=24)
        winner = "policy-007"
        winner_effective = _effective_policy_key(teacher["strategies"][winner])
        context_key = "C.ADD|MAIN|scope"
        checkpoint = "a" * 64
        channel = teacher["causal_experiment"]
        channel["contexts"][context_key] = {
            winner: {
                "trials": 1, "reward_sum": -.06, "unsafe": 0,
                "retained": 1, "latest": -.06, "no_target_gain_streak": 0,
            },
        }
        channel["capability_stagnation"] = {
            "C.ADD|scope": {
                "rejection_streak": 8, "no_target_gain_streak": 0,
                "attempts_since_retained": 8, "total_rejections": 8,
                "total_retained": 1, "current_rejection_reasons": {},
            },
        }
        # The existing same-student rule is the exploitation bound: after four
        # unretained uses, the proven effective policy leaves the active set.
        channel["student_policy_epoch"] = {
            "student_sha256": checkpoint,
            "contexts": {context_key: {}},
            "unretained_contexts": {
                context_key: {winner_effective: 4},
            },
        }

        _key, _policy, metadata = contextual_pick(
            policy_engine, teacher, "C.ADD", "MAIN", random.Random(13),
            curriculum_scope="scope", return_metadata=True,
            student_checkpoint_sha256=checkpoint)

        self.assertEqual(metadata["selection_reason"], "FRESH_MUTATED_CHALLENGER")
        self.assertGreaterEqual(
            metadata["checkpoint_retired_effective_strategy_count"], 1)
