"""Replay policy."""
import unittest

from bilqis_mlx.learning.tests.test_fragile_replay import (
    _direct_u7c_replay_rows, _v2_replay_rows, fragile_preservation_capabilities, screen_replay,
    select_preservation_rows, select_structural_preservation_rows, structural_signature,
)


class ReplayPolicyTests(unittest.TestCase):
    def test_retention_profile_owns_immutable_fragile_source_policy(self):
        from dataclasses import FrozenInstanceError
        from bilqis_mlx.profiles.retention import FragilePreservationPolicy, fragile_preservation_policy
        policy = fragile_preservation_policy()
        self.assertIsInstance(policy, FragilePreservationPolicy)
        self.assertEqual(policy.capabilities, ("B.OR", "B.XOR"))
        self.assertIs(fragile_preservation_capabilities(), policy.capabilities)
        self.assertEqual(policy.per_capability_target, 4)
        self.assertEqual(policy.source_selector, "bilqis.mlx.grade-b-u7c-runtime-sampler/v3")
        with self.assertRaises(FrozenInstanceError):
            policy.per_capability_target = 8
        for capabilities, target, selector in ((["B.OR"], 4, "source"),
                (("B.OR", "B.OR"), 4, "source"), (("",), 4, "source"),
                (("B.OR",), True, "source"), (("B.OR",), 0, "source"),
                (("B.OR",), 4, "")):
            with self.subTest(capabilities=capabilities, target=target, selector=selector), \
                    self.assertRaises(ValueError):
                FragilePreservationPolicy(capabilities, target, selector)

    def test_generic_selection_uses_source_callbacks_for_non_boolean_shapes(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from bilqis_mlx.learning import fragile_replay
        policy = SimpleNamespace(
            is_exact=lambda row: False,
            pattern_counts=lambda *args, **kwargs: {("alpha",): 1},
            row_pattern=lambda row: (row["shape"],), eligible=lambda row: True,
            answer_values=("OK", "BAD"), signature=lambda row: (row["capability"], row["shape"]),
            matching_keys=lambda signature: (signature,))
        row = {"id": "synthetic", "capability": "X", "gold": "OK", "tokens": [1], "shape": "alpha"}
        with patch.object(fragile_replay, "_source_policy", return_value=policy):
            self.assertEqual(select_preservation_rows([row]), (row,))
            self.assertEqual(select_structural_preservation_rows(
                [row], [row], rotation=0, limit=1), (row,))
            self.assertEqual(screen_replay((row,), {"synthetic": "OK"},
                {"synthetic": "BAD"}, "c" * 64)["regressions"],
                [{"id": "synthetic", "capability": "X"}])

    def test_source_policy_owns_fragile_truth_and_structure_callbacks(self):
        from bilqis_mlx.source_adapters.school import fragile_source_policy
        from bilqis_mlx.profiles.retention import fragile_preservation_policy
        policy = fragile_source_policy(fragile_preservation_policy().source_selector)
        direct = _direct_u7c_replay_rows()[0]
        historical = _v2_replay_rows()[0]
        self.assertTrue(policy.is_exact(direct))
        self.assertFalse(policy.is_exact(historical))
        self.assertEqual(policy.signature(direct), structural_signature(direct))
        self.assertTrue(policy.verify_row(direct, direct["capability"]))
        self.assertTrue(policy.verify_row(historical, historical["capability"]))
        self.assertFalse(policy.verify_row({**direct, "gold": "wrong"}, direct["capability"]))
        self.assertEqual(policy.pattern_counts("B.OR", _direct_u7c_replay_rows(), each=4),
                         {(False, False): 2, (False, True): 1, (True, False): 1})
        with self.assertRaisesRegex(ValueError, "FRAGILE_PRESERVATION_SOURCE_POLICY_UNKNOWN"):
            fragile_source_policy("unadmitted.source")
