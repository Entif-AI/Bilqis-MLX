"""Row-scoped validation for B11 source-backed forward decoding."""
from __future__ import annotations

import mlx.core as mx
import time

from bilqis_mlx.b11_observation import attach_performance_observation
from .atlas_model_contracts import (
    BamfMicrobatchGradientExecution, _MICROBATCH_EXECUTION_ISSUER, _invalid,
)
from bilqis_mlx.runtime.model_topology_v2 import validate_bamf_parameters
from .atlas_model_forward_preflight import (
    microbatch_trace_from_hidden, microbatch_trace_preflight,
    validate_decode_row_custody, validate_decode_row_input, validate_task_plan_custody,
)
from .atlas_model_route_evidence import microbatch_trace_from_route


def _validate_route_trajectory(answer_plans, executions, trajectory):
    if (type(answer_plans) is not tuple or type(executions) is not tuple
            or type(trajectory) is not tuple
            or len(answer_plans) != len(executions)):
        _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")
    ordered = tuple(
        tuple({item.decision_id: item for item in plan.decisions}[key]
              for key in plan.execution_order)
        for plan in answer_plans)
    if len(trajectory) != max(len(items) for items in ordered):
        _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")
    committed = tuple(
        {item.decision_id: item.value for item in execution.output.committed}
        for execution in executions)
    for index, observed in enumerate(trajectory):
        expected = []
        for items, values in zip(ordered, committed):
            if index >= len(items):
                expected.append(0)
                continue
            decision = items[index]
            if decision.decision_id not in values:
                _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")
            value = values[decision.decision_id]
            try:
                expected.append(decision.legal_values.index(value))
            except ValueError:
                _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")
        expected_array = mx.array(tuple(expected), dtype=observed.dtype)
        if not bool(mx.all(observed == expected_array)):
            _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")


def finalize_microbatch_gradient(
    backend, batch, row_batches, preflight_executions,
    executions, mean_loss, gradients, *, answer_plans=None, route_trajectory=None,
):
    """Verify row evidence, numerical parity and issue one microbatch result."""
    finalize_started = time.perf_counter()
    from bilqis_mlx.learning.atlas_readout.decoder.prediction import (
        attest_issued_outputs,
    )

    stage_started = time.perf_counter()
    if preflight_executions is None:
        if (type(executions) is not tuple or len(executions) != len(row_batches)
                or route_trajectory is None):
            _invalid("B11_MICROBATCH_EXECUTION_MISSING")
        _validate_route_trajectory(answer_plans, executions, route_trajectory)
        reference_executions = executions
    else:
        reused_preflight_evidence = executions is None
        if reused_preflight_evidence:
            executions = preflight_executions
        elif type(executions) is not tuple or len(executions) != len(row_batches):
            _invalid("B11_MICROBATCH_EXECUTION_MISSING")
        if not reused_preflight_evidence and any(
                execution.output.committed != preflight.output.committed
                or execution.output.status is not preflight.output.status
                for execution, preflight in zip(executions, preflight_executions)):
            _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")
        reference_executions = preflight_executions
    trajectory_validation_seconds = time.perf_counter() - stage_started
    if type(executions) is not tuple or len(executions) != len(row_batches):
        _invalid("B11_MICROBATCH_EXECUTION_MISSING")
    stage_started = time.perf_counter()
    if not attest_issued_outputs(tuple(execution.output for execution in executions)):
        _invalid("B11_MICROBATCH_OUTPUT_ATTESTATION_FAILED")
    output_attestation_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    reference_mean = sum(
        (execution.loss.total for execution in reference_executions),
        mx.array(0.0, dtype=mx.float32)) / len(reference_executions)
    if not bool(mx.allclose(mean_loss, reference_mean, rtol=1e-5, atol=1e-6)):
        _invalid("B11_MICROBATCH_LOSS_DRIFT")
    loss_validation_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    validate_bamf_parameters(
        backend.topology, batch.compiled.extents, gradients)
    gradient_structure_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    result = object.__new__(BamfMicrobatchGradientExecution)
    for name, value in (
        ("executions", executions), ("gradients", gradients),
        ("mean_loss", mean_loss),
        ("schema_version", "bilqis.mlx.b11-microbatch-gradient-execution/v1"),
        ("_issuance", _MICROBATCH_EXECUTION_ISSUER),
    ):
        object.__setattr__(result, name, value)
    result.__post_init__()
    result_construction_seconds = time.perf_counter() - stage_started
    observation = {
        "b11_postflight_trajectory_validation_wall_seconds": float(
            trajectory_validation_seconds),
        "b11_postflight_output_attestation_wall_seconds": float(
            output_attestation_seconds),
        "b11_postflight_loss_validation_wall_seconds": float(
            loss_validation_seconds),
        "b11_postflight_gradient_structure_wall_seconds": float(
            gradient_structure_seconds),
        "b11_postflight_result_construction_wall_seconds": float(
            result_construction_seconds),
    }
    measured = sum(observation.values())
    observation["b11_postflight_other_wall_seconds"] = float(max(
        0.0, time.perf_counter() - finalize_started - measured))
    attach_performance_observation(result, observation)
    return result


__all__ = (
    "finalize_microbatch_gradient",
    "microbatch_trace_from_hidden",
    "microbatch_trace_from_route",
    "microbatch_trace_preflight",
    "validate_decode_row_custody",
    "validate_decode_row_input",
    "validate_task_plan_custody",
)
