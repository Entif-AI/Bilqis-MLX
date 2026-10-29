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
        training_row_sha256="a" * 64, delivered_content_sha256="b" * 64,
    ) for index in range(count))


class AtlasResourcesTests(unittest.TestCase):
    def test_two_cpu_workers_freeze_same_source_packet_without_neural_authority(self):
        packet = {
            "schema": SOURCE_PREFETCH_SCHEMA,
            "identity": "a" * 64,
            "fresh": [{"id": "row:1", "tokens": [1, 2, 3]}],
            "prior": [], "preservation": [],
            "retention_support": [], "teaching_enrichment_rows": [],
        }
        serial = freeze_source_packet(packet)
        with source_prefetch_pool(2) as pool:
            futures = tuple(
                pool.submit(freeze_source_packet, packet)
                for _ in range(2))
            parallel = tuple(future.result(timeout=15) for future in futures)
        self.assertEqual(parallel, (serial, serial))
        self.assertIsInstance(serial.payload, tuple)
        packet["fresh"][0]["tokens"].append(99)
        self.assertNotEqual(serial, freeze_source_packet(packet))
        with_source_receipt = freeze_source_packet({
            **packet, "fresh": [{
                "id": "row:1", "tokens": [1, 2, 3],
                "receipt": {"source_sha256": "f" * 64},
            }],
        })
        self.assertNotEqual(with_source_receipt.digest, serial.digest)
        with self.assertRaises(BilqisError) as caught:
            freeze_source_packet({
                **packet,
                "fresh": [{"id": "row:1", "model_state": "forbidden"}],
            })
        self.assertEqual(caught.exception.context["reason"],
                         "SOURCE_PREFETCH_FORBIDDEN_AUTHORITY")
        with self.assertRaises(BilqisError) as caught:
            source_prefetch_pool(3)
        self.assertEqual(caught.exception.context["reason"],
                         "SOURCE_PREFETCH_WORKER_COUNT_INVALID")

    def test_complete_next_bundle_budget_keeps_100_gib_floor_before_write(self):
        budget = estimate_next_bundle_bytes(
            self.census, manifest_bytes=1_000_000,
            publication_overhead_bytes=10_000_000)
        self.assertEqual(
            budget.total_bytes,
            budget.weights_bytes + budget.optimizer_moments_bytes
            + 1_000_000 + 10_000_000)
        free = budget.total_bytes + RETAINED_DISK_RESERVE_BYTES + 1
        with patch("bilqis_mlx.runtime.disk.shutil.disk_usage",
                   return_value=SimpleNamespace(free=free)):
            report = assert_bundle_headroom(Path("/tmp"), budget)
        self.assertEqual(report["reserve_bytes"],
                         RETAINED_DISK_RESERVE_BYTES)
        self.assertEqual(report["required_next_bundle_bytes"],
                         budget.total_bytes)
        with patch("bilqis_mlx.runtime.disk.shutil.disk_usage",
                   return_value=SimpleNamespace(free=free - 2)):
            with self.assertRaisesRegex(
                    RuntimeError, "DISK_BUDGET_EXHAUSTED"):
                assert_bundle_headroom(Path("/tmp"), budget)

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

    def test_installed_mlx_memory_getters_are_snapshot_only(self):
        class FakeMLX:
            __version__ = "0.31.1"

            def get_active_memory(self):
                return 123

            def get_cache_memory(self):
                return 45

            def get_peak_memory(self):
                return 678

            def reset_peak_memory(self):
                raise AssertionError("snapshot must not mutate MLX telemetry")

        snapshot = snapshot_mlx_memory(FakeMLX(), observed_at=700)
        self.assertEqual(
            (snapshot.active_bytes, snapshot.cache_bytes,
             snapshot.peak_bytes, snapshot.mlx_version),
            (123, 45, 678, "0.31.1"))

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


if __name__ == "__main__":
    unittest.main()
