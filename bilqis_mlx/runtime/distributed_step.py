"""C08.4 distributed logical-step contracts.

This module owns execution identity, deterministic rank partitioning, receipt
validation, FP32 reduction semantics and replay protection. It does not start a
learner, initialize a distributed process group, or publish canonical state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Callable

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL

SCHEMA = "bilqis.mlx.distributed-step-manifest/v1"
RECEIPT_SCHEMA = "bilqis.mlx.distributed-rank-gradient/v1"
REDUCED_SCHEMA = "bilqis.mlx.distributed-reduced-gradient/v1"
COMMIT_SCHEMA = "bilqis.mlx.distributed-step-commit/v1"
_ALLOWED_BACKENDS = ("ring", "jaccl", "mpi", "nccl")
_SHA = frozenset("0123456789abcdef")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _text(value: object) -> bool:
    return type(value) is str and bool(value)


def _sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256(raw).hexdigest()


def _digest64(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(ch in _SHA for ch in value)


def _generation(value: object) -> bool:
    return type(value) is str and value.startswith("generation:") and _digest64(value.removeprefix("generation:"))


def _finite(value: object, *, nonnegative: bool = False) -> bool:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        return False
    return not nonnegative or float(value) >= 0


class ReductionPolicy(str, Enum):
    WEIGHTED_MEAN_FP32 = "WEIGHTED_MEAN_FP32"


@dataclass(frozen=True)
class WorkerIdentity:
    rank: int
    worker_id: str
    device_family: str
    memory_bytes: int
    measured_compute_gflops: float
    memory_bandwidth_gbps: float
    interconnect: str

    def __post_init__(self) -> None:
        if (type(self.rank) is not int or self.rank < 0
                or not all(_text(v) for v in (self.worker_id, self.device_family, self.interconnect))
                or type(self.memory_bytes) is not int or self.memory_bytes <= 0
                or not _finite(self.measured_compute_gflops, nonnegative=True)
                or not _finite(self.memory_bandwidth_gbps, nonnegative=True)):
            _invalid("BAMF_C08_DISTRIBUTED_WORKER_INVALID")

    def identity_payload(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "worker_id": self.worker_id,
            "device_family": self.device_family,
            "memory_bytes": self.memory_bytes,
            "measured_compute_gflops": float(self.measured_compute_gflops),
            "memory_bandwidth_gbps": float(self.memory_bandwidth_gbps),
            "interconnect": self.interconnect,
        }


@dataclass(frozen=True)
class DistributedStepManifest:
    retained_generation: str
    curriculum_release: str
    logical_batch_row_ids: tuple[str, ...]
    logical_batch_digest: str
    partition_seed: int
    workers: tuple[WorkerIdentity, ...]
    mlx_version: str
    backend: str
    numeric_precision: str
    reduction_policy: ReductionPolicy
    topology_digest: str
    schema_version: str = SCHEMA

    @classmethod
    def create(
        cls, *, retained_generation: str, curriculum_release: str,
        logical_batch_row_ids: tuple[str, ...], partition_seed: int,
        workers: tuple[WorkerIdentity, ...], mlx_version: str, backend: str,
        numeric_precision: str, reduction_policy: ReductionPolicy,
        topology_digest: str,
    ) -> "DistributedStepManifest":
        digest = _sha({"rows": logical_batch_row_ids})
        return cls(
            retained_generation, curriculum_release, logical_batch_row_ids,
            digest, partition_seed, workers, mlx_version, backend,
            numeric_precision, reduction_policy, topology_digest,
        )

    def __post_init__(self) -> None:
        ranks = tuple(worker.rank for worker in self.workers) if type(self.workers) is tuple else ()
        if (not _generation(self.retained_generation)
                or not _digest64(self.curriculum_release)
                or type(self.logical_batch_row_ids) is not tuple
                or not self.logical_batch_row_ids
                or any(not _text(row) for row in self.logical_batch_row_ids)
                or len(set(self.logical_batch_row_ids)) != len(self.logical_batch_row_ids)
                or self.logical_batch_digest != _sha({"rows": self.logical_batch_row_ids})
                or type(self.partition_seed) is not int or self.partition_seed < 0
                or type(self.workers) is not tuple or not self.workers
                or any(type(worker) is not WorkerIdentity for worker in self.workers)
                or ranks != tuple(range(len(self.workers)))
                or len({worker.worker_id for worker in self.workers}) != len(self.workers)
                or not _text(self.mlx_version)
                or self.backend not in _ALLOWED_BACKENDS
                or self.numeric_precision != "fp32"
                or type(self.reduction_policy) is not ReductionPolicy
                or self.reduction_policy is not ReductionPolicy.WEIGHTED_MEAN_FP32
                or not _digest64(self.topology_digest)
                or self.schema_version != SCHEMA):
            _invalid("BAMF_C08_DISTRIBUTED_MANIFEST_INVALID")

    @property
    def world_size(self) -> int:
        return len(self.workers)

    @property
    def semantic_identity_digest(self) -> str:
        """School/model identity excludes replaceable execution topology."""
        return _sha({
            "retained_generation": self.retained_generation,
            "curriculum_release": self.curriculum_release,
            "logical_batch_digest": self.logical_batch_digest,
            "topology_digest": self.topology_digest,
        })

    @property
    def execution_digest(self) -> str:
        return _sha({
            "schema": self.schema_version,
            "semantic_identity_digest": self.semantic_identity_digest,
            "partition_seed": self.partition_seed,
            "workers": [worker.identity_payload() for worker in self.workers],
            "mlx_version": self.mlx_version,
            "backend": self.backend,
            "numeric_precision": self.numeric_precision,
            "reduction_policy": self.reduction_policy.value,
        })


def partition_logical_batch(manifest: DistributedStepManifest) -> tuple[tuple[str, ...], ...]:
    if type(manifest) is not DistributedStepManifest:
        _invalid("BAMF_C08_DISTRIBUTED_MANIFEST_REQUIRED")
    manifest.__post_init__()
    if manifest.world_size == 1:
        return (manifest.logical_batch_row_ids,)
    ordered = tuple(sorted(
        manifest.logical_batch_row_ids,
        key=lambda row: (_sha({"seed": manifest.partition_seed, "row": row}), row),
    ))
    buckets = [[] for _ in range(manifest.world_size)]
    for index, row in enumerate(ordered):
        buckets[index % manifest.world_size].append(row)
    return tuple(tuple(bucket) for bucket in buckets)


@dataclass(frozen=True)
class RankGradientReceipt:
    manifest_digest: str
    rank: int
    row_ids: tuple[str, ...]
    gradient: tuple[float, ...]
    weighted_mean_loss: float
    compute_seconds: float
    communication_seconds: float
    evaluation_seconds: float
    examples: int
    tokens: int
    peak_memory_bytes: int
    receipt_digest: str
    schema_version: str = RECEIPT_SCHEMA

    @classmethod
    def create(
        cls, manifest: DistributedStepManifest, rank: int, row_ids: tuple[str, ...],
        gradient: tuple[float, ...], weighted_mean_loss: float, *,
        compute_seconds: float, communication_seconds: float,
        evaluation_seconds: float, examples: int, tokens: int,
        peak_memory_bytes: int = 0,
    ) -> "RankGradientReceipt":
        if type(manifest) is not DistributedStepManifest:
            _invalid("BAMF_C08_DISTRIBUTED_MANIFEST_REQUIRED")
        partitions = partition_logical_batch(manifest)
        if type(rank) is not int or rank < 0 or rank >= manifest.world_size or row_ids != partitions[rank]:
            _invalid("BAMF_C08_DISTRIBUTED_RANK_PARTITION_DRIFT")
        payload = {
            "manifest_digest": manifest.execution_digest, "rank": rank,
            "row_ids": row_ids, "gradient": gradient,
            "weighted_mean_loss": weighted_mean_loss,
            "compute_seconds": compute_seconds,
            "communication_seconds": communication_seconds,
            "evaluation_seconds": evaluation_seconds,
            "examples": examples, "tokens": tokens,
            "peak_memory_bytes": peak_memory_bytes,
        }
        return cls(
            manifest.execution_digest, rank, row_ids, gradient,
            weighted_mean_loss, compute_seconds, communication_seconds,
            evaluation_seconds, examples, tokens, peak_memory_bytes, _sha(payload),
        )

    def __post_init__(self) -> None:
        payload = {
            "manifest_digest": self.manifest_digest, "rank": self.rank,
            "row_ids": self.row_ids, "gradient": self.gradient,
            "weighted_mean_loss": self.weighted_mean_loss,
            "compute_seconds": self.compute_seconds,
            "communication_seconds": self.communication_seconds,
            "evaluation_seconds": self.evaluation_seconds,
            "examples": self.examples, "tokens": self.tokens,
            "peak_memory_bytes": self.peak_memory_bytes,
        }
        if (not _digest64(self.manifest_digest)
                or type(self.rank) is not int or self.rank < 0
                or type(self.row_ids) is not tuple or any(not _text(row) for row in self.row_ids)
                or type(self.gradient) is not tuple or not self.gradient
                or any(not _finite(value) for value in self.gradient)
                or not _finite(self.weighted_mean_loss)
                or any(not _finite(value, nonnegative=True) for value in (
                    self.compute_seconds, self.communication_seconds, self.evaluation_seconds))
                or type(self.examples) is not int or self.examples != len(self.row_ids)
                or type(self.tokens) is not int or self.tokens < 0
                or type(self.peak_memory_bytes) is not int or self.peak_memory_bytes < 0
                or self.receipt_digest != _sha(payload)
                or self.schema_version != RECEIPT_SCHEMA):
            _invalid("BAMF_C08_DISTRIBUTED_RANK_RECEIPT_INVALID")


@dataclass(frozen=True)
class DistributedTelemetry:
    compute_seconds: float
    communication_seconds: float
    evaluation_seconds: float
    effective_examples_per_second: float
    effective_tokens_per_second: float
    attempted_steps_per_hour: float
    accepted_steps_per_hour: float
    peak_worker_seconds: float
    peak_memory_bytes_by_rank: tuple[int, ...]

    def __post_init__(self) -> None:
        if (any(not _finite(value, nonnegative=True) for value in (
                    self.compute_seconds, self.communication_seconds, self.evaluation_seconds,
                    self.effective_examples_per_second, self.effective_tokens_per_second,
                    self.attempted_steps_per_hour, self.accepted_steps_per_hour,
                    self.peak_worker_seconds))
                or type(self.peak_memory_bytes_by_rank) is not tuple
                or not self.peak_memory_bytes_by_rank
                or any(type(value) is not int or value < 0 for value in self.peak_memory_bytes_by_rank)):
            _invalid("BAMF_C08_DISTRIBUTED_TELEMETRY_INVALID")


@dataclass(frozen=True)
class ReducedDistributedGradient:
    manifest_digest: str
    retained_generation: str
    logical_row_ids: tuple[str, ...]
    gradient: tuple[float, ...]
    weighted_mean_loss: float
    optimizer_steps: int
    telemetry: DistributedTelemetry
    reduction_digest: str
    schema_version: str = REDUCED_SCHEMA

    def __post_init__(self) -> None:
        if (not _digest64(self.manifest_digest)
                or not _generation(self.retained_generation)
                or type(self.logical_row_ids) is not tuple or not self.logical_row_ids
                or any(not _text(row) for row in self.logical_row_ids)
                or type(self.gradient) is not tuple or not self.gradient
                or any(not _finite(value) for value in self.gradient)
                or not _finite(self.weighted_mean_loss)
                or self.optimizer_steps != 1
                or type(self.telemetry) is not DistributedTelemetry
                or not _digest64(self.reduction_digest)
                or self.schema_version != REDUCED_SCHEMA):
            _invalid("BAMF_C08_DISTRIBUTED_REDUCTION_INVALID")


def reduce_rank_gradients(
    manifest: DistributedStepManifest,
    receipts: tuple[RankGradientReceipt, ...],
) -> ReducedDistributedGradient:
    if (type(manifest) is not DistributedStepManifest or type(receipts) is not tuple
            or len(receipts) != manifest.world_size
            or any(type(receipt) is not RankGradientReceipt for receipt in receipts)):
        _invalid("BAMF_C08_DISTRIBUTED_RECEIPT_SET_INVALID")
    expected = partition_logical_batch(manifest)
    by_rank: dict[int, RankGradientReceipt] = {}
    width = None
    for receipt in receipts:
        receipt.__post_init__()
        if (receipt.manifest_digest != manifest.execution_digest
                or receipt.rank >= manifest.world_size
                or receipt.rank in by_rank
                or receipt.row_ids != expected[receipt.rank]):
            _invalid("BAMF_C08_DISTRIBUTED_RECEIPT_DRIFT")
        width = len(receipt.gradient) if width is None else width
        if len(receipt.gradient) != width:
            _invalid("BAMF_C08_DISTRIBUTED_GRADIENT_SHAPE_DRIFT")
        by_rank[receipt.rank] = receipt
    if tuple(sorted(by_rank)) != tuple(range(manifest.world_size)):
        _invalid("BAMF_C08_DISTRIBUTED_RANK_MISSING")
    total_examples = sum(receipt.examples for receipt in receipts)
    if total_examples != len(manifest.logical_batch_row_ids) or total_examples <= 0:
        _invalid("BAMF_C08_DISTRIBUTED_EXAMPLE_COUNT_DRIFT")
    # The declared authoritative reduction is FP32. Convert each weighted rank
    # contribution before summation so the pure coordinator contract mirrors
    # the device collective's numeric width rather than Python float64.
    gradient = tuple(float(np.float32(sum(
        np.float32(receipt.gradient[index]) * np.float32(receipt.examples)
        for receipt in receipts)) / np.float32(total_examples))
        for index in range(width or 0))
    loss = float(np.float32(sum(
        np.float32(receipt.weighted_mean_loss) * np.float32(receipt.examples)
        for receipt in receipts)) / np.float32(total_examples))
    peak = max(receipt.compute_seconds + receipt.communication_seconds + receipt.evaluation_seconds
               for receipt in receipts)
    if peak <= 0:
        _invalid("BAMF_C08_DISTRIBUTED_TIMING_INVALID")
    total_tokens = sum(receipt.tokens for receipt in receipts)
    telemetry = DistributedTelemetry(
        compute_seconds=max(receipt.compute_seconds for receipt in receipts),
        communication_seconds=max(receipt.communication_seconds for receipt in receipts),
        evaluation_seconds=max(receipt.evaluation_seconds for receipt in receipts),
        effective_examples_per_second=total_examples / peak,
        effective_tokens_per_second=total_tokens / peak,
        attempted_steps_per_hour=3600.0 / peak,
        accepted_steps_per_hour=3600.0 / peak,
        peak_worker_seconds=peak,
        peak_memory_bytes_by_rank=tuple(by_rank[i].peak_memory_bytes for i in range(manifest.world_size)),
    )
    reduction_digest = _sha({
        "manifest_digest": manifest.execution_digest,
        "logical_row_ids": manifest.logical_batch_row_ids,
        "gradient": gradient,
        "weighted_mean_loss": loss,
        "receipt_digests": tuple(by_rank[i].receipt_digest for i in range(manifest.world_size)),
    })
    return ReducedDistributedGradient(
        manifest.execution_digest, manifest.retained_generation,
        manifest.logical_batch_row_ids, gradient, loss, 1, telemetry,
        reduction_digest,
    )


@dataclass(frozen=True)
class LogicalStepCommitReceipt:
    manifest_digest: str
    retained_parent_generation: str
    new_generation: str
    reduction_digest: str
    optimizer_steps_applied: int
    schema_version: str = COMMIT_SCHEMA

    def __post_init__(self) -> None:
        if (not _digest64(self.manifest_digest)
                or not _generation(self.retained_parent_generation)
                or not _generation(self.new_generation)
                or self.new_generation == self.retained_parent_generation
                or not _digest64(self.reduction_digest)
                or self.optimizer_steps_applied != 1
                or self.schema_version != COMMIT_SCHEMA):
            _invalid("BAMF_C08_DISTRIBUTED_COMMIT_RECEIPT_INVALID")


def commit_logical_step(
    reduced: ReducedDistributedGradient,
    consumed_manifest_digests: tuple[str, ...],
    apply: Callable[[tuple[float, ...], str, str], str],
) -> tuple[LogicalStepCommitReceipt, tuple[str, ...]]:
    """Call one external transaction owner at most once per execution manifest."""
    if (type(reduced) is not ReducedDistributedGradient
            or type(consumed_manifest_digests) is not tuple
            or any(not _digest64(item) for item in consumed_manifest_digests)
            or not callable(apply)):
        _invalid("BAMF_C08_DISTRIBUTED_COMMIT_INPUT_INVALID")
    reduced.__post_init__()
    if reduced.manifest_digest in consumed_manifest_digests:
        _invalid("BAMF_C08_DISTRIBUTED_REPLAY_REJECTED")
    if reduced.optimizer_steps != 1:
        _invalid("BAMF_C08_DISTRIBUTED_OPTIMIZER_STEP_COUNT_INVALID")
    new_generation = apply(
        reduced.gradient, reduced.retained_generation, reduced.manifest_digest)
    if not _generation(new_generation) or new_generation == reduced.retained_generation:
        _invalid("BAMF_C08_DISTRIBUTED_BACKEND_GENERATION_INVALID")
    receipt = LogicalStepCommitReceipt(
        reduced.manifest_digest, reduced.retained_generation, new_generation,
        reduced.reduction_digest, 1,
    )
    return receipt, consumed_manifest_digests + (reduced.manifest_digest,)


@dataclass(frozen=True)
class DistributedTrainStepResult:
    reduced: ReducedDistributedGradient
    commit: LogicalStepCommitReceipt
    consumed_manifest_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        if (type(self.reduced) is not ReducedDistributedGradient
                or type(self.commit) is not LogicalStepCommitReceipt
                or self.commit.manifest_digest != self.reduced.manifest_digest
                or self.commit.reduction_digest != self.reduced.reduction_digest
                or type(self.consumed_manifest_digests) is not tuple
                or self.consumed_manifest_digests.count(self.reduced.manifest_digest) != 1):
            _invalid("BAMF_C08_DISTRIBUTED_STEP_RESULT_INVALID")


def distributed_train_step(
    manifest: DistributedStepManifest,
    rank_receipts: tuple[RankGradientReceipt, ...],
    consumed_manifest_digests: tuple[str, ...],
    apply: Callable[[tuple[float, ...], str, str], str],
) -> DistributedTrainStepResult:
    """Reduce one logical batch and invoke the external transaction owner once."""
    reduced = reduce_rank_gradients(manifest, rank_receipts)
    commit, guard = commit_logical_step(reduced, consumed_manifest_digests, apply)
    return DistributedTrainStepResult(reduced, commit, guard)


def validate_resume_execution(
    saved: DistributedStepManifest, runtime: DistributedStepManifest, *,
    allow_execution_replan: bool,
) -> None:
    if (type(saved) is not DistributedStepManifest or type(runtime) is not DistributedStepManifest
            or type(allow_execution_replan) is not bool):
        _invalid("BAMF_C08_DISTRIBUTED_RESUME_INPUT_INVALID")
    if saved.semantic_identity_digest != runtime.semantic_identity_digest:
        _invalid("BAMF_C08_DISTRIBUTED_RESUME_SEMANTIC_DRIFT")
    if not allow_execution_replan and saved.execution_digest != runtime.execution_digest:
        _invalid("BAMF_C08_DISTRIBUTED_RESUME_EXECUTION_DRIFT")


class ResourceTopology(str, Enum):
    SINGLE_FASTEST_TRAINER = "SINGLE_FASTEST_TRAINER"
    SYNCHRONOUS_WORKERS = "SYNCHRONOUS_WORKERS"
    TRAINER_PLUS_AUXILIARY = "TRAINER_PLUS_AUXILIARY"


@dataclass(frozen=True)
class TopologyBenchmark:
    topology: ResourceTopology
    wall_seconds: float
    retained_capability_gain: float
    attempted_steps: int
    accepted_steps: int
    examples: int
    tokens: int
    peak_memory_bytes_by_worker: tuple[int, ...]

    def __post_init__(self) -> None:
        if (type(self.topology) is not ResourceTopology
                or not _finite(self.wall_seconds) or self.wall_seconds <= 0
                or not _finite(self.retained_capability_gain, nonnegative=True)
                or any(type(value) is not int or value < 0 for value in (
                    self.attempted_steps, self.accepted_steps, self.examples, self.tokens))
                or self.accepted_steps > self.attempted_steps
                or type(self.peak_memory_bytes_by_worker) is not tuple
                or not self.peak_memory_bytes_by_worker
                or any(type(value) is not int or value < 0 for value in self.peak_memory_bytes_by_worker)):
            _invalid("BAMF_C08_TOPOLOGY_BENCHMARK_INVALID")

    @property
    def retained_gain_per_hour(self) -> float:
        return self.retained_capability_gain * 3600.0 / self.wall_seconds


def choose_resource_topology(benchmarks: tuple[TopologyBenchmark, ...]) -> TopologyBenchmark:
    """Choose measured retained-learning throughput, never nominal FLOPS alone."""
    if (type(benchmarks) is not tuple or not benchmarks
            or any(type(item) is not TopologyBenchmark for item in benchmarks)
            or len({item.topology for item in benchmarks}) != len(benchmarks)):
        _invalid("BAMF_C08_TOPOLOGY_BENCHMARK_SET_INVALID")
    return max(benchmarks, key=lambda item: (item.retained_gain_per_hour, item.accepted_steps, -item.wall_seconds))


@dataclass(frozen=True)
class BackendCapability:
    name: str
    available: bool

    def __post_init__(self) -> None:
        if self.name not in _ALLOWED_BACKENDS or type(self.available) is not bool:
            _invalid("BAMF_C08_DISTRIBUTED_BACKEND_CAPABILITY_INVALID")


def distributed_backend_capabilities() -> tuple[BackendCapability, ...]:
    """Inspect installed MLX support without creating a communication group."""
    return tuple(
        BackendCapability(name, bool(mx.distributed.is_available(name)))
        for name in _ALLOWED_BACKENDS
    )
