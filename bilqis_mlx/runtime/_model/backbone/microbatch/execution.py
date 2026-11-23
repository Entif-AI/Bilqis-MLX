"""Microbatch B11 execution and performance observation."""
from __future__ import annotations

import time

from bilqis_mlx.b11_observation import (
    attach_performance_observation, source_replay_observation,
)

from ..atlas_model_backend import Backend
from ..atlas_model_contracts import (
    BamfCompiledBatch, BamfMicrobatchGradientExecution, _invalid,
)
from ..atlas_model_forward_validation import finalize_microbatch_gradient
from ..atlas_model_training import (
    _gradient_execution_rebinder, _require_finite_tensor_tree,
)
from .compiled_batch import _MIN_ROWS, _compiled_microbatch, _microbatch_salience_labels
from .route_kernel import prepare_route_microbatch_kernel, route_microbatch_compatible
from ..atlas_model_microbatch import (
    _gradient_path, _materialize_gradient, _microbatch_objective,
    _require_materialized_finite_witness,
)


def _microbatch_performance_observation(
        result, replay, *, preflight_wall_seconds, finite_validation_wall_seconds,
        execution_rebinding_wall_seconds, preflight_timings, preflight_other_wall_seconds,
        autodiff_wall_seconds, autodiff_timings, gradient_finite_validation_wall_seconds,
        postflight_validation_wall_seconds, total_started):
    postflight = dict(getattr(result, "_performance_observation", {}) or {})
    autodiff_accounted = (
        "b11_autodiff_dispatch_wall_seconds", "b11_autodiff_materialization_wall_seconds",
        "b11_route_evidence_wall_seconds")
    autodiff_other = max(0.0, autodiff_wall_seconds - sum(
        float(autodiff_timings.get(name, 0.0) or 0.0) for name in autodiff_accounted))
    observation = {
        **postflight,
        "b11_preflight_wall_seconds": float(preflight_wall_seconds),
        "b11_finite_validation_wall_seconds": float(finite_validation_wall_seconds),
        "b11_execution_rebinding_wall_seconds": float(execution_rebinding_wall_seconds),
        **{name: float(value) for name, value in preflight_timings.items()},
        "b11_preflight_other_wall_seconds": float(preflight_other_wall_seconds),
        "b11_autodiff_wall_seconds": float(autodiff_wall_seconds),
        **{name: float(value) for name, value in autodiff_timings.items()},
        "b11_autodiff_other_wall_seconds": float(autodiff_other),
        "b11_gradient_finite_validation_wall_seconds": float(gradient_finite_validation_wall_seconds),
        "b11_postflight_validation_wall_seconds": float(postflight_validation_wall_seconds),
        "b11_materialization_barrier_count": int(
            autodiff_timings.get("b11_materialization_barrier_count", 0)),
        "b11_host_readback_count": int(
            autodiff_timings.get("b11_host_readback_count", 0)) + 1,
        "b11_validation_sync_count": int(
            postflight.get("b11_validation_sync_count", 0)),
        "b11_provider_draw_count": replay["provider_draws"],
        "b11_atlas_reload_count": replay["atlas_reloads"],
    }
    root_names = (
        "b11_preflight_wall_seconds", "b11_autodiff_wall_seconds",
        "b11_gradient_finite_validation_wall_seconds", "b11_postflight_validation_wall_seconds")
    measured_root = sum(float(observation.get(name, 0.0) or 0.0) for name in root_names)
    observation["b11_total_wall_seconds"] = float(time.perf_counter() - total_started)
    observation["b11_outer_other_wall_seconds"] = float(max(
        0.0, observation["b11_total_wall_seconds"] - measured_root))
    return observation


def _microbatch_request_context(backend, row_batches, answer_plans, targets, masks,
                                salience_supervision):
    if (type(answer_plans) is not tuple or type(targets) is not tuple
            or type(masks) is not tuple or len(row_batches) < _MIN_ROWS
            or not (len(row_batches) == len(answer_plans) == len(targets) == len(masks))):
        _invalid("B11_MICROBATCH_ARGUMENT_INVALID")
    batch = _compiled_microbatch(row_batches)
    backend.__post_init__()
    salience_labels = _microbatch_salience_labels(row_batches, salience_supervision)
    generation = answer_plans[0].generation_binding
    if any(plan.generation_binding != generation for plan in answer_plans):
        _invalid("B11_MICROBATCH_GENERATION_BINDING_MISMATCH")
    snapshot = answer_plans[0].snapshot
    if any(plan.snapshot != snapshot for plan in answer_plans):
        _invalid("B11_MICROBATCH_SEMANTIC_SNAPSHOT_MISMATCH")
    return batch, salience_labels, generation, snapshot


def _learning_first_microbatch_value_and_grad_impl(
        backend, params, row_batches, answer_plans, targets, masks, cache,
        salience_supervision):
    """Run one vectorized numerical batch without evidence preflight or replay."""
    total_started = time.perf_counter()
    batch, salience_labels, generation, snapshot = _microbatch_request_context(
        backend, row_batches, answer_plans, targets, masks, salience_supervision)
    if not route_microbatch_compatible(row_batches, answer_plans, targets, masks):
        _invalid("B11_MICROBATCH_ROUTE_KERNEL_INCOMPATIBLE")
    rebind_started = time.perf_counter()
    rebind_execution = _gradient_execution_rebinder(
        params, None, spec=backend.topology, extents=batch.compiled.extents,
        generation=generation)
    execution_rebinding_wall_seconds = time.perf_counter() - rebind_started
    refinement_selections = (None,) * len(row_batches)
    route_kernel = prepare_route_microbatch_kernel(
        row_batches, answer_plans, targets, masks, None, salience_labels)
    holder = {}
    objective = _microbatch_objective(
        backend, batch, row_batches, answer_plans, targets, masks, None,
        generation, snapshot, rebind_execution, True, None,
        refinement_selections, route_kernel, salience_supervision, holder)
    with source_replay_observation() as replay:
        autodiff_started = time.perf_counter()
        mean_loss, gradients, executions, route_trajectory, finite_witness, timings = (
            _materialize_gradient(
                objective, params, True, holder, backend, row_batches,
                answer_plans, targets, masks, salience_supervision,
                rebind_execution, refinement_selections))
        autodiff_wall_seconds = time.perf_counter() - autodiff_started
    finite_started = time.perf_counter()
    _require_materialized_finite_witness(
        finite_witness, "B11_GRADIENT_NONFINITE")
    finite_seconds = time.perf_counter() - finite_started
    postflight_started = time.perf_counter()
    result = finalize_microbatch_gradient(
        backend, batch, row_batches, None, executions, mean_loss, gradients,
        answer_plans=answer_plans, route_trajectory=route_trajectory,
        learning_first=True, numerical_finite_attested=True)
    postflight_seconds = time.perf_counter() - postflight_started
    observation = _microbatch_performance_observation(
        result, replay, preflight_wall_seconds=0.0,
        finite_validation_wall_seconds=0.0,
        execution_rebinding_wall_seconds=execution_rebinding_wall_seconds,
        preflight_timings={}, preflight_other_wall_seconds=0.0,
        autodiff_wall_seconds=autodiff_wall_seconds, autodiff_timings=timings,
        gradient_finite_validation_wall_seconds=finite_seconds,
        postflight_validation_wall_seconds=postflight_seconds,
        total_started=total_started)
    attach_performance_observation(result, observation)
    return result


def _bamf_microbatch_value_and_grad_impl(
    backend: Backend, params, row_batches: tuple[BamfCompiledBatch, ...],
    answer_plans: tuple, targets: tuple, masks: tuple, cache=None,
    *, salience_supervision=None,
) -> BamfMicrobatchGradientExecution:
    """Run one differentiable source-backbone graph for one compatible C08 group."""
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    if not strict_evidence_enabled():
        return _learning_first_microbatch_value_and_grad_impl(
            backend, params, row_batches, answer_plans, targets, masks, cache,
            salience_supervision)
    total_started = time.perf_counter()
    batch, salience_labels, generation, snapshot = _microbatch_request_context(
        backend, row_batches, answer_plans, targets, masks, salience_supervision)
    with source_replay_observation() as replay:
        preflight_started = time.perf_counter()
        stage_started = time.perf_counter()
        _require_finite_tensor_tree(params, "B11_PARAMETER_NONFINITE")
        finite_validation_wall_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        rebind_execution = _gradient_execution_rebinder(
            params, cache, spec=backend.topology, extents=batch.compiled.extents,
            generation=generation)
        execution_rebinding_wall_seconds = time.perf_counter() - stage_started
        (route_vectorized, preflight_executions, refinement_selections, route_kernel,
         preflight_timings) = (
            _gradient_path(
                backend, params, batch, row_batches, answer_plans, targets, masks,
                generation, cache, rebind_execution, salience_supervision, snapshot,
                salience_labels))
        preflight_wall_seconds = time.perf_counter() - preflight_started
        measured_preflight = (
            finite_validation_wall_seconds
            + execution_rebinding_wall_seconds
            + sum(preflight_timings.values()))
        preflight_other_wall_seconds = max(
            0.0, preflight_wall_seconds - measured_preflight)
        holder = {}
        objective = _microbatch_objective(
            backend, batch, row_batches, answer_plans, targets, masks, cache,
            generation, snapshot, rebind_execution, route_vectorized,
            preflight_executions, refinement_selections, route_kernel,
            salience_supervision, holder)
        autodiff_started = time.perf_counter()
        from bilqis_mlx.runtime.b11_source_execution_authority import (
            b11_source_authority_launch_epoch,
        )
        with b11_source_authority_launch_epoch(row_batches):
            (mean_loss, gradients, executions, route_trajectory, finite_witness,
             autodiff_timings) = _materialize_gradient(
                objective, params, route_vectorized, holder, backend, row_batches,
                answer_plans, targets, masks, salience_supervision, rebind_execution,
                refinement_selections)
        autodiff_wall_seconds = time.perf_counter() - autodiff_started
    stage_started = time.perf_counter()
    _require_materialized_finite_witness(
        finite_witness, "B11_GRADIENT_NONFINITE")
    gradient_finite_validation_wall_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    result = finalize_microbatch_gradient(
        backend, batch, row_batches, preflight_executions,
        executions, mean_loss, gradients, answer_plans=answer_plans,
        route_trajectory=route_trajectory, numerical_finite_attested=True)
    postflight_validation_wall_seconds = time.perf_counter() - stage_started
    observation = _microbatch_performance_observation(
        result, replay, preflight_wall_seconds=preflight_wall_seconds,
        finite_validation_wall_seconds=finite_validation_wall_seconds,
        execution_rebinding_wall_seconds=execution_rebinding_wall_seconds,
        preflight_timings=preflight_timings,
        preflight_other_wall_seconds=preflight_other_wall_seconds,
        autodiff_wall_seconds=autodiff_wall_seconds, autodiff_timings=autodiff_timings,
        gradient_finite_validation_wall_seconds=gradient_finite_validation_wall_seconds,
        postflight_validation_wall_seconds=postflight_validation_wall_seconds,
        total_started=total_started)
    attach_performance_observation(result, observation)
    return result
