import random
import unittest
from types import SimpleNamespace
from unittest import mock

from bilqis_mlx.learning.teacher_strategy_population import effective_strategy_inventory
from bilqis_mlx.learning.tests.teacher_strategy.support import teacher_fixture

_teacher = teacher_fixture


class TeacherVNextReplayTests(unittest.TestCase):
    def test_every_fourth_candidate_can_select_supported_active_policy(self):
        from bilqis_mlx.learning.teacher_vnext_replay import select_canary

        teacher, strong, weak = teacher_fixture()
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

        teacher, strong, weak = teacher_fixture()
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

        teacher, strong, _weak = teacher_fixture()
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

        teacher, strong, weak = teacher_fixture()
        legacy_metadata = {
            "diagnostic_context_consumed": True,
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
        self.assertTrue(metadata["legacy_diagnostic_context_consumed"])
        self.assertFalse(metadata["diagnostic_context_consumed"])
        self.assertTrue(metadata["vnext_canary"]["actual_authority_changed"])

    def test_runtime_selector_does_not_override_portable_retained_challenger(self):
        from bilqis_mlx.runtime import visits

        teacher, strong, weak = teacher_fixture()
        portable_metadata = {
            "diagnostic_context_consumed": False,
            "diagnostic_context_key": None,
            "selection_reason": "PORTABLE_RETAINED_CHALLENGER",
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
                              portable_metadata)):
            key, policy, metadata = visits._select_visit_policy(
                object(), teacher, "C.ADD", school, random.Random(7), object(),
                "factory/7", {}, "C")

        self.assertEqual(key, "p-weak")
        self.assertEqual(policy, teacher["strategies"]["p-weak"])
        self.assertEqual(metadata["selection_reason"],
                         "PORTABLE_RETAINED_CHALLENGER")
        self.assertEqual(metadata["vnext_canary"]["status"],
                         "BYPASSED_PORTABLE_RETAINED_CHALLENGER")

    def test_shadow_policy_waits_until_step_eight_and_preserves_late_recovery(self):
        from bilqis_mlx.learning.teacher_multifidelity import (
            DEFAULT_SHADOW_POLICY, active_rungs, evaluate_shadow,
            target_correct_delta,
        )

        self.assertEqual(target_correct_delta(.5, .53125, 32), 1.)
        self.assertEqual(target_correct_delta(.5, .5625, 32), 2.)

        self.assertEqual(active_rungs(DEFAULT_SHADOW_POLICY, 16), (2, 4, 8, 16))
        self.assertEqual(active_rungs(DEFAULT_SHADOW_POLICY, 12), (2, 4, 8, 12))
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

    def test_activation_receipt_reports_false_continue_quality(self):
        from bilqis_mlx.learning.teacher_multifidelity import (
            DEFAULT_SHADOW_POLICY, evaluate_shadow, qualify_activation,
        )

        false_continue = evaluate_shadow(
            DEFAULT_SHADOW_POLICY,
            probes=((2, 1), (4, 1), (8, 1), (12, 1)),
            final_retained=False, full_budget_steps=12)
        would_stop = evaluate_shadow(
            DEFAULT_SHADOW_POLICY,
            probes=((2, 0), (4, 0), (8, 0), (12, 0)),
            final_retained=False, full_budget_steps=12)
        receipt = qualify_activation((false_continue, would_stop))

        self.assertEqual(receipt["continue_recommendations"], 1)
        self.assertEqual(receipt["false_continues"], 1)
        self.assertEqual(receipt["false_continue_rate"], 1.0)
        self.assertEqual(receipt["retained_would_kill"], 0)
        self.assertEqual(receipt["status"], "NOT_QUALIFIED")




if __name__ == "__main__":
    unittest.main()
