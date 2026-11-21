"""C08 owner for raw MLX gradient-tree accumulation across one logical batch."""
from __future__ import annotations

import time
from typing import Callable

import mlx.core as mx

from bilqis_mlx.b11_observation import attach_performance_observation
from bilqis_mlx.runtime.atlas_model import (
    BamfGradientExecution, BamfMicrobatchGradientExecution,
)
from bilqis_mlx.runtime.atlas_resources import BatchPlan

from .c08_gradient_contracts import (
    DistributedLogicalBatchMetadata, LogicalBatchGradientExecution, _ISSUER,
    _add_b11_observation, _invalid, _scale_tree, _sum_tree,
    require_logical_batch_gradient_execution,
)


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
