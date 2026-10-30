from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.factory.curriculum.capability_identity import (
    CapabilityIdentityInput, StableCapabilityIdentity,
    bind_stable_capability_identity, stable_capability_id,
)
from bilqis_mlx.semantics.foundation.core import Signature


class CapabilityIdentityTests(unittest.TestCase):
    def test_semantic_family_signature_and_answer_modality_define_identity(self):
        identity = bind_stable_capability_identity(
            "boolean_composition", Signature(("Boolean", "Boolean"), "Boolean"),
            ("BOOLEAN",))
        self.assertTrue(identity.capability_id.startswith("cap:"))
        self.assertEqual(len(identity.capability_id), 68)
        self.assertEqual(identity.capability_id, stable_capability_id(identity.identity))

    def test_grade_provider_source_path_and_root_ordinal_are_not_identity_inputs(self):
        identity = CapabilityIdentityInput(
            "numeric_composition", Signature(("Number", "Number"), "Number"),
            ("INTEGER",))
        baseline = stable_capability_id(identity)
        # These execution/placement facts are intentionally not accepted arguments.
        placements = (
            {"grade": "C", "provider": "mlx", "source": "row:1", "ordinal": 1},
            {"grade": "Z", "provider": "cpu", "source": "row:999", "ordinal": 999},
        )
        self.assertEqual({stable_capability_id(identity) for _ in placements}, {baseline})

    def test_semantic_change_changes_identity(self):
        base = CapabilityIdentityInput(
            "numeric_composition", Signature(("Number", "Number"), "Number"),
            ("INTEGER",))
        variants = (
            replace(base, family_id="boolean_composition"),
            replace(base, signature=Signature(("Number",), "Number")),
            replace(base, answer_kinds=("INTEGER", "SEMANTIC_TOKEN")),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertNotEqual(stable_capability_id(base), stable_capability_id(variant))

    def test_forged_digest_and_noncanonical_modalities_fail(self):
        base = CapabilityIdentityInput(
            "boolean_composition", Signature(("Boolean",), "Boolean"),
            ("BOOLEAN",))
        with self.assertRaises(ValueError):
            StableCapabilityIdentity("cap:" + "0" * 64, base)
        for answer_kinds in ((), ("B", "A"), ("A", "A")):
            with self.subTest(answer_kinds=answer_kinds), self.assertRaises(ValueError):
                CapabilityIdentityInput(
                    "boolean_composition", Signature(("Boolean",), "Boolean"),
                    answer_kinds)


if __name__ == "__main__":
    unittest.main()
