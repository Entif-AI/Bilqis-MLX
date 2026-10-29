"""C08.1 pure resource and gradient-accumulation contract witnesses."""
from __future__ import annotations

from dataclasses import replace
import math
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, bamf_parameter_census,
)
from bilqis_mlx.runtime.atlas_training_adapter import (
    BamfDeliveryProvenance, BamfModelInput, BamfTarget, BamfTrainingRow,
)
from bilqis_mlx.runtime.atlas_resources import (
    BackendStepReceipt, FrameStats, GradientChunk, MemoryBudget, ResourceRow,
    accumulate_gradients, apply_one_adamw_step, estimate_row_activation_bytes,
    indices_for_plan, plan_microbatches,
)


GENERATION = "fixture:retained-generation"


def _rows(count: int, *, positions: int = 64,
          raw_frame_length: int | None = None) -> tuple[ResourceRow, ...]:
    return tuple(ResourceRow(
        row_id="row:" + str(index),
        frame_stats=FrameStats(
            compiled_positions=positions,
            frame_lengths=(raw_frame_length or positions,),
            constituent_expansions=max(1, positions // 4),
            depth_summaries=3,
        ),
        target_decisions=2,
        optimizer_step_seed=73,
        generation_binding=GENERATION,
    ) for index in range(count))


class AtlasResourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topology = ModelTopologySpecV2()
        cls.extents = GenerationExtents(
            1, 1, "a" * 64, "b" * 64, "c" * 64)
        cls.census = bamf_parameter_census(cls.topology, cls.extents)
        cls.budget = MemoryBudget(census=cls.census)

    def test_short_rows_start_at_32_and_preserve_exact_logical_batch(self):
        rows = _rows(32)
        plan = plan_microbatches(rows, self.topology, self.budget)
        self.assertEqual(plan.microbatch_size, 32)
        self.assertEqual(indices_for_plan(plan), (tuple(range(32)),))
        self.assertEqual(plan.logical_row_ids,
                         tuple(row.row_id for row in rows))
        self.assertEqual(plan.optimizer_step_seed, 73)
        self.assertEqual(plan.generation_binding, GENERATION)
        self.assertEqual(plan.topology_digest, self.topology.digest)
        self.assertLessEqual(plan.estimated_peak_bytes,
                             self.budget.allocation_bytes)
        self.assertEqual(plan, plan_microbatches(
            rows, self.topology, self.budget))

    def test_c02_delivered_row_identity_is_bound_to_compiler_frame_statistics(self):
        target = BamfTarget("binary", "TRUE", 1, True)
        delivered = BamfTrainingRow(
            BamfModelInput(
                prefix=None, features=(), eligibility_digest="e" * 64,
                answer_plan=(
                    ("generation_binding", GENERATION),
                    ("maximum_decisions", 2),
                )),
            target, None,
            BamfDeliveryProvenance(
                row_id="source:actual", source_id="source:fixture",
                capability_id="capability:fixture", operation_id=None,
                teacher_strategy=(), requested_count=1,
                delivered_count=1, rehearsal=None, optimizer_step_seed=73),
        )
        stats = _rows(1)[0].frame_stats
        resource = ResourceRow.from_training_row(
            delivered, stats, generation_binding=GENERATION)
        self.assertEqual(resource.row_id, "source:actual")
        self.assertEqual(resource.frame_stats, stats)
        self.assertEqual(resource.target_decisions, 2)
        with self.assertRaises(BilqisError) as caught:
            ResourceRow.from_training_row(
                delivered, stats, generation_binding="foreign:generation")
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C08_DELIVERY_PROFILE_INVALID")

    def test_full_1024_position_rows_start_at_four_or_fewer(self):
        rows = _rows(8, positions=1022, raw_frame_length=1024)
        plan = plan_microbatches(rows, self.topology, self.budget)
        self.assertEqual(plan.microbatch_size, 4)
        self.assertEqual(indices_for_plan(plan),
                         ((0, 1, 2, 3), (4, 5, 6, 7)))
        self.assertEqual(sum(map(len, plan.groups)), 8)

    def test_budget_forces_deterministic_two_then_safe_batch_one_failure(self):
        rows = _rows(8)
        row_bytes = estimate_row_activation_bytes(rows[0], self.topology)
        resident = self.budget.resident_bytes
        constrained = replace(
            self.budget,
            allocation_bytes=resident + 2 * row_bytes
            * self.budget.activation_safety_factor)
        plan = plan_microbatches(rows, self.topology, constrained)
        self.assertEqual(plan.microbatch_size, 2)
        self.assertEqual(indices_for_plan(plan),
                         ((0, 1), (2, 3), (4, 5), (6, 7)))
        exhausted = replace(
            constrained,
            allocation_bytes=resident + row_bytes - 1)
        with self.assertRaises(BilqisError) as caught:
            plan_microbatches(rows, self.topology, exhausted)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C08_BUDGET_EXHAUSTED")

    def test_all_declared_microbatch_fallback_sizes_and_frame_components(self):
        rows = _rows(32)
        row_bytes = estimate_row_activation_bytes(rows[0], self.topology)
        for size in (16, 8, 4, 2, 1):
            with self.subTest(size=size):
                budget = replace(
                    self.budget,
                    allocation_bytes=(
                        self.budget.resident_bytes
                        + size * row_bytes
                        * self.budget.activation_safety_factor))
                plan = plan_microbatches(rows, self.topology, budget)
                self.assertEqual(plan.microbatch_size, size)
                self.assertEqual(tuple(
                    index for group in plan.groups for index in group),
                    tuple(range(32)))
        baseline = rows[0]
        bigger = replace(
            baseline, frame_stats=replace(
                baseline.frame_stats,
                frame_lengths=(128,),
                constituent_expansions=32,
                depth_summaries=6))
        self.assertGreater(
            estimate_row_activation_bytes(bigger, self.topology),
            estimate_row_activation_bytes(baseline, self.topology))

    def test_weighted_split_gradient_matches_unsplit_and_applies_one_step(self):
        rows = _rows(4)
        row_bytes = estimate_row_activation_bytes(rows[0], self.topology)
        constrained = replace(
            self.budget, allocation_bytes=(
                self.budget.resident_bytes + 2 * row_bytes
                * self.budget.activation_safety_factor))
        split = plan_microbatches(rows, self.topology, constrained)
        whole = plan_microbatches(rows, self.topology, self.budget)
        self.assertEqual(split.groups, ((0, 1), (2, 3)))
        chunks = (
            GradientChunk((0, 1), (1.0, 2.0), 0.25, 73, GENERATION),
            GradientChunk((2, 3), (3.0, 4.0), 0.75, 73, GENERATION),
        )
        split_grad = accumulate_gradients(split, chunks, clip_norm=1.0)
        whole_grad = accumulate_gradients(
            whole, (GradientChunk(
                (0, 1, 2, 3), (2.0, 3.0), 0.5, 73, GENERATION),),
            clip_norm=1.0)
        self.assertEqual(split_grad.gradient, whole_grad.gradient)
        self.assertAlmostEqual(split_grad.weighted_mean_loss, 0.5)
        self.assertAlmostEqual(
            split_grad.gradient[0], 2.0 / math.sqrt(13.0), places=7)
        self.assertAlmostEqual(
            split_grad.gradient[1], 3.0 / math.sqrt(13.0), places=7)
        calls = []

        def backend_apply(gradient, generation_binding, source_digest):
            calls.append((gradient, generation_binding, source_digest))
            return BackendStepReceipt(
                optimizer_steps_applied=1,
                generation_binding=generation_binding,
                source_digest=source_digest,
                gradient_digest=split_grad.gradient_digest,
                new_state_digest="f" * 64,
            )

        receipt = apply_one_adamw_step(split_grad, backend_apply)
        self.assertEqual(len(calls), 1)
        self.assertEqual(receipt.optimizer_steps_applied, 1)
        self.assertEqual(receipt.new_state_digest, "f" * 64)
        with self.assertRaises(BilqisError) as caught:
            apply_one_adamw_step(
                split_grad,
                lambda gradient, generation, source: replace(
                    receipt, gradient_digest="0" * 64))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C08_BACKEND_STEP_DRIFT")

    def test_wrong_generation_seed_or_group_rejects_before_backend_call(self):
        rows = _rows(4)
        plan = plan_microbatches(rows, self.topology, self.budget)
        valid = GradientChunk((0, 1, 2, 3), (1.0,), 0.5, 73, GENERATION)
        for bad in (
            replace(valid, optimizer_step_seed=74),
            replace(valid, generation_binding="foreign:generation"),
            replace(valid, row_indices=(0, 1, 2)),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(BilqisError):
                    accumulate_gradients(plan, (bad,), clip_norm=1.0)


if __name__ == "__main__":
    unittest.main()
