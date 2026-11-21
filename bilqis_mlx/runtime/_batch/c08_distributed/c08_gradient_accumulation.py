"""C08 owner for raw MLX gradient-tree accumulation across one logical batch."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable, Mapping

import mlx.core as mx

from bilqis_mlx.b11_observation import attach_performance_observation
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.atlas_model import (
    BamfGradientExecution, BamfMicrobatchGradientExecution,
)
from bilqis_mlx.runtime.atlas_resources import BatchPlan, DistributedStepManifest


_ISSUER = object()
_LOGICAL_BATCH_MIN_ROWS = 2
_SHA256_HEX_LENGTH = 64


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


@dataclass(frozen=True)
class DistributedLogicalBatchMetadata:
    """Execution-only distributed facts; excluded from logical/model identity."""
    manifest: DistributedStepManifest
    compute_seconds_per_worker: tuple[float, ...]
    communication_seconds: float
    peak_memory_per_worker: tuple[int, ...]
    training_authorities: tuple = ()

    def __post_init__(self) -> None:
        if (type(self.manifest) is not DistributedStepManifest
                or type(self.compute_seconds_per_worker) is not tuple
                or len(self.compute_seconds_per_worker) != self.manifest.world_size
                or any(type(value) is not float or value < 0.0
                       for value in self.compute_seconds_per_worker)
                or type(self.communication_seconds) is not float
                or self.communication_seconds < 0.0
                or type(self.peak_memory_per_worker) is not tuple
                or len(self.peak_memory_per_worker) != self.manifest.world_size
                or any(type(value) is not int or value < 0
                       for value in self.peak_memory_per_worker)
                or type(self.training_authorities) is not tuple):
            _invalid("C08_DISTRIBUTED_LOGICAL_METADATA_INVALID")
        self.manifest.__post_init__()


@dataclass(frozen=True, init=False)
class LogicalBatchGradientExecution:
    """Owner-issued raw mean gradient plus every row-scoped B11 loss execution."""

    loss_executions: tuple
    gradients: Mapping
    weighted_mean_loss: mx.array
    source_digest: str
    generation_binding: str
    plan_digest: str
    gradient_launches: int
    vectorized_microbatches: int
    materialization_barriers: int
    scalar_fallback_rows: int
    wall_seconds: float
    distributed_metadata: DistributedLogicalBatchMetadata | None = field(
        default=None, repr=False, compare=False)
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("C08_LOGICAL_BATCH_GRADIENT_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _ISSUER
                or type(self.loss_executions) is not tuple
                or len(self.loss_executions) < _LOGICAL_BATCH_MIN_ROWS
                or not isinstance(self.gradients, Mapping)
                or not self.gradients
                or any(not isinstance(value, mx.array)
                       for value in self.gradients.values())
                or not isinstance(self.weighted_mean_loss, mx.array)
                or self.weighted_mean_loss.size != 1
                or not bool(mx.all(mx.isfinite(self.weighted_mean_loss)))
                or not isinstance(self.source_digest, str)
                or not self.source_digest
                or not isinstance(self.generation_binding, str)
                or not self.generation_binding
                or not isinstance(self.plan_digest, str)
                or len(self.plan_digest) != _SHA256_HEX_LENGTH
                or any(char not in "0123456789abcdef" for char in self.plan_digest)
                or type(self.gradient_launches) is not int
                or self.gradient_launches < 1
                or type(self.vectorized_microbatches) is not int
                or not 0 <= self.vectorized_microbatches <= self.gradient_launches
                or type(self.materialization_barriers) is not int
                or self.materialization_barriers != 1
                or type(self.scalar_fallback_rows) is not int
                or not 0 <= self.scalar_fallback_rows <= len(self.loss_executions)
                or type(self.wall_seconds) is not float
                or self.wall_seconds < 0.0
                or (self.distributed_metadata is not None
                    and type(self.distributed_metadata)
                    is not DistributedLogicalBatchMetadata)):
            _invalid("C08_LOGICAL_BATCH_GRADIENT_INVALID")
        if self.distributed_metadata is not None:
            self.distributed_metadata.__post_init__()
            if self.distributed_metadata.manifest.logical_batch_digest != self.plan_digest:
                _invalid("C08_DISTRIBUTED_LOGICAL_METADATA_PLAN_DRIFT")


def require_logical_batch_gradient_execution(value):
    if type(value) is not LogicalBatchGradientExecution:
        _invalid("C08_LOGICAL_BATCH_GRADIENT_REQUIRED")
    value.__post_init__()
    return value


def _sum_tree(total, gradients):
    if total is None:
        return {name: value for name, value in gradients.items()}
    if set(total) != set(gradients):
        _invalid("C08_LOGICAL_BATCH_GRADIENT_TREE_DRIFT")
    return {name: total[name] + gradients[name] for name in total}


def _scale_tree(gradients, scale: float):
    return {name: value * mx.array(scale, dtype=value.dtype)
            for name, value in gradients.items()}


def _add_b11_observation(total: dict, execution) -> None:
    observed = getattr(execution, "_performance_observation", None)
    if not isinstance(observed, dict):
        return
    for name in (
        "b11_preflight_wall_seconds",
        "b11_finite_validation_wall_seconds",
        "b11_execution_rebinding_wall_seconds",
        "b11_refinement_selection_wall_seconds",
        "b11_route_compatibility_wall_seconds",
        "b11_route_kernel_prepare_wall_seconds",
        "b11_fallback_trace_preflight_wall_seconds",
        "b11_preflight_other_wall_seconds",
        "b11_autodiff_wall_seconds",
        "b11_autodiff_dispatch_wall_seconds",
        "b11_autodiff_dispatch_rebind_wall_seconds",
        "b11_autodiff_dispatch_source_producer_wall_seconds",
        "b11_autodiff_dispatch_source_hidden_graph_wall_seconds",
        "b11_autodiff_dispatch_refinement_graph_wall_seconds",
        "b11_autodiff_dispatch_route_graph_wall_seconds",
        "b11_autodiff_dispatch_transform_other_wall_seconds",
        "b11_autodiff_materialization_wall_seconds",
        "b11_route_evidence_wall_seconds",
        "b11_autodiff_other_wall_seconds",
        "b11_gradient_finite_validation_wall_seconds",
        "b11_postflight_validation_wall_seconds",
        "b11_postflight_trajectory_validation_wall_seconds",
        "b11_postflight_output_attestation_wall_seconds",
        "b11_postflight_loss_validation_wall_seconds",
        "b11_postflight_gradient_structure_wall_seconds",
        "b11_postflight_result_construction_wall_seconds",
    ):
        total[name] += float(observed.get(name, 0.0))
    for name in ("b11_provider_draw_count", "b11_atlas_reload_count"):
        total[name] += int(observed.get(name, 0))


def _vectorized_group(
        group, microbatch, plan, total_rows, aggregate, weighted_loss,
        losses, b11_observation):
    if type(microbatch) is not BamfMicrobatchGradientExecution:
        _invalid("C08_LOGICAL_BATCH_MICROBATCH_EXECUTION_REQUIRED")
    microbatch.__post_init__()
    _add_b11_observation(b11_observation, microbatch)
    if (len(microbatch.executions) != len(group)
            or any(execution.output.generation_binding != plan.generation_binding
                   for execution in microbatch.executions)):
        _invalid("C08_LOGICAL_BATCH_GENERATION_DRIFT")
    weight = len(group) / total_rows
    if aggregate is None and weight == 1.0:
        # The common one-group vector path already owns the exact logical-batch
        # mean. Reuse its materialized gradient tree instead of manufacturing a
        # second tree through multiply-by-one operations.
        aggregate = microbatch.gradients
        weighted_loss = microbatch.mean_loss
    else:
        aggregate = _sum_tree(aggregate, _scale_tree(microbatch.gradients, weight))
        weighted_loss = weighted_loss + (microbatch.mean_loss * weight)
    losses.extend(microbatch.executions)
    return aggregate, weighted_loss


def _scalar_group(
        group, plan, total_rows, execute_row, aggregate, weighted_loss,
        losses, b11_observation):
    group_sum = None
    group_loss = mx.array(0.0, dtype=mx.float32)
    execution_wall_seconds = 0.0
    aggregation_wall_seconds = 0.0
    for index in group:
        started = time.perf_counter()
        execution = execute_row(index)
        execution_wall_seconds += time.perf_counter() - started
        started = time.perf_counter()
        if type(execution) is not BamfGradientExecution:
            _invalid("C08_LOGICAL_BATCH_B11_EXECUTION_REQUIRED")
        execution.__post_init__()
        _add_b11_observation(b11_observation, execution)
        if execution.execution.output.generation_binding != plan.generation_binding:
            _invalid("C08_LOGICAL_BATCH_GENERATION_DRIFT")
        group_sum = _sum_tree(group_sum, execution.gradients)
        group_loss = group_loss + execution.loss_total
        losses.append(execution.execution)
        aggregation_wall_seconds += time.perf_counter() - started
    started = time.perf_counter()
    group_mean = _scale_tree(group_sum, 1.0 / len(group))
    aggregate = _sum_tree(
        aggregate, _scale_tree(group_mean, len(group) / total_rows))
    weighted_loss = weighted_loss + (
        group_loss / len(group)) * (len(group) / total_rows)
    aggregation_wall_seconds += time.perf_counter() - started
    return (
        aggregate, weighted_loss, len(group),
        execution_wall_seconds, aggregation_wall_seconds,
    )


def _logical_batch_result(
        plan, aggregate, weighted_loss, losses, gradient_launches,
        vectorized_microbatches, scalar_fallback_rows, wall_seconds,
        b11_observation):
    result = object.__new__(LogicalBatchGradientExecution)
    for name, value in (
        ("loss_executions", tuple(losses)),
        ("gradients", aggregate),
        ("weighted_mean_loss", weighted_loss),
        ("source_digest", plan.source_digest),
        ("generation_binding", plan.generation_binding),
        ("plan_digest", plan.digest),
        ("gradient_launches", gradient_launches),
        ("vectorized_microbatches", vectorized_microbatches),
        ("materialization_barriers", 1),
        ("scalar_fallback_rows", scalar_fallback_rows),
        ("wall_seconds", wall_seconds),
        ("distributed_metadata", None),
        ("_issuance", _ISSUER),
    ):
        object.__setattr__(result, name, value)
    attach_performance_observation(result, b11_observation)
    result.__post_init__()
    return result


def accumulate_logical_batch_gradients(
        plan: BatchPlan,
        execute_row: Callable[[int], BamfGradientExecution],
        *,
        execute_group: Callable[[tuple[int, ...]], BamfMicrobatchGradientExecution | None]
        | None = None,
) -> LogicalBatchGradientExecution:
    """Execute each group once when vectorizable, otherwise preserve scalar oracle."""
    if (not isinstance(plan, BatchPlan) or not callable(execute_row)
            or (execute_group is not None and not callable(execute_group))):
        _invalid("C08_LOGICAL_BATCH_GRADIENT_ARGUMENT_INVALID")
    plan.__post_init__()
    started = time.perf_counter()
    total_rows = len(plan.logical_row_ids)
    aggregate = None
    weighted_loss = mx.array(0.0, dtype=mx.float32)
    losses = []
    gradient_launches = 0
    vectorized_microbatches = 0
    scalar_fallback_rows = 0
    group_execution_wall_seconds = 0.0
    aggregation_wall_seconds = 0.0
    reused_materialized_full_batch = False
    b11_observation = {
        "b11_preflight_wall_seconds": 0.0,
        "b11_finite_validation_wall_seconds": 0.0,
        "b11_execution_rebinding_wall_seconds": 0.0,
        "b11_refinement_selection_wall_seconds": 0.0,
        "b11_route_compatibility_wall_seconds": 0.0,
        "b11_route_kernel_prepare_wall_seconds": 0.0,
        "b11_fallback_trace_preflight_wall_seconds": 0.0,
        "b11_preflight_other_wall_seconds": 0.0,
        "b11_autodiff_wall_seconds": 0.0,
        "b11_autodiff_dispatch_wall_seconds": 0.0,
        "b11_autodiff_dispatch_rebind_wall_seconds": 0.0,
        "b11_autodiff_dispatch_source_producer_wall_seconds": 0.0,
        "b11_autodiff_dispatch_source_hidden_graph_wall_seconds": 0.0,
        "b11_autodiff_dispatch_refinement_graph_wall_seconds": 0.0,
        "b11_autodiff_dispatch_route_graph_wall_seconds": 0.0,
        "b11_autodiff_dispatch_transform_other_wall_seconds": 0.0,
        "b11_autodiff_materialization_wall_seconds": 0.0,
        "b11_route_evidence_wall_seconds": 0.0,
        "b11_autodiff_other_wall_seconds": 0.0,
        "b11_gradient_finite_validation_wall_seconds": 0.0,
        "b11_postflight_validation_wall_seconds": 0.0,
        "b11_postflight_trajectory_validation_wall_seconds": 0.0,
        "b11_postflight_output_attestation_wall_seconds": 0.0,
        "b11_postflight_loss_validation_wall_seconds": 0.0,
        "b11_postflight_gradient_structure_wall_seconds": 0.0,
        "b11_postflight_result_construction_wall_seconds": 0.0,
        "b11_provider_draw_count": 0,
        "b11_atlas_reload_count": 0,
    }
    for group in plan.groups:
        group_started = time.perf_counter()
        microbatch = execute_group(group) if execute_group is not None and len(group) > 1 else None
        group_execution_wall_seconds += time.perf_counter() - group_started
        if microbatch is not None:
            aggregation_started = time.perf_counter()
            aggregate, weighted_loss = _vectorized_group(
                group, microbatch, plan, total_rows, aggregate, weighted_loss,
                losses, b11_observation)
            aggregation_wall_seconds += time.perf_counter() - aggregation_started
            reused_materialized_full_batch = (
                len(plan.groups) == 1 and len(group) == total_rows)
            gradient_launches += 1
            vectorized_microbatches += 1
            continue
        if len(group) > 1 and execute_group is not None:
            scalar_fallback_rows += len(group)
        (aggregate, weighted_loss, scalar_launches, scalar_execution_seconds,
         scalar_aggregation_seconds) = _scalar_group(
            group, plan, total_rows, execute_row, aggregate, weighted_loss,
            losses, b11_observation)
        group_execution_wall_seconds += scalar_execution_seconds
        aggregation_wall_seconds += scalar_aggregation_seconds
        gradient_launches += scalar_launches
    if len(losses) != total_rows or aggregate is None:
        _invalid("C08_LOGICAL_BATCH_EXECUTION_COVERAGE_DRIFT")
    materialization_started = time.perf_counter()
    if not reused_materialized_full_batch:
        mx.eval(aggregate, weighted_loss)
    final_materialization_wall_seconds = time.perf_counter() - materialization_started
    wall_seconds = float(time.perf_counter() - started)
    accounted_wall_seconds = (
        group_execution_wall_seconds
        + aggregation_wall_seconds
        + final_materialization_wall_seconds)
    b11_observation.update({
        "c08_group_execution_wall_seconds": float(group_execution_wall_seconds),
        "c08_aggregation_wall_seconds": float(aggregation_wall_seconds),
        "c08_final_materialization_wall_seconds": float(
            final_materialization_wall_seconds),
        "c08_unattributed_wall_seconds": float(max(
            0.0, wall_seconds - accounted_wall_seconds)),
        "c08_reused_materialized_full_batch": bool(reused_materialized_full_batch),
    })
    result_started = time.perf_counter()
    result = _logical_batch_result(
        plan, aggregate, weighted_loss, losses, gradient_launches,
        vectorized_microbatches, scalar_fallback_rows, wall_seconds,
        b11_observation)
    result_construction_wall_seconds = time.perf_counter() - result_started
    observation = dict(getattr(result, "_performance_observation", {}) or {})
    observation["c08_result_construction_wall_seconds"] = float(
        result_construction_wall_seconds)
    attach_performance_observation(result, observation)
    return result


__all__ = (
    "LogicalBatchGradientExecution", "accumulate_logical_batch_gradients",
    "require_logical_batch_gradient_execution",
)
