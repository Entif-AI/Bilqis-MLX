import random
import unittest
from types import SimpleNamespace
from unittest import mock

from bilqis_mlx.learning.teacher_strategy_population import (
    checkpoint_active_effective_strategy_keys,
    durable_policy_cooldown_status,
    effective_policy_key,
    effective_strategy_inventory,
    record_checkpoint_policy_outcome,
    sibling_cooldown_penalty,
)


def _teacher():
    strategies = {
        "p-strong": {"lr": 0.00013, "old": 8, "preview": 0,
                     "depth": 3, "contrast": 0.5, "distill": 0.15},
        "p-weak": {"lr": 0.00004, "old": 4, "preview": 0,
                   "depth": 1, "contrast": 0.0, "distill": 0.0},
        "p-other": {"lr": 0.00030, "old": 12, "preview": 0,
                    "depth": 1, "contrast": 0.0, "distill": 0.0},
    }
    strong = effective_policy_key(strategies["p-strong"])
    weak = effective_policy_key(strategies["p-weak"])
    return {
        "strategies": strategies,
        "causal_experiment": {
            "events": 11,
            "contexts": {
                "C.ADD|RECOVERY_1|factory/7": {
                    "p-strong": {
                        "trials": 16, "retained": 12, "reward_sum": 8.0,
                        "unsafe": 4, "no_target_gain_streak": 0,
                        "target_delta_sum": 24.0,
                        "protected_net_delta_sum": 0.0,
                        "worst_protected_loss_sum": 0.0,
                        "attempted_steps_sum": 160,
                    },
                    "p-weak": {
                        "trials": 16, "retained": 1, "reward_sum": -4.0,
                        "unsafe": 15, "no_target_gain_streak": 3,
                        "target_delta_sum": 3.0,
                        "protected_net_delta_sum": -8.0,
                        "worst_protected_loss_sum": 8.0,
                        "attempted_steps_sum": 256,
                    },
                },
            },
            "capability_stagnation": {},
        },
    }, strong, weak


class TeacherVNextReplayTests(unittest.TestCase):
    def test_durable_capability_cooldown_requires_two_failed_student_epochs_and_retention_clears(self):
        teacher, strong, _weak = _teacher()
        channel = teacher["causal_experiment"]
        capability_key = "C.ADD|factory/7"
        channel["capability_stagnation"] = {
            capability_key: {
                "total_rejections": 0, "total_retained": 0,
            },
        }
        context = "C.ADD|RECOVERY_1|factory/7"

        for sha in ("a" * 64, "b" * 64):
            for _ in range(4):
                channel["capability_stagnation"][capability_key]["total_rejections"] += 1
                record_checkpoint_policy_outcome(
                    channel, context, strong, sha,
                    no_target_gain=True, retained=False)
            status = durable_policy_cooldown_status(
                channel, "C.ADD", "factory/7", strong)
            if sha.startswith("a"):
                self.assertFalse(status["active"])

        self.assertTrue(status["active"])
        self.assertEqual(status["failed_student_epochs"], 2)
        self.assertEqual(status["remaining_capability_visits"], 8)
        inventory = effective_strategy_inventory(teacher)
        active, retired = checkpoint_active_effective_strategy_keys(
            teacher, "C",
            channel["contexts"][context], channel, context,
            tuple(inventory), inventory, "c" * 64)
        self.assertIn(strong, retired)
        self.assertNotIn(strong, active)
        self.assertGreater(
            sibling_cooldown_penalty(
                channel, "C.SUB", "factory/7", strong), 0.)
        self.assertFalse(durable_policy_cooldown_status(
            channel, "C.SUB", "factory/7", strong)["active"])

        channel["capability_stagnation"][capability_key]["total_retained"] += 1
        record_checkpoint_policy_outcome(
            channel, context, strong, "c" * 64,
            no_target_gain=False, retained=True)
        self.assertFalse(durable_policy_cooldown_status(
            channel, "C.ADD", "factory/7", strong)["active"])

    def test_every_fourth_candidate_can_select_supported_active_policy(self):
        from bilqis_mlx.learning.teacher_vnext_replay import select_canary

        teacher, strong, weak = _teacher()
        inventory = effective_strategy_inventory(teacher)

        decision = select_canary(
            teacher,
            capability="C.ADD",
            phase="RECOVERY_1",
            curriculum_scope="factory/7",
            candidate_ordinal=12,
            rng=random.Random(7),
            active_effective_policy_keys=(strong, weak),
            inventory=inventory,
        )

        self.assertEqual(decision["status"], "SELECTED")
        self.assertTrue(decision["actual_authority_changed"])
        self.assertEqual(decision["selected_effective_policy_key"], strong)
        self.assertEqual(decision["policy_key"], "p-strong")
        self.assertGreaterEqual(decision["evidence"]["trials"], 8)
        self.assertGreaterEqual(decision["evidence"]["retained"], 1)

    def test_canary_is_bounded_by_cadence_and_current_active_set(self):
        from bilqis_mlx.learning.teacher_vnext_replay import select_canary

        teacher, strong, weak = _teacher()
        inventory = effective_strategy_inventory(teacher)

        not_scheduled = select_canary(
            teacher, capability="C.ADD", phase="RECOVERY_1",
            curriculum_scope="factory/7", candidate_ordinal=11,
            rng=random.Random(7), active_effective_policy_keys=(strong, weak),
            inventory=inventory)
        self.assertEqual(not_scheduled["status"], "NOT_SCHEDULED")
        self.assertFalse(not_scheduled["actual_authority_changed"])

        weak_only = select_canary(
            teacher, capability="C.ADD", phase="RECOVERY_1",
            curriculum_scope="factory/7", candidate_ordinal=12,
            rng=random.Random(7), active_effective_policy_keys=(weak,),
            inventory=inventory)
        self.assertEqual(weak_only["status"], "SELECTED")
        self.assertEqual(weak_only["selected_effective_policy_key"], weak)
        self.assertNotEqual(weak_only["selected_effective_policy_key"], strong)

    def test_underpowered_canary_falls_back_without_authority(self):
        from bilqis_mlx.learning.teacher_vnext_replay import select_canary

        teacher, strong, _weak = _teacher()
        teacher["causal_experiment"]["contexts"]["C.ADD|RECOVERY_1|factory/7"][
            "p-strong"]["trials"] = 3
        inventory = effective_strategy_inventory(teacher)

        decision = select_canary(
            teacher, capability="C.ADD", phase="RECOVERY_1",
            curriculum_scope="factory/7", candidate_ordinal=12,
            rng=random.Random(7), active_effective_policy_keys=(strong,),
            inventory=inventory)

        self.assertEqual(decision["status"], "FALLBACK_UNDERPOWERED")
        self.assertFalse(decision["actual_authority_changed"])

    def test_runtime_selector_grants_bounded_canary_authority(self):
        from bilqis_mlx.runtime import visits

        teacher, strong, weak = _teacher()
        legacy_metadata = {
            "diagnostic_context_consumed": False,
            "diagnostic_context_key": None,
            "selection_reason": "INHERITED_FALLBACK",
            "selection_policy": "bilqis.mlx.teacher-selection/349-replay-v1",
            "active_effective_strategy_keys": [strong, weak],
        }
        school = SimpleNamespace(
            stage="RECOVERY_1",
            current_student=SimpleNamespace(sha256="a" * 64),
        )
        with mock.patch.object(
                visits._learning_learning_experiment, "contextual_pick",
                return_value=("p-weak", teacher["strategies"]["p-weak"],
                              legacy_metadata)):
            key, policy, metadata = visits._select_visit_policy(
                object(), teacher, "C.ADD", school, random.Random(7), object(),
                "factory/7", {}, "C")

        self.assertEqual(key, "p-strong")
        self.assertEqual(policy, teacher["strategies"]["p-strong"])
        self.assertEqual(metadata["selection_reason"], "VNEXT_CANARY")
        self.assertEqual(metadata["legacy_policy_key"], "p-weak")
        self.assertTrue(metadata["vnext_canary"]["actual_authority_changed"])

    def test_shadow_policy_waits_until_step_eight_and_preserves_late_recovery(self):
        from bilqis_mlx.learning.teacher_multifidelity import (
            DEFAULT_SHADOW_POLICY, active_rungs, evaluate_shadow,
        )

        self.assertEqual(active_rungs(DEFAULT_SHADOW_POLICY, 16), (2, 4, 8, 16))
        recovered = evaluate_shadow(
            DEFAULT_SHADOW_POLICY,
            probes=((2, 0), (4, 1), (8, 0), (16, 2)),
            final_retained=True, full_budget_steps=16)
        self.assertIsNone(recovered["first_would_stop_step"])
        self.assertFalse(recovered["false_kill"])

        inert_until_eight = evaluate_shadow(
            DEFAULT_SHADOW_POLICY,
            probes=((2, 0), (4, 0), (8, 0), (16, 2)),
            final_retained=True, full_budget_steps=16)
        self.assertEqual(inert_until_eight["first_would_stop_step"], 8)
        self.assertTrue(inert_until_eight["false_kill"])
        self.assertEqual(inert_until_eight["shadow_steps_saved"], 8)


if __name__ == "__main__":
    unittest.main()
