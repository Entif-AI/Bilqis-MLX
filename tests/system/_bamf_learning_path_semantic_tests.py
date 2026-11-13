"""C13.1 append-only semantic-delta conservation contracts."""
from types import SimpleNamespace
import unittest

import numpy as np

from scripts.bamf.c13 import delivery_runtime


class BamfLearningPathSemanticDeltaTests(unittest.TestCase):
    def test_c13_semantic_delta_composition_preserves_prior_optimizer_prefix(self):
        RowAge = __import__(
            "bilqis_mlx.learning._retention._atlas_plasticity_base",
            fromlist=["IdentityRowAge"],
        ).IdentityRowAge
        parent_policy = SimpleNamespace(row_ages=(RowAge(0, 0, 7),))
        current_policy = SimpleNamespace(
            row_ages=(RowAge(0, 0, 7), RowAge(0, 1, 0)))
        before = np.arange(6, dtype=np.float32).reshape(2, 3)
        after = np.vstack((before, np.asarray([[11, 12, 13]], dtype=np.float32)))
        zero_before = np.zeros_like(before)
        zero_after = np.vstack((zero_before, np.zeros((1, 3), dtype=np.float32)))
        counts_before = np.zeros_like(before, dtype=np.int64)
        counts_after = np.vstack((counts_before, np.zeros((1, 3), dtype=np.int64)))

        def student(generation, policy, params, m, v, counts):
            optimizer = SimpleNamespace(
                parameters={"identity.bank.0": params},
                m={"identity.bank.0": m},
                v={"identity.bank.0": v},
                update_counts={"identity.bank.0": counts},
            )
            return SimpleNamespace(
                generation=generation,
                retained_state=SimpleNamespace(
                    optimizer_step=9, optimizer=optimizer, policy=policy))

        parent = student(4, parent_policy, before, zero_before, zero_before, counts_before)
        current = student(5, current_policy, after, zero_after, zero_after, counts_after)
        receipt = delivery_runtime.record_append_only_semantic_delta(
            parent, current, "new.semantic")
        self.assertEqual(receipt.parent_generation, 4)
        self.assertEqual(receipt.current_generation, 5)
        self.assertEqual(receipt.optimizer_step, 9)
        self.assertEqual(receipt.new_rows, ((0, 1),))


__all__ = ("BamfLearningPathSemanticDeltaTests",)
