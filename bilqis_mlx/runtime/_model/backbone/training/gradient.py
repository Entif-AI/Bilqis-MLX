"""Scalar B11 gradient execution behind the stable training facade."""
from __future__ import annotations

import time

import mlx.core as mx

from bilqis_mlx.learning.atlas_readout import AnswerPlan, DecisionOutput, ExecutionMode
from bilqis_mlx.learning.atlas_readout.decoder.prediction import attest_issued_output
from bilqis_mlx.runtime.backbone_identity import (
    _execution_generation_autodiff_rebinder,
    issue_execution_generation_binding,
    issue_learning_first_execution_generation_binding,
)
from bilqis_mlx.runtime.bamf_bundle.execution_cache import bind_execution_generation
from bilqis_mlx.runtime.model_topology_v2 import validate_bamf_parameters
from bilqis_mlx.runtime.autodiff_trace import defer_host_tensor_validation
from bilqis_mlx.b11_observation import (
    attach_performance_observation, source_replay_observation,
)

from ..atlas_model_backend import Backend
from ..atlas_model_contracts import (
    BamfCompiledBatch, BamfGradientExecution, BamfLossExecution,
    _LOSS_EXECUTION_ISSUER, _invalid,
)
from ..atlas_model_forward import _forward_bamf_impl
from ..atlas_model_training import loss_bearing_bamf, _require_finite_tensor_tree


def _gradient_execution_rebinder(params, cache, *, spec, extents, generation):
    if cache is None:
        from bilqis_mlx.runtime.candidate.step_authority import (
            learning_first_step_authority_exists,
            record_learning_first_full_proof_fallback,
        )
        if learning_first_step_authority_exists(generation):
            binding = issue_learning_first_execution_generation_binding(
                params, spec=spec, extents=extents, generation=generation)
        else:
            from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
                strict_evidence_enabled,
            )
            if not strict_evidence_enabled():
                record_learning_first_full_proof_fallback()
            binding = issue_execution_generation_binding(
                params, spec=spec, extents=extents,
                expected_generation=generation)
    else:
        binding = bind_execution_generation(
            cache, params, spec=spec, extents=extents)
    if binding.generation_digest != generation:
        _invalid("B11_GRADIENT_GENERATION_BINDING_MISMATCH")
    return _execution_generation_autodiff_rebinder(
        binding, params, spec=spec, extents=extents)


def _gradient_preflight(
        backend, params, compiled_batch, answer_plan, targets, mask, cache,
        salience_supervision, source_loss_multiplier):
    started = time.perf_counter()
    _require_finite_tensor_tree(params, "B11_PARAMETER_NONFINITE")
    rebind_execution = _gradient_execution_rebinder(
        params, cache, spec=backend.topology, extents=compiled_batch.compiled.extents,
        generation=answer_plan.generation_binding)
    preflight_binding = rebind_execution(params)
    from bilqis_mlx.runtime.b11_source_execution_authority import (
        b11_source_authority_launch_epoch,
    )
    with b11_source_authority_launch_epoch((compiled_batch,)):
        preflight_output = _forward_bamf_impl(
            backend, params, compiled_batch, answer_plan, ExecutionMode.INFERENCE, cache,
            refinement_training=True, execution_binding=preflight_binding,
            decoder_trace=False)
    preflight_execution = loss_bearing_bamf(
        preflight_output, targets, mask, salience_supervision=salience_supervision,
        source_loss_multiplier=source_loss_multiplier)
    return (
        rebind_execution, preflight_output, preflight_execution,
        time.perf_counter() - started,
    )


def _finalize_gradient_execution(
        backend, compiled_batch, execution, preflight_output, preflight_execution,
        loss_total, gradients, observation):
    _require_finite_tensor_tree(gradients, "B11_GRADIENT_NONFINITE")
    if type(execution) is not BamfLossExecution:
        _invalid("B11_GRADIENT_EXECUTION_MISSING")
    if not attest_issued_output(execution.output):
        _invalid("B11_TRAINING_OUTPUT_ATTESTATION_FAILED")
    if (execution.output.committed != preflight_output.committed
            or execution.output.status is not preflight_output.status):
        _invalid("B11_TRAINING_TRAJECTORY_DRIFT")
    if not bool(mx.allclose(
            execution.loss.total, preflight_execution.loss.total,
            rtol=1e-5, atol=1e-6)):
        _invalid("B11_TRAINING_LOSS_DRIFT")
    validate_bamf_parameters(
        backend.topology, compiled_batch.compiled.extents, gradients)
    return _issue_gradient_execution(execution, loss_total, gradients, observation)


def _issue_gradient_execution(execution, loss_total, gradients, observation):
    result = object.__new__(BamfGradientExecution)
    for name, value in (
        ("execution", execution),
        ("gradients", gradients),
        ("loss_total", loss_total),
        ("schema_version", "bilqis.mlx.b11-gradient-execution/v1"),
        ("_issuance", _LOSS_EXECUTION_ISSUER),
    ):
        object.__setattr__(result, name, value)
    attach_performance_observation(result, observation)
    result.__post_init__()
    return result


def _learning_first_value_and_grad_impl(
        backend, params, compiled_batch, answer_plan, targets, mask, cache,
        salience_supervision, source_loss_multiplier):
    """Run one numerical training pass with no evidence replay or preflight."""
    rebind_execution = _gradient_execution_rebinder(
        params, None, spec=backend.topology,
        extents=compiled_batch.compiled.extents,
        generation=answer_plan.generation_binding)
    holder = {}
    with source_replay_observation() as replay:
        def objective(current):
            with defer_host_tensor_validation():
                execution_binding = rebind_execution(current)
                output = _forward_bamf_impl(
                    backend, current, compiled_batch, answer_plan,
                    ExecutionMode.INFERENCE, None,
                    refinement_training=True,
                    execution_binding=execution_binding,
                    decoder_trace=False)
                execution = loss_bearing_bamf(
                    output, targets, mask,
                    salience_supervision=salience_supervision,
                    source_loss_multiplier=source_loss_multiplier,
                    validate_finite=False)
                holder["execution"] = execution
                return execution.loss.total

        autodiff_started = time.perf_counter()
        loss_total, gradients = mx.value_and_grad(objective)(params)
        mx.eval(loss_total, gradients)
        autodiff_wall_seconds = time.perf_counter() - autodiff_started
    _require_finite_tensor_tree(gradients, "B11_GRADIENT_NONFINITE")
    validate_bamf_parameters(
        backend.topology, compiled_batch.compiled.extents, gradients)
    return _issue_gradient_execution(
        holder.get("execution"), loss_total, gradients, {
            "b11_preflight_wall_seconds": 0.0,
            "b11_autodiff_wall_seconds": float(autodiff_wall_seconds),
            "b11_provider_draw_count": replay["provider_draws"],
            "b11_atlas_reload_count": replay["atlas_reloads"],
        })


def _bamf_value_and_grad_impl(
    backend: Backend,
    params,
    compiled_batch: BamfCompiledBatch,
    answer_plan: AnswerPlan,
    targets: tuple[DecisionOutput, ...],
    mask,
    cache=None,
    *, salience_supervision=None, source_loss_multiplier: float = 1.0,
) -> BamfGradientExecution:
    """Run one exact forward/loss/gradient dispatch with one execution identity."""
    if salience_supervision is not None:
        from .salience_training import PortableSalienceSupervision, SalienceSupervision
        if type(salience_supervision) not in (
                SalienceSupervision, PortableSalienceSupervision):
            _invalid("BAMF_SALIENCE_SUPERVISION_REQUIRED")
        salience_supervision.labels_for(compiled_batch)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    if not strict_evidence_enabled():
        return _learning_first_value_and_grad_impl(
            backend, params, compiled_batch, answer_plan, targets, mask, cache,
            salience_supervision, source_loss_multiplier)
    with source_replay_observation() as replay:
        (
            rebind_execution, preflight_output, preflight_execution,
            preflight_wall_seconds,
        ) = _gradient_preflight(
            backend, params, compiled_batch, answer_plan, targets, mask, cache,
            salience_supervision, source_loss_multiplier)
        holder = {}

        def objective(current):
            with defer_host_tensor_validation():
                execution_binding = rebind_execution(current)
                output = _forward_bamf_impl(
                    backend,
                    current,
                    compiled_batch,
                    answer_plan,
                    ExecutionMode.INFERENCE,
                    cache,
                    refinement_training=True,
                    execution_binding=execution_binding,
                    replay_output=preflight_output,
                )
                execution = loss_bearing_bamf(
                    output, targets, mask,
                    salience_supervision=salience_supervision,
                    source_loss_multiplier=source_loss_multiplier,
                    validate_finite=False)
                holder["execution"] = execution
                return execution.loss.total

        from bilqis_mlx.runtime.b11_source_execution_authority import (
            b11_source_authority_launch_epoch,
        )
        autodiff_started = time.perf_counter()
        with b11_source_authority_launch_epoch((compiled_batch,)):
            loss_total, gradients = mx.value_and_grad(objective)(params)
        mx.eval(loss_total, gradients)
        autodiff_wall_seconds = time.perf_counter() - autodiff_started
    return _finalize_gradient_execution(
        backend, compiled_batch, holder.get("execution"), preflight_output,
        preflight_execution, loss_total, gradients, {
        "b11_preflight_wall_seconds": float(preflight_wall_seconds),
        "b11_autodiff_wall_seconds": float(autodiff_wall_seconds),
        "b11_provider_draw_count": replay["provider_draws"],
        "b11_atlas_reload_count": replay["atlas_reloads"],
    })
