from __future__ import annotations

from dataclasses import replace
import copy
import unittest

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.distributed_step import (
    BackendCapability,
    DistributedStepManifest,
    RankGradientReceipt,
    ReductionPolicy,
    ResourceTopology,
    TopologyBenchmark,
    WorkerIdentity,
    choose_resource_topology,
    commit_logical_step,
    distributed_backend_capabilities,
    distributed_train_step,
    partition_logical_batch,
    reduce_rank_gradients,
    validate_resume_execution,
)

GENERATION = "generation:" + "a" * 64
SOURCE_RELEASE = "b" * 64
TOPOLOGY = "c" * 64
BATCH = tuple(f"row:{i}" for i in range(7))


def worker(rank: int, *, family: str = "Apple M3 Ultra") -> WorkerIdentity:
    return WorkerIdentity(
        rank=rank,
        worker_id=f"worker:{rank}",
        device_family=family,
        memory_bytes=96 * 1024**3,
        measured_compute_gflops=1000.0 - rank * 100,
        memory_bandwidth_gbps=800.0 - rank * 50,
        interconnect="Thunderbolt-5",
    )


def manifest(world_size: int = 2) -> DistributedStepManifest:
    return DistributedStepManifest.create(
        retained_generation=GENERATION,
        curriculum_release=SOURCE_RELEASE,
        logical_batch_row_ids=BATCH,
        partition_seed=73,
        workers=tuple(worker(i) for i in range(world_size)),
        mlx_version="0.30.1",
        backend="ring",
        numeric_precision="fp32",
        reduction_policy=ReductionPolicy.WEIGHTED_MEAN_FP32,
        topology_digest=TOPOLOGY,
    )


class DistributedStepTests(unittest.TestCase):
    def test_two_rank_partition_is_deterministic_disjoint_and_covers_single_worker_batch(self):
        two = manifest(2)
        first = partition_logical_batch(two)
        second = partition_logical_batch(two)
        one = partition_logical_batch(manifest(1))
        self.assertEqual(first, second)
        self.assertEqual(tuple(sorted(x for rows in first for x in rows)), tuple(sorted(BATCH)))
        self.assertEqual(set(first[0]).intersection(first[1]), set())
        self.assertEqual(one, (BATCH,))
        self.assertEqual(tuple(sorted(x for rows in first for x in rows)), tuple(sorted(one[0])))

    def test_weighted_rank_reduction_matches_single_worker_reference(self):
        m = manifest(2)
        parts = partition_logical_batch(m)
        receipts = (
            RankGradientReceipt.create(m, 0, parts[0], (1.0, 3.0), 0.25,
                                       compute_seconds=2, communication_seconds=.2,
                                       evaluation_seconds=.1, examples=len(parts[0]), tokens=40),
            RankGradientReceipt.create(m, 1, parts[1], (5.0, 7.0), 0.75,
                                       compute_seconds=3, communication_seconds=.4,
                                       evaluation_seconds=.2, examples=len(parts[1]), tokens=30),
        )
        reduced = reduce_rank_gradients(m, receipts)
        n0, n1 = len(parts[0]), len(parts[1])
        total = n0 + n1
        expected = ((1*n0+5*n1)/total, (3*n0+7*n1)/total)
        self.assertEqual(reduced.logical_row_ids, BATCH)
        self.assertEqual(reduced.optimizer_steps, 1)
        for actual, reference in zip(reduced.gradient, expected):
            self.assertAlmostEqual(actual, reference, places=6)
        self.assertGreater(reduced.telemetry.effective_examples_per_second, 0)
        self.assertGreater(reduced.telemetry.effective_tokens_per_second, 0)

    def test_duplicate_stale_or_wrong_partition_receipt_fails_before_reduction(self):
        m = manifest(2)
        parts = partition_logical_batch(m)
        good0 = RankGradientReceipt.create(m, 0, parts[0], (1.0,), 0.5,
                                           compute_seconds=1, communication_seconds=.1,
                                           evaluation_seconds=.1, examples=len(parts[0]), tokens=4)
        good1 = RankGradientReceipt.create(m, 1, parts[1], (1.0,), 0.5,
                                           compute_seconds=1, communication_seconds=.1,
                                           evaluation_seconds=.1, examples=len(parts[1]), tokens=3)
        with self.assertRaises(BilqisError):
            reduce_rank_gradients(m, (good0, good0))
        stale = copy.copy(good1)
        object.__setattr__(stale, "manifest_digest", "0" * 64)
        with self.assertRaises(BilqisError):
            reduce_rank_gradients(m, (good0, stale))
        wrong = copy.copy(good1)
        object.__setattr__(wrong, "row_ids", parts[0])
        with self.assertRaises(BilqisError):
            reduce_rank_gradients(m, (good0, wrong))

    def test_tampered_reduced_gradient_cannot_reach_backend(self):
        m = manifest(2)
        parts = partition_logical_batch(m)
        receipts = tuple(
            RankGradientReceipt.create(m, rank, rows, (1.0,), 0.5,
                                       compute_seconds=1, communication_seconds=.1,
                                       evaluation_seconds=.1, examples=len(rows), tokens=len(rows))
            for rank, rows in enumerate(parts))
        reduced = reduce_rank_gradients(m, receipts)
        tampered = copy.copy(reduced)
        object.__setattr__(tampered, "optimizer_steps", 2)
        calls = []
        with self.assertRaises(BilqisError):
            commit_logical_step(tampered, (), lambda *args: calls.append(args))
        self.assertEqual(calls, [])

    def test_one_manifest_can_commit_only_one_logical_optimizer_step(self):
        m = manifest(2)
        parts = partition_logical_batch(m)
        receipts = tuple(
            RankGradientReceipt.create(m, rank, rows, (float(rank + 1),), 0.5,
                                       compute_seconds=1, communication_seconds=.1,
                                       evaluation_seconds=.1, examples=len(rows), tokens=len(rows))
            for rank, rows in enumerate(parts)
        )
        reduced = reduce_rank_gradients(m, receipts)
        calls = []
        def apply(gradient, retained_generation, manifest_digest):
            calls.append((gradient, retained_generation, manifest_digest))
            return "generation:" + "d" * 64
        receipt, guard = commit_logical_step(reduced, (), apply)
        self.assertEqual(receipt.optimizer_steps_applied, 1)
        self.assertEqual(len(calls), 1)
        with self.assertRaises(BilqisError):
            commit_logical_step(reduced, guard, apply)
        self.assertEqual(len(calls), 1)

    def test_distributed_train_step_composes_one_reduce_and_one_commit(self):
        m = manifest(2)
        parts = partition_logical_batch(m)
        receipts = tuple(
            RankGradientReceipt.create(m, rank, rows, (float(rank + 1),), 0.5,
                                       compute_seconds=1, communication_seconds=.1,
                                       evaluation_seconds=.1, examples=len(rows), tokens=len(rows),
                                       peak_memory_bytes=1024 * (rank + 1))
            for rank, rows in enumerate(parts))
        calls = []
        def apply(gradient, retained_generation, manifest_digest):
            calls.append((gradient, retained_generation, manifest_digest))
            return "generation:" + "f" * 64
        result = distributed_train_step(m, receipts, (), apply)
        self.assertEqual(result.commit.optimizer_steps_applied, 1)
        self.assertEqual(result.commit.new_generation, "generation:" + "f" * 64)
        self.assertEqual(result.reduced.telemetry.peak_memory_bytes_by_rank, (1024, 2048))
        self.assertEqual(len(calls), 1)
        with self.assertRaises(BilqisError):
            distributed_train_step(m, receipts, result.consumed_manifest_digests, apply)
        self.assertEqual(len(calls), 1)

    def test_rejection_or_worker_loss_never_calls_backend(self):
        m = manifest(2)
        parts = partition_logical_batch(m)
        only = RankGradientReceipt.create(m, 0, parts[0], (1.0,), 0.5,
                                          compute_seconds=1, communication_seconds=.1,
                                          evaluation_seconds=.1, examples=len(parts[0]), tokens=4)
        with self.assertRaises(BilqisError):
            reduce_rank_gradients(m, (only,))

    def test_execution_metadata_changes_do_not_change_semantic_identity(self):
        two = manifest(2)
        changed = replace(two, backend="jaccl", mlx_version="0.30.2")
        self.assertEqual(two.semantic_identity_digest, changed.semantic_identity_digest)
        self.assertNotEqual(two.execution_digest, changed.execution_digest)
        validate_resume_execution(two, changed, allow_execution_replan=True)
        with self.assertRaises(BilqisError):
            validate_resume_execution(two, changed, allow_execution_replan=False)
        with self.assertRaises(BilqisError):
            validate_resume_execution(two, replace(changed, retained_generation="generation:"+"e"*64), allow_execution_replan=True)

    def test_backend_capability_surface_matches_installed_mlx_without_initializing_group(self):
        caps = distributed_backend_capabilities()
        self.assertEqual(tuple(x.name for x in caps), ("ring", "jaccl", "mpi", "nccl"))
        self.assertTrue(all(type(x.available) is bool for x in caps))
        observed = {name: bool(mx.distributed.is_available(name)) for name in ("ring", "jaccl", "mpi", "nccl")}
        self.assertEqual({x.name: x.available for x in caps}, observed)

    def test_backend_change_can_select_nccl_without_changing_school_identity(self):
        base = manifest(2)
        nccl = replace(base, backend="nccl")
        self.assertEqual(base.semantic_identity_digest, nccl.semantic_identity_digest)
        self.assertNotEqual(base.execution_digest, nccl.execution_digest)

    def test_topology_choice_uses_retained_gain_per_hour_not_nominal_speed(self):
        single = TopologyBenchmark(
            ResourceTopology.SINGLE_FASTEST_TRAINER, 3600, 4.0, 100, 90, 1000, 10000, (20,))
        sync = TopologyBenchmark(
            ResourceTopology.SYNCHRONOUS_WORKERS, 1800, 1.0, 120, 100, 1200, 12000, (18, 18))
        aux = TopologyBenchmark(
            ResourceTopology.TRAINER_PLUS_AUXILIARY, 3600, 5.0, 95, 92, 1100, 11000, (20, 8))
        self.assertIs(choose_resource_topology((single, sync, aux)), aux)

    def test_worker_rank_and_manifest_world_size_are_exact(self):
        with self.assertRaises(BilqisError):
            DistributedStepManifest.create(
                retained_generation=GENERATION, curriculum_release=SOURCE_RELEASE,
                logical_batch_row_ids=BATCH, partition_seed=73,
                workers=(worker(0), worker(2)), mlx_version="0.30.1",
                backend="ring", numeric_precision="fp32",
                reduction_policy=ReductionPolicy.WEIGHTED_MEAN_FP32,
                topology_digest=TOPOLOGY)


if __name__ == "__main__":
    unittest.main()
