"""True MLX microbatch execution while preserving row-scoped B11 evidence."""
from __future__ import annotations

import time

import mlx.core as mx

from .atlas_model_backend import Backend, model_backend
from .atlas_model_contracts import (
    BamfCompiledBatch, BamfMicrobatchGradientExecution,
    _invalid,
)
from .atlas_model_forward import (
    _decode_bamf_producer_row, _finalize_source_hidden, _source_producer,
)
from .atlas_model_forward_validation import (
    finalize_microbatch_gradient, microbatch_trace_from_hidden,
    microbatch_trace_from_route, microbatch_trace_preflight,
)
from .atlas_model_training import (
    _gradient_execution_rebinder, _require_finite_tensor_tree, loss_bearing_bamf,
)
from .microbatch.refinement_kernel import (
    batched_refine_hidden_with_routing,
    batched_refinement_routing_loss, prepare_refinement_selections,
)
from .microbatch.compiled_batch import (
    _MIN_ROWS, _compiled_microbatch, _microbatch_salience_labels,
    microbatch_compatible,
)
from .microbatch.gradient_preflight import gradient_path as _gradient_path_impl
from .microbatch.route_kernel import (
    prepare_route_microbatch_kernel, route_microbatch_compatible,
    route_microbatch_loss_and_trajectory,
)
from bilqis_mlx.runtime.autodiff_trace import defer_host_tensor_validation
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.b11_observation import (
    attach_performance_observation, source_replay_observation,
)


_ROUTE_CONTEXT_FIELDS = 3

_DISPATCH_CHILD_FIELDS = (
    "b11_autodiff_dispatch_rebind_wall_seconds",
    "b11_autodiff_dispatch_source_producer_wall_seconds",
    "b11_autodiff_dispatch_source_hidden_graph_wall_seconds",
    "b11_autodiff_dispatch_refinement_graph_wall_seconds",
    "b11_autodiff_dispatch_route_graph_wall_seconds",
)


def _attach_dispatch_timings(timings, holder):
    children = holder.get("dispatch_timings", {})
    for key in _DISPATCH_CHILD_FIELDS:
        timings[key] = float(children.get(key, 0.0) or 0.0)
    timings["b11_autodiff_dispatch_transform_other_wall_seconds"] = max(
        0.0,
        float(timings["b11_autodiff_dispatch_wall_seconds"])
        - sum(float(timings[key]) for key in _DISPATCH_CHILD_FIELDS),
    )


def _finite_tensor_tree_witness(values):
    """Build one lazy scalar finite witness for an already-issued tensor tree."""
    checks = tuple(mx.all(mx.isfinite(value)) for value in values.values())
    if not checks:
        _invalid("B11_GRADIENT_NONFINITE")
    return mx.all(mx.stack(checks))


def _require_materialized_finite_witness(witness, code):
    """Inspect a witness already included in the owner's materialization barrier."""
    if not bool(witness):
        _invalid(code)


def _gradient_path(
        backend, params, batch, row_batches, answer_plans, targets, masks,
        generation, cache, rebind_execution, salience_supervision, snapshot,
        salience_labels):
    return _gradient_path_impl(
        backend, params, batch, row_batches, answer_plans, targets, masks,
        generation, cache, rebind_execution, salience_supervision, snapshot,
        salience_labels,
        prepare_refinement_selections=prepare_refinement_selections,
        route_microbatch_compatible=route_microbatch_compatible,
        microbatch_trace_preflight=microbatch_trace_preflight,
        prepare_route_microbatch_kernel=prepare_route_microbatch_kernel)


def _materialize_gradient(
        objective, params, route_vectorized, holder, backend, row_batches,
        answer_plans, targets, masks, salience_supervision, rebind_execution,
        refinement_selections):
    timings = {
        "b11_autodiff_dispatch_wall_seconds": 0.0,
        "b11_autodiff_materialization_wall_seconds": 0.0,
        "b11_route_evidence_wall_seconds": 0.0,
    }
    if not route_vectorized:
        started = time.perf_counter()
        mean_loss, gradients = mx.value_and_grad(objective)(params)
        timings["b11_autodiff_dispatch_wall_seconds"] = time.perf_counter() - started
        _attach_dispatch_timings(timings, holder)
        finite_witness = _finite_tensor_tree_witness(gradients)
        started = time.perf_counter()
        mx.eval(mean_loss, gradients, finite_witness)
        timings["b11_autodiff_materialization_wall_seconds"] = (
            time.perf_counter() - started)
        return (
            mean_loss, gradients, holder.get("executions"), None,
            finite_witness, timings,
        )
    started = time.perf_counter()
    (mean_loss, route_hidden, route_trajectory, route_logits,
     refinement_route_logits), gradients = mx.value_and_grad(
        objective)(params)
    timings["b11_autodiff_dispatch_wall_seconds"] = time.perf_counter() - started
    _attach_dispatch_timings(timings, holder)
    finite_witness = _finite_tensor_tree_witness(gradients)
    started = time.perf_counter()
    mx.eval(
        mean_loss, gradients, route_hidden, route_trajectory, route_logits,
        refinement_route_logits, finite_witness)
    timings["b11_autodiff_materialization_wall_seconds"] = (
        time.perf_counter() - started)
    started = time.perf_counter()
    route_context = holder.get("route_context")
    if (type(route_context) is not tuple
            or len(route_context) != _ROUTE_CONTEXT_FIELDS):
        _invalid("B11_MICROBATCH_EXECUTION_MISSING")
    producer, accepted_cache, _trace_binding = route_context
    execution_binding = rebind_execution(params)
    executions = microbatch_trace_from_route(
        backend, params, row_batches, answer_plans, targets, masks,
        producer, route_hidden, accepted_cache, execution_binding,
        salience_supervision, refinement_selections, route_trajectory, route_logits,
        refinement_route_logits)
    timings["b11_route_evidence_wall_seconds"] = time.perf_counter() - started
    return (
        mean_loss, gradients, executions, route_trajectory,
        finite_witness, timings,
    )


def _microbatch_objective(
        backend, batch, row_batches, answer_plans, targets, masks, cache,
        generation, snapshot, rebind_execution, route_vectorized,
        preflight_executions, refinement_selections, route_kernel,
        salience_supervision, holder):
    dispatch_timings = {key: 0.0 for key in _DISPATCH_CHILD_FIELDS}
    holder["dispatch_timings"] = dispatch_timings

    def objective(current):
        with defer_host_tensor_validation():
            started = time.perf_counter()
            execution_binding = rebind_execution(current)
            dispatch_timings["b11_autodiff_dispatch_rebind_wall_seconds"] += (
                time.perf_counter() - started)
            started = time.perf_counter()
            producer, accepted_cache, _capture_derived_cache = _source_producer(
                current, batch, generation, cache, execution_binding,
                trace=True, snapshot=snapshot)
            dispatch_timings["b11_autodiff_dispatch_source_producer_wall_seconds"] += (
                time.perf_counter() - started)
            started = time.perf_counter()
            hidden = _finalize_source_hidden(
                producer, accepted_cache, batch, capture_derived_cache=False)
            dispatch_timings[
                "b11_autodiff_dispatch_source_hidden_graph_wall_seconds"
            ] += time.perf_counter() - started
            if hidden.shape[0] != len(row_batches):
                _invalid("B11_MICROBATCH_HIDDEN_BATCH_MISMATCH")
            if not route_vectorized:
                executions = []
                total = mx.array(0.0, dtype=mx.float32)
                for index, (row_batch, plan, row_targets, mask) in enumerate(zip(
                        row_batches, answer_plans, targets, masks)):
                    output = _decode_bamf_producer_row(
                        backend, current, row_batch, plan, producer, hidden, index,
                        accepted_cache, execution_binding, refinement_training=True,
                        trace=True, replay_output=preflight_executions[index].output)
                    execution = loss_bearing_bamf(
                        output, row_targets, mask,
                        salience_supervision=salience_supervision,
                        validate_finite=False)
                    executions.append(execution)
                    total = total + execution.loss.total
                holder["executions"] = tuple(executions)
                return total / len(row_batches)
            holder["route_context"] = (producer, accepted_cache, execution_binding)
            salience_hidden = hidden
            started = time.perf_counter()
            refined, refinement_routing = batched_refine_hidden_with_routing(
                current, row_batches, producer, hidden, refinement_selections)
            refinement_routing_loss = batched_refinement_routing_loss(
                refinement_routing, len(row_batches))
            dispatch_timings["b11_autodiff_dispatch_refinement_graph_wall_seconds"] += (
                time.perf_counter() - started)
            started = time.perf_counter()
            mean_loss, trajectory, route_logits = route_microbatch_loss_and_trajectory(
                current, refined, route_kernel, salience_hidden=salience_hidden,
                refinement_routing_loss=refinement_routing_loss,
                return_logits=True)
            dispatch_timings["b11_autodiff_dispatch_route_graph_wall_seconds"] += (
                time.perf_counter() - started)
            return (
                mean_loss, hidden, trajectory, route_logits,
                tuple(item[0] for item in refinement_routing))

    return objective


def _bamf_microbatch_value_and_grad_impl(
    backend: Backend,
    params,
    row_batches: tuple[BamfCompiledBatch, ...],
    answer_plans: tuple,
    targets: tuple,
    masks: tuple,
    cache=None,
    *, salience_supervision=None,
) -> BamfMicrobatchGradientExecution:
    """Run one differentiable source-backbone graph for one compatible C08 group."""
    total_started = time.perf_counter()
    if (type(answer_plans) is not tuple or type(targets) is not tuple
            or type(masks) is not tuple or len(row_batches) < _MIN_ROWS
            or not (len(row_batches) == len(answer_plans) == len(targets) == len(masks))):
        _invalid("B11_MICROBATCH_ARGUMENT_INVALID")
    batch = _compiled_microbatch(row_batches)
    backend.__post_init__()
    salience_labels = _microbatch_salience_labels(
        row_batches, salience_supervision)
    generation = answer_plans[0].generation_binding
    if any(plan.generation_binding != generation for plan in answer_plans):
        _invalid("B11_MICROBATCH_GENERATION_BINDING_MISMATCH")
    snapshot = answer_plans[0].snapshot
    if any(plan.snapshot != snapshot for plan in answer_plans):
        _invalid("B11_MICROBATCH_SEMANTIC_SNAPSHOT_MISMATCH")
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
        route_trajectory=route_trajectory)
    postflight_validation_wall_seconds = time.perf_counter() - stage_started
    postflight_observation = dict(
        getattr(result, "_performance_observation", {}) or {})
    autodiff_other_wall_seconds = max(
        0.0,
        autodiff_wall_seconds
        - sum(float(autodiff_timings.get(name, 0.0) or 0.0) for name in (
            "b11_autodiff_dispatch_wall_seconds",
            "b11_autodiff_materialization_wall_seconds",
            "b11_route_evidence_wall_seconds",
        )),
    )
    observation = {
        **postflight_observation,
        "b11_preflight_wall_seconds": float(preflight_wall_seconds),
        "b11_finite_validation_wall_seconds": float(
            finite_validation_wall_seconds),
        "b11_execution_rebinding_wall_seconds": float(
            execution_rebinding_wall_seconds),
        **{name: float(value) for name, value in preflight_timings.items()},
        "b11_preflight_other_wall_seconds": float(preflight_other_wall_seconds),
        "b11_autodiff_wall_seconds": float(autodiff_wall_seconds),
        **{name: float(value) for name, value in autodiff_timings.items()},
        "b11_autodiff_other_wall_seconds": float(autodiff_other_wall_seconds),
        "b11_gradient_finite_validation_wall_seconds": float(
            gradient_finite_validation_wall_seconds),
        "b11_postflight_validation_wall_seconds": float(
            postflight_validation_wall_seconds),
        "b11_provider_draw_count": replay["provider_draws"],
        "b11_atlas_reload_count": replay["atlas_reloads"],
    }
    measured_root = sum(float(observation.get(name, 0.0) or 0.0) for name in (
        "b11_preflight_wall_seconds",
        "b11_autodiff_wall_seconds",
        "b11_gradient_finite_validation_wall_seconds",
        "b11_postflight_validation_wall_seconds",
    ))
    observation["b11_total_wall_seconds"] = float(
        time.perf_counter() - total_started)
    observation["b11_outer_other_wall_seconds"] = float(max(
        0.0, observation["b11_total_wall_seconds"] - measured_root))
    attach_performance_observation(result, observation)
    return result


def bamf_microbatch_value_and_grad(
    params,
    row_batches: tuple[BamfCompiledBatch, ...],
    answer_plans: tuple,
    targets: tuple,
    masks: tuple,
    cache=None,
    *, salience_supervision=None,
) -> BamfMicrobatchGradientExecution:
    return model_backend(ModelTopologySpecV2()).microbatch_value_and_grad(
        params, row_batches, answer_plans, targets, masks, cache,
        salience_supervision=salience_supervision)


__all__ = ("bamf_microbatch_value_and_grad", "microbatch_compatible")
