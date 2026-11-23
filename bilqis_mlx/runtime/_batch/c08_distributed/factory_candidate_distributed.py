"""Distributed C08 execution behind the stable Factory microbatch facade."""
from __future__ import annotations

import time

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.atlas_resources import partition_logical_batch, validate_runtime_rank
from bilqis_mlx.runtime.atlas_training_authority import extend_training_dependencies

from .c08_gradient_accumulation import DistributedLogicalBatchMetadata
from .c08_distributed_gradient import execute_distributed_rank
from .c08_distributed_coordinator import logical_batch_from_distributed_outcome
from .c08_distributed_outcome import (
    DistributedRuntimeAttestation, DistributedStepOutcome,
    all_gather_runtime_attestation,
)
from .c08_distributed_collective import all_reduce_fp32_rank_mean
from .c08_distributed_evidence import all_gather_b11_evidence, evidence_training_extension


def _row_execution_inputs(*args, **kwargs):
    from .factory_candidate_microbatch import _row_execution_inputs as owner
    return owner(*args, **kwargs)


def execute_factory_distributed_rank(
        parameters, prepared, source_context, feature_snapshot, generation, cache,
        resource_plan, manifest, partition, *, salience_supervision=None,
        mentor_supervision=None):
    """Execute only the coordinator-declared rows for one distributed rank."""
    rows = tuple(_row_execution_inputs(
        source_context, compiled, feature_snapshot, generation)
        for compiled in prepared.compiled_rows)

    def execute_row(index):
        bound, _authority, targets, mask, plan = rows[index]
        multiplier = _mentor_multiplier(
            mentor_supervision, prepared.compiled_rows[index])
        return bamf_value_and_grad(
            parameters, bound, plan, targets, mask, cache,
            salience_supervision=salience_supervision,
            source_loss_multiplier=multiplier)

    return execute_distributed_rank(
        resource_plan, manifest, partition, execute_row,
        base_authority_for_row=lambda index: rows[index][0].training_authority)


def execute_factory_distributed_rows_rank(
        parameters, compiled_rows, source_context, feature_snapshot, generation, cache,
        resource_plan, manifest, partition, *, source_loss_multipliers,
        salience_supervision=None):
    """Execute rank rows reconstructed from a portable coordinator capsule."""
    rows = tuple(_row_execution_inputs(
        source_context, compiled, feature_snapshot, generation)
        for compiled in compiled_rows)
    if (type(source_loss_multipliers) is not tuple
            or len(source_loss_multipliers) != len(compiled_rows)):
        ErrorBus.raise_(
            SCHOOL.BAMF_TRAINING_ADAPTER.INVALID,
            reason="FACTORY_DISTRIBUTED_MULTIPLIER_DRIFT")

    def execute_row(index):
        bound, _authority, targets, mask, plan = rows[index]
        return bamf_value_and_grad(
            parameters, bound, plan, targets, mask, cache,
            salience_supervision=salience_supervision,
            source_loss_multiplier=source_loss_multipliers[index])

    return execute_distributed_rank(
        resource_plan, manifest, partition, execute_row,
        base_authority_for_row=lambda index: rows[index][0].training_authority)


def execute_factory_distributed_rank_collective(
        parameters, prepared, source_context, feature_snapshot, generation, cache,
        resource_plan, manifest, partition, *, salience_supervision=None,
        mentor_supervision=None, group=None, backend=None,
        device_family=None, mlx_version=None, numeric_precision="fp32"):
    """Execute a rank and participate in the declared MLX FP32 collective."""
    if group is None or group.size() != manifest.world_size:
        ErrorBus.raise_(
            SCHOOL.BAMF_TRAINING_ADAPTER.INVALID,
            reason="FACTORY_DISTRIBUTED_GROUP_WORLD_SIZE_DRIFT")
    validate_runtime_rank(
        manifest, partition, group, backend=backend,
        device_family=device_family, mlx_version=mlx_version,
        numeric_precision=numeric_precision)
    local_attestation = DistributedRuntimeAttestation(
        manifest.digest, partition.rank, manifest.workers[partition.rank].worker_id,
        device_family, mlx_version, manifest.backend, numeric_precision)
    rank_result = execute_factory_distributed_rank(
        parameters, prepared, source_context, feature_snapshot, generation, cache,
        resource_plan, manifest, partition,
        salience_supervision=salience_supervision,
        mentor_supervision=mentor_supervision)
    communication_started = time.perf_counter()
    gradients, loss, _all_reduce_seconds = all_reduce_fp32_rank_mean(
        rank_result.gradients, rank_result.mean_loss,
        local_rows=len(rank_result.row_indices),
        total_rows=len(resource_plan.logical_row_ids), group=group)
    evidence = all_gather_b11_evidence(rank_result.evidence, group)
    attestations = all_gather_runtime_attestation(local_attestation, group)
    compute = mx.distributed.all_gather(
        mx.array([rank_result.compute_seconds], dtype=mx.float32), group=group)
    local_peak = max(
        rank_result.peak_memory_bytes,
        int(mx.get_active_memory()),
        int(mx.get_peak_memory()))
    peak = mx.distributed.all_gather(
        mx.array([local_peak], dtype=mx.int64), group=group)
    mx.eval(compute, peak)
    communication_seconds = time.perf_counter() - communication_started
    return DistributedStepOutcome(
        manifest.digest, evidence, attestations, gradients, loss,
        tuple(float(value) for value in compute.tolist()), communication_seconds,
        tuple(int(value) for value in peak.tolist()))


def execute_factory_distributed_group(
        parameters, prepared, source_context, feature_snapshot, generation, cache,
        resource_plan, manifest, *, group, backend, device_family, mlx_version,
        numeric_precision="fp32", salience_supervision=None,
        mentor_supervision=None):
    """MLX worker entrypoint: execute this process rank and return portable outcome."""
    partitions = partition_logical_batch(resource_plan, manifest)
    rank = group.rank()
    if rank < 0 or rank >= len(partitions):
        ErrorBus.raise_(
            SCHOOL.BAMF_TRAINING_ADAPTER.INVALID,
            reason="FACTORY_DISTRIBUTED_GROUP_RANK_DRIFT")
    return execute_factory_distributed_rank_collective(
        parameters, prepared, source_context, feature_snapshot, generation, cache,
        resource_plan, manifest, partitions[rank], group=group, backend=backend,
        device_family=device_family, mlx_version=mlx_version,
        numeric_precision=numeric_precision,
        salience_supervision=salience_supervision,
        mentor_supervision=mentor_supervision)


def execute_factory_distributed_rows_group(
        parameters, compiled_rows, source_context, feature_snapshot, generation, cache,
        resource_plan, manifest, *, source_loss_multipliers, group, backend,
        device_family, mlx_version, numeric_precision="fp32",
        salience_supervision=None):
    """Worker entrypoint for a portable capsule with rank-local authorities."""
    partitions = partition_logical_batch(resource_plan, manifest)
    rank = group.rank()
    if rank < 0 or rank >= len(partitions):
        ErrorBus.raise_(
            SCHOOL.BAMF_TRAINING_ADAPTER.INVALID,
            reason="FACTORY_DISTRIBUTED_GROUP_RANK_DRIFT")
    partition = partitions[rank]
    validate_runtime_rank(
        manifest, partition, group, backend=backend,
        device_family=device_family, mlx_version=mlx_version,
        numeric_precision=numeric_precision)
    local_attestation = DistributedRuntimeAttestation(
        manifest.digest, partition.rank, manifest.workers[partition.rank].worker_id,
        device_family, mlx_version, manifest.backend, numeric_precision)
    rank_result = execute_factory_distributed_rows_rank(
        parameters, compiled_rows, source_context, feature_snapshot, generation, cache,
        resource_plan, manifest, partition,
        source_loss_multipliers=source_loss_multipliers,
        salience_supervision=salience_supervision)
    communication_started = time.perf_counter()
    gradients, loss, _all_reduce_seconds = all_reduce_fp32_rank_mean(
        rank_result.gradients, rank_result.mean_loss,
        local_rows=len(rank_result.row_indices),
        total_rows=len(resource_plan.logical_row_ids), group=group)
    evidence = all_gather_b11_evidence(rank_result.evidence, group)
    attestations = all_gather_runtime_attestation(local_attestation, group)
    compute = mx.distributed.all_gather(
        mx.array([rank_result.compute_seconds], dtype=mx.float32), group=group)
    local_peak = max(
        rank_result.peak_memory_bytes, int(mx.get_active_memory()),
        int(mx.get_peak_memory()))
    peak = mx.distributed.all_gather(
        mx.array([local_peak], dtype=mx.int64), group=group)
    mx.eval(compute, peak)
    return DistributedStepOutcome(
        manifest.digest, evidence, attestations, gradients, loss,
        tuple(float(value) for value in compute.tolist()),
        time.perf_counter() - communication_started,
        tuple(int(value) for value in peak.tolist()))


def bind_factory_distributed_outcome(
        prepared, source_context, feature_snapshot, generation, resource_plan,
        manifest, outcome: DistributedStepOutcome):
    """Rebuild row authority locally around a portable distributed outcome."""
    rows = tuple(_row_execution_inputs(
        source_context, compiled, feature_snapshot, generation)
        for compiled in prepared.compiled_rows)
    gradient = logical_batch_from_distributed_outcome(
        resource_plan, manifest, outcome)
    evidence = tuple(sorted(outcome.evidence, key=lambda item: item.row_index))
    authorities = []
    for row, item in zip(rows, evidence):
        base = row[0].training_authority
        if base is None:
            ErrorBus.raise_(
                SCHOOL.BAMF_TRAINING_ADAPTER.INVALID,
                reason="FACTORY_DISTRIBUTED_B11_AUTHORITY_REQUIRED")
        dependencies, artifacts = evidence_training_extension(item)
        authority = extend_training_dependencies(
            base, dependencies, artifact_nodes=artifacts)
        if authority.digest != item.training_authority_digest:
            ErrorBus.raise_(
                SCHOOL.BAMF_TRAINING_ADAPTER.INVALID,
                reason="FACTORY_DISTRIBUTED_B11_AUTHORITY_DRIFT")
        authorities.append(authority)
    authorities = tuple(authorities)
    metadata = gradient.distributed_metadata
    object.__setattr__(gradient, "distributed_metadata", DistributedLogicalBatchMetadata(
        manifest=metadata.manifest,
        compute_seconds_per_worker=metadata.compute_seconds_per_worker,
        communication_seconds=metadata.communication_seconds,
        peak_memory_per_worker=metadata.peak_memory_per_worker,
        training_authorities=authorities))
    gradient.__post_init__()
    return gradient, authorities, tuple(item[2] for item in rows)
