"""Evolution."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, _effective_policy_key, contextual_pick, patch,
    random,
)


class Evolution4Tests(CausalTeacherExperimentTests):
    def test_scope_revision_retries_proven_capability_policy_before_fresh_search(self):
        import bilqis_mlx.compatibility.historical_teacher_policy as policy_engine

        winner = {
            "old": 8, "preview": 0, "depth": 3, "contrast": 0.,
            "lr": .00004, "distill": .35,
        }
        current = dict(winner, lr=.00013)
        winner_effective = _effective_policy_key(winner)
        teacher = {
            "strategies": {"winner": winner, "current": current},
            "global_stats": {
                "winner": {"trials": 4, "reward_sum": .2,
                           "reward_ema": .05, "latest": .05},
                "current": {"trials": 8, "reward_sum": -.8,
                            "reward_ema": -.1, "latest": -.1},
            },
            "grade_stats": {"C": {
                "winner": {"trials": 4, "reward_sum": .2,
                           "reward_ema": .05, "latest": .05},
                "current": {"trials": 8, "reward_sum": -.8,
                            "reward_ema": -.1, "latest": -.1},
            }},
            "events": 20, "mutations": 0,
            "causal_experiment": {
                "version": "bilqis.mlx.causal-teacher-experiment/v1",
                "events": 12, "negative_archetypes": [],
                "contexts": {
                    "C.ADD|MAIN|release/10": {
                        "winner": {"trials": 4, "reward_sum": .2,
                                   "unsafe": 0, "retained": 2,
                                   "latest": .05, "no_target_gain_streak": 0},
                    },
                    "C.ADD|MAIN|release/4": {
                        "current": {"trials": 4, "reward_sum": -.8,
                                    "unsafe": 0, "retained": 0,
                                    "latest": -.2, "no_target_gain_streak": 4},
                    },
                },
                "capability_stagnation": {
                    "C.ADD|release/4": {
                        "rejection_streak": 4, "no_target_gain_streak": 4,
                        "attempts_since_retained": 4, "total_rejections": 4,
                        "total_retained": 0,
                        "current_rejection_reasons": {"NO_MEASURABLE_TARGET_GAIN": 4},
                    },
                },
                "strategy_births": {
                    winner_effective: {
                        "origin_capability": "C.ADD", "origin_grade": "C",
                        "curriculum_scope": "release/10",
                        "parent_policy_key": "current",
                        "parent_effective_policy_key": _effective_policy_key(current),
                        "parent_basis": "CAPABILITY_RETAINED",
                        "changed_fields": ["lr"], "birth_event": 3,
                        "proven_retained": True,
                    },
                },
            },
        }

        # Both effective knob values already exist, so the old code cannot
        # escape by minting a third policy. The proven /10 winner must instead
        # get one fresh trial under /4 without importing its old reward record.
        with patch.object(policy_engine, "KNOBS", {"lr": [.00004, .00013]}):
            key, _policy, metadata = contextual_pick(
                policy_engine, teacher, "C.ADD", "MAIN", random.Random(7),
                curriculum_scope="release/4", return_metadata=True)

        self.assertEqual(key, "winner")
        self.assertEqual(metadata["selection_reason"],
                         "PORTABLE_RETAINED_CHALLENGER")
        self.assertNotIn(
            "winner", teacher["causal_experiment"]["contexts"][
                "C.ADD|MAIN|release/4"])
