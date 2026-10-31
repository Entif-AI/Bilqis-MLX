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
