"""Structural test shard from test_atlas_resources.py; assertions preserved."""
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
from bilqis_mlx.runtime.tests.model.test_atlas_resources_helpers import (GENERATION, _rows)

class AtlasResourcesTests(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.topology = ModelTopologySpecV2()
            cls.extents = GenerationExtents(
                1, 1, "a" * 64, "b" * 64, "c" * 64)
            cls.census = bamf_parameter_census(cls.topology, cls.extents)
            cls.budget = MemoryBudget(census=cls.census)

        def test_one_oom_retry_preserves_rows_seed_and_parent_then_exhausts_safely(self):
            rows = _rows(32)
            plan = plan_microbatches(rows, self.topology, self.budget)
            state = RetryState.start(
                plan, retained_candidate_digest="a" * 64,
                optimizer_snapshot_digest="b" * 64)
            restores = []

            def restore(candidate_digest, optimizer_digest, generation):
                restores.append((candidate_digest, optimizer_digest, generation))
                return RestorationReceipt(
                    candidate_digest, optimizer_digest, generation,
                    restored=True)

            def oom(for_plan, attempt):
                return OOMReceipt(
                    failure_id="oom:" + str(attempt),
                    failed_microbatch_size=for_plan.microbatch_size,
                    source_digest=for_plan.source_digest,
                    generation_binding=for_plan.generation_binding,
                    optimizer_step_seed=for_plan.optimizer_step_seed,
                    peak_allocated_bytes=50 * 1024**3,
                    cache_bytes=1024,
                    observed_at=720 + attempt,
                    exception_class="MemoryError",
                )

            retry = handle_oom(
                state, oom(plan, 0), rows, self.topology, self.budget,
                restore=restore)
            self.assertEqual(retry.status, RetryStatus.RETRY_PENDING)
            self.assertEqual(retry.current_plan.microbatch_size, 16)
            self.assertEqual(retry.current_plan.source_digest, plan.source_digest)
            self.assertEqual(retry.current_plan.logical_row_ids,
                             plan.logical_row_ids)
            self.assertEqual(retry.current_plan.optimizer_step_seed, 73)
            self.assertEqual(retry.retained_candidate_digest, "a" * 64)
            self.assertEqual(retry.optimizer_snapshot_digest, "b" * 64)
            exhausted = handle_oom(
                retry, oom(retry.current_plan, 1), rows,
                self.topology, self.budget, restore=restore)
            self.assertEqual(exhausted.status, RetryStatus.EXHAUSTED)
            self.assertIsNone(exhausted.current_plan)
            self.assertEqual(len(exhausted.failures), 2)
            self.assertEqual(len(restores), 2)
            self.assertEqual(restores[0],
                             ("a" * 64, "b" * 64, GENERATION))
            self.assertEqual(state.status, RetryStatus.PLANNED)
            restored_before_reject = []

            def restore_then_reject(candidate, optimizer, generation):
                restored_before_reject.append(candidate)
                return RestorationReceipt(candidate, optimizer, generation, True)

            with self.assertRaises(BilqisError) as caught:
                handle_oom(
                    state, replace(oom(plan, 0), source_digest="0" * 64),
                    rows, self.topology, self.budget,
                    restore=restore_then_reject)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C08_OOM_SOURCE_DRIFT")
            self.assertEqual(restored_before_reject, ["a" * 64])

        def test_batch_one_oom_restores_parent_without_speculative_second_attempt(self):
            rows = _rows(2)
            row_bytes = estimate_row_activation_bytes(rows[0], self.topology)
            budget = replace(
                self.budget, allocation_bytes=(
                    self.budget.resident_bytes + row_bytes
                    * self.budget.activation_safety_factor))
            plan = plan_microbatches(rows, self.topology, budget)
            self.assertEqual(plan.microbatch_size, 1)
            state = RetryState.start(
                plan, retained_candidate_digest="a" * 64,
                optimizer_snapshot_digest="b" * 64)
            failure = OOMReceipt(
                "oom:batch1", 1, plan.source_digest, GENERATION, 73,
                50 * 1024**3, 0, 730, "MemoryError")
            restored = []

            def restore(candidate, optimizer, generation):
                restored.append(candidate)
                return RestorationReceipt(candidate, optimizer, generation, True)

            exhausted = handle_oom(
                state, failure, rows, self.topology, budget, restore=restore)
            self.assertEqual(exhausted.status, RetryStatus.EXHAUSTED)
            self.assertIsNone(exhausted.current_plan)
            self.assertEqual(restored, ["a" * 64])
            self.assertEqual(exhausted.retained_candidate_digest, "a" * 64)
