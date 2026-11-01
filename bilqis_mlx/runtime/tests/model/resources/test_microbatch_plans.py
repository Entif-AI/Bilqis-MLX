"""C08.1 pure resource and gradient-accumulation contract witnesses."""
from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
from bilqis_mlx.runtime.atlas_memory_retry import (
    OOMReceipt, RestorationReceipt, RetryState, RetryStatus,
    handle_oom, snapshot_mlx_memory,
)
from bilqis_mlx.runtime.disk import (
    RETAINED_DISK_RESERVE_BYTES, assert_bundle_headroom,
    estimate_next_bundle_bytes,
)
from bilqis_mlx.runtime.source_prefetch import (
    SCHEMA as SOURCE_PREFETCH_SCHEMA,
    freeze_source_packet, source_prefetch_pool,
)


GENERATION = "fixture:retained-generation"


from bilqis_mlx.runtime.tests.model.resources.helpers import AtlasResourcesFixture, GENERATION, _rows

class AtlasResourcesTests(AtlasResourcesFixture):
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
            delivered, stats, generation_binding=GENERATION, delivered_content_sha256="e" * 64)
        self.assertEqual(resource.row_id, "source:actual")
        self.assertEqual(resource.frame_stats, stats)
        self.assertEqual(resource.target_decisions, 2)
        changed = ResourceRow.from_training_row(
            replace(delivered, model_input=replace(delivered.model_input, eligibility_digest='f' * 64),
                    target=replace(target, value='changed')),
            stats, generation_binding=GENERATION, delivered_content_sha256='e' * 64)
        self.assertNotEqual(resource, changed)
        original_plan = plan_microbatches((resource,), self.topology, self.budget)
        state = RetryState.start(original_plan, retained_candidate_digest='a' * 64,
                                 optimizer_snapshot_digest='b' * 64)
        failure = OOMReceipt('oom:changed-content', original_plan.microbatch_size,
            original_plan.source_digest, GENERATION, 73, 50 * 1024**3, 0, 720, 'MemoryError')
        restored = []
        def restore(candidate, optimizer, generation):
            restored.append(candidate)
            return RestorationReceipt(candidate, optimizer, generation, True)
        with self.assertRaises(BilqisError) as caught:
            handle_oom(state, failure, (changed,), self.topology, self.budget, restore=restore)
        self.assertEqual(caught.exception.context['reason'], 'BAMF_C08_OOM_DELIVERY_REPLAY_DRIFT')
        self.assertEqual(restored, ['a' * 64])
        for field in ('training_row_sha256', 'delivered_content_sha256'):
            changed_hash = replace(resource, **{field: '0' * 64})
            with self.subTest(field=field), self.assertRaises(BilqisError) as caught:
                handle_oom(state, failure, (changed_hash,), self.topology, self.budget, restore=restore)
            self.assertEqual(caught.exception.context['reason'], 'BAMF_C08_OOM_DELIVERY_REPLAY_DRIFT')


        self.assertNotEqual(plan_microbatches((resource,), self.topology, self.budget).source_digest,
                            plan_microbatches((changed,), self.topology, self.budget).source_digest)

        with self.assertRaises(BilqisError) as caught:
            ResourceRow.from_training_row(
                delivered, stats, generation_binding="foreign:generation", delivered_content_sha256="e" * 64)
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
