"""Issue #1578 accelerator-work-unit qualification contracts."""
from __future__ import annotations

import unittest

from bilqis_mlx.runtime.accelerator_work_units import (
    C08_EQUIVALENCE_ATOL,
    DEFAULT_LOGICAL_BATCH_SIZE,
    PHYSICAL_CAPS,
    classify_physical_row_work_unit,
    equal_row_budget_schedule,
    physical_result_contract_equivalent,
)


class AcceleratorWorkUnitQualificationTests(unittest.TestCase):
    def test_default_logical_batch_cannot_claim_more_than_32_rows_per_launch(self):
        self.assertEqual(DEFAULT_LOGICAL_BATCH_SIZE, 32)
        self.assertEqual(PHYSICAL_CAPS, (8, 16, 32))
        qualified = classify_physical_row_work_unit(
            logical_batch_size=DEFAULT_LOGICAL_BATCH_SIZE,
            rows_per_launch=32,
        )
        semantic_change = classify_physical_row_work_unit(
            logical_batch_size=DEFAULT_LOGICAL_BATCH_SIZE,
            rows_per_launch=64,
        )
        self.assertEqual(qualified.status, "SEMANTICS_PRESERVING")
        self.assertFalse(qualified.learning_policy_change)
        self.assertEqual(semantic_change.status, "SEMANTIC_CHANGE_REQUIRED")
        self.assertTrue(semantic_change.learning_policy_change)

    def test_equal_budget_learning_schedule_keeps_row_presentations_fixed(self):
        schedule = equal_row_budget_schedule(row_budget=96)
        self.assertEqual(
            tuple(item.logical_batch_size for item in schedule),
            (8, 16, 24, 32),
        )
        self.assertEqual(
            tuple(item.optimizer_steps for item in schedule),
            (12, 6, 4, 3),
        )
        self.assertTrue(all(item.row_presentations == 96 for item in schedule))
        self.assertTrue(all(item.learning_policy_experiment for item in schedule[:-1]))
        self.assertFalse(schedule[-1].learning_policy_experiment)

    def test_equal_budget_schedule_rejects_non_divisible_budget(self):
        with self.assertRaises(ValueError):
            equal_row_budget_schedule(row_budget=100)

    def test_physical_witness_uses_c08_fp32_tolerance_not_bitwise_state_hash(self):
        results = [
            {
                "logical_batch_size": 32,
                "optimizer_step": 1,
                "loss_total": 0.695968508720398,
                "optimizer_state_sha256": "a" * 64,
            },
            {
                "logical_batch_size": 32,
                "optimizer_step": 1,
                "loss_total": 0.6959685683250427,
                "optimizer_state_sha256": "b" * 64,
            },
        ]
        self.assertLess(
            abs(results[0]["loss_total"] - results[1]["loss_total"]),
            C08_EQUIVALENCE_ATOL,
        )
        self.assertTrue(physical_result_contract_equivalent(results))

    def test_physical_witness_rejects_loss_outside_c08_tolerance(self):
        self.assertFalse(physical_result_contract_equivalent([
            {"logical_batch_size": 32, "optimizer_step": 1, "loss_total": 1.0},
            {
                "logical_batch_size": 32,
                "optimizer_step": 1,
                "loss_total": 1.0 + 2 * C08_EQUIVALENCE_ATOL,
            },
        ]))


if __name__ == "__main__":
    unittest.main()
