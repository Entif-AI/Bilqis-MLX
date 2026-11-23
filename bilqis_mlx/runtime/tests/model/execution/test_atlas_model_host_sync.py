"""#1575 host synchronization and materialization-boundary regressions."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx
import pytest

import bilqis_mlx.runtime.atlas_model_forward_validation as forward_validation
import bilqis_mlx.runtime.atlas_model_microbatch as microbatch
import bilqis_mlx.runtime.microbatch.execution as microbatch_execution
import bilqis_mlx.runtime.microbatch.route_evidence as route_evidence
from bilqis_mlx.errors import BilqisError


@pytest.mark.parametrize(
    ("mean_loss", "gradients"),
    (
        (mx.array(float("nan"), dtype=mx.float32),
         {"x": mx.array(1.0, dtype=mx.float32)}),
        (mx.array(1.0, dtype=mx.float32),
         {"x": mx.array(float("inf"), dtype=mx.float32)}),
    ),
)
def test_fused_materialization_witness_rejects_nonfinite_loss_or_gradient(
        mean_loss, gradients):
    witness = microbatch._finite_gradient_witness(mean_loss, gradients)
    mx.eval(witness)
    with pytest.raises(BilqisError) as caught:
        microbatch._require_materialized_finite_witness(
            witness, "B11_GRADIENT_NONFINITE")
    assert caught.value.context["reason"] == "B11_GRADIENT_NONFINITE"


def _strict_vector_finalization_fixture(*, selected=0):
    plans = tuple(SimpleNamespace(
        decisions=(SimpleNamespace(
            decision_id="route", legal_values=("LEFT", "RIGHT")),),
        execution_order=("route",),
    ) for _ in range(2))
    executions = tuple(SimpleNamespace(
        output=SimpleNamespace(
            committed=(SimpleNamespace(decision_id="route", value="LEFT"),),
            status="complete"),
        loss=SimpleNamespace(total=mx.array(1.0, dtype=mx.float32)),
    ) for _ in range(2))
    trajectory = (mx.array((selected, 0), dtype=mx.uint32),)
    return plans, executions, trajectory


def test_strict_vectorized_finalization_accepts_materialized_route_without_preflight():
    plans, executions, trajectory = _strict_vector_finalization_fixture()
    batch = SimpleNamespace(compiled=SimpleNamespace(extents=object()))

    with patch(
            "bilqis_mlx.learning.atlas_readout.decoder.prediction.attest_issued_outputs",
            return_value=True), patch.object(
                forward_validation, "validate_bamf_parameters"), patch.object(
                    forward_validation.BamfMicrobatchGradientExecution,
                    "__post_init__", return_value=None):
        result = forward_validation.finalize_microbatch_gradient(
            SimpleNamespace(topology=object()), batch, (object(), object()), None,
            executions, mx.array(1.0, dtype=mx.float32),
            {"x": mx.array(1.0, dtype=mx.float32)},
            answer_plans=plans, route_trajectory=trajectory,
            numerical_finite_attested=True)

    assert result.executions == executions
    assert result._performance_observation["b11_validation_sync_count"] == 2


def test_strict_vectorized_finalization_rejects_materialized_route_drift():
    plans, executions, trajectory = _strict_vector_finalization_fixture(selected=1)
    batch = SimpleNamespace(compiled=SimpleNamespace(extents=object()))

    with pytest.raises(BilqisError) as caught:
        forward_validation.finalize_microbatch_gradient(
            SimpleNamespace(topology=object()), batch, (object(), object()), None,
            executions, mx.array(1.0, dtype=mx.float32),
            {"x": mx.array(1.0, dtype=mx.float32)},
            answer_plans=plans, route_trajectory=trajectory,
            numerical_finite_attested=True)

    assert caught.value.context["reason"] == "B11_MICROBATCH_TRAJECTORY_DRIFT"


def test_learning_first_real_owners_report_one_barrier_two_readbacks_no_validation_sync():
    params = {"x": mx.array(1.0, dtype=mx.float32)}
    holder = {"route_context": (object(), None, object())}
    row = SimpleNamespace(positions=(0,))
    compiled = SimpleNamespace(extents=object(), compiled=SimpleNamespace(rows=(row,)))
    rows = tuple(SimpleNamespace(
        compiled=compiled, training_authority=None) for _ in range(2))
    plans = (object(), object())

    class Backend:
        topology = object()

    def objective(current):
        loss = current["x"] * current["x"]
        hidden = mx.zeros((2, 1, 1), dtype=mx.float32) + current["x"] * 0
        trajectory = (mx.zeros((2,), dtype=mx.uint32),)
        logits = (mx.zeros((2, 2), dtype=mx.float32) + current["x"] * 0,)
        return loss, hidden, trajectory, logits, ()

    def loss_execution(output, *_args, **_kwargs):
        return SimpleNamespace(
            output=output,
            loss=SimpleNamespace(total=mx.array(1.0, dtype=mx.float32)))

    with patch.object(mx, "eval", wraps=mx.eval) as evaluate, patch.object(
            route_evidence.np, "asarray", wraps=route_evidence.np.asarray) as asarray, patch(
                "bilqis_mlx.runtime.backbone_identity.require_execution_generation_binding",
                return_value=SimpleNamespace(generation_digest="generation")), patch.object(
                    route_evidence, "validate_decode_row_input"), patch(
                        "bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode.strict_evidence_enabled",
                        return_value=False), patch.object(
                            route_evidence, "_route_output_from_materialized_logits",
                            side_effect=lambda *_args: SimpleNamespace(
                                generation_binding="generation")), patch(
                                    "bilqis_mlx.runtime.atlas_model_participation._forward_participation",
                                    return_value=object()), patch(
                                        "bilqis_mlx.runtime.atlas_model_training.loss_bearing_bamf",
                                        side_effect=loss_execution), patch(
                                            "dataclasses.replace",
                                            side_effect=lambda value, **_kwargs: value), patch.object(
                                                route_evidence, "_FORWARD_ISSUANCE",
                                                SimpleNamespace(issue=lambda *_args: None)):
        mean_loss, gradients, executions, trajectory, witness, timings = (
            microbatch._materialize_gradient(
                objective, params, True, holder, Backend(), rows, plans,
                ((), ()), ({}, {}), None, lambda _current: object(),
                (None, None)))
        microbatch._require_materialized_finite_witness(
            witness, "B11_GRADIENT_NONFINITE")
        batch = SimpleNamespace(compiled=SimpleNamespace(extents=object()))
        with patch(
                "bilqis_mlx.learning.atlas_readout.decoder.prediction.attest_issued_outputs",
                return_value=True), patch.object(
                    forward_validation, "validate_bamf_parameters"), patch.object(
                        forward_validation.BamfMicrobatchGradientExecution,
                        "__post_init__", return_value=None):
            result = forward_validation.finalize_microbatch_gradient(
                SimpleNamespace(topology=object()), batch, rows, None, executions,
                mean_loss, gradients, answer_plans=plans, route_trajectory=trajectory,
                learning_first=True, numerical_finite_attested=True)

    observation = microbatch_execution._microbatch_performance_observation(
        result, {"provider_draws": 0, "atlas_reloads": 0},
        preflight_wall_seconds=0.0, finite_validation_wall_seconds=0.0,
        execution_rebinding_wall_seconds=0.0, preflight_timings={},
        preflight_other_wall_seconds=0.0, autodiff_wall_seconds=0.0,
        autodiff_timings=timings, gradient_finite_validation_wall_seconds=0.0,
        postflight_validation_wall_seconds=0.0, total_started=0.0)
    assert evaluate.call_count == 1
    assert asarray.call_count == 1
    assert observation["b11_materialization_barrier_count"] == 1
    assert observation["b11_host_readback_count"] == 2
    assert observation["b11_validation_sync_count"] == 0
