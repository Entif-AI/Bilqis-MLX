"""#1265 one-backbone model-owned trajectory witnesses."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx
import numpy as np
import pytest

import bilqis_mlx.runtime.atlas_model_microbatch as microbatch
import bilqis_mlx.runtime.microbatch.execution as microbatch_execution
import bilqis_mlx.runtime.atlas_model_forward_validation as validation
import bilqis_mlx.runtime.atlas_model_forward as forward
import bilqis_mlx.runtime.atlas_model_training as training
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout import DecisionKind, DecisionOutput, DecisionSpec
from bilqis_mlx.runtime.microbatch.route_kernel import (
    prepare_route_microbatch_inference_kernel, prepare_route_microbatch_kernel,
    route_microbatch_loss_and_trajectory, route_microbatch_compatible,
    route_microbatch_mean_loss, route_microbatch_trajectory,
)
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
def _parameters():
    width, inner = ModelTopologySpecV2.width, 192
    return {
        "features.role": mx.stack((
            mx.zeros((width,), dtype=mx.float32),
            mx.arange(width, dtype=mx.float32) / 1000.0,
        )),
        "features.gates": mx.zeros((4,), dtype=mx.float32),
        "features.project_role": mx.eye(width, dtype=mx.float32),
        "readout.feedback": mx.eye(width, dtype=mx.float32) * 0.02,
        "readout.state_norm": mx.ones((width,), dtype=mx.float32),
        "readout.output_norm": mx.ones((width,), dtype=mx.float32),
        "readout.key": mx.eye(inner, width, dtype=mx.float32),
        "readout.value": mx.eye(inner, width, dtype=mx.float32),
        "readout.query": mx.eye(inner, width, dtype=mx.float32),
        "readout.output": mx.eye(width, inner, dtype=mx.float32),
    }


def _route_fixture(target_first=("op.b", "op.a")):
    first = (
        DecisionSpec("op", None, 0, DecisionKind.OPERATOR, ("op.a", "op.b")),
        DecisionSpec(
            "arg", None, 1, DecisionKind.OPERAND,
            ("arg.a", "arg.b"), ("op",)),
    )
    plans = tuple(SimpleNamespace(
        route_only=True, decisions=first, execution_order=("op", "arg"))
        for _ in range(2))
    targets = tuple((
        DecisionOutput("op", selected),
        DecisionOutput("arg", "arg.b" if index == 0 else "arg.a"),
    ) for index, selected in enumerate(target_first))
    masks = ({"op": True, "arg": True},) * 2
    features = SimpleNamespace(role_map=(("UNKNOWN", 0), ("NONE", 1)))
    extents = SimpleNamespace()
    rows = tuple(SimpleNamespace(compiled=SimpleNamespace(
        compiled=SimpleNamespace(rows=(SimpleNamespace(positions=(None,) * 3),)),
        features=features, extents=extents)) for _ in range(2))
    kernel = prepare_route_microbatch_kernel(
        rows, plans, targets, masks, None)
    hidden = (mx.arange(2 * 3 * ModelTopologySpecV2.width, dtype=mx.float32)
              .reshape(2, 3, ModelTopologySpecV2.width) / 10000.0)
    return rows, plans, targets, masks, kernel, hidden


def test_route_trajectory_is_model_owned_and_label_independent():
    params = _parameters()
    *_prefix, first_kernel, hidden = _route_fixture(("op.a", "op.b"))
    *_prefix, second_kernel, _ = _route_fixture(("op.b", "op.a"))
    first_loss, first_trajectory = route_microbatch_loss_and_trajectory(
        params, hidden, first_kernel)
    second_loss, second_trajectory = route_microbatch_loss_and_trajectory(
        params, hidden, second_kernel)
    mx.eval(first_loss, second_loss, first_trajectory, second_trajectory)

    assert any(not bool(mx.all(left == right))
               for left, right in zip(
                   first_kernel.target_indices, second_kernel.target_indices))
    assert len(first_trajectory) == len(second_trajectory) == 2
    for left, right in zip(first_trajectory, second_trajectory):
        np.testing.assert_array_equal(np.asarray(left), np.asarray(right))


def test_inference_kernel_preserves_model_owned_route_trajectory():
    params = _parameters()
    rows, plans, _targets, _masks, supervised, hidden = _route_fixture()
    inference = prepare_route_microbatch_inference_kernel(rows, plans)

    supervised_trajectory, _ = route_microbatch_trajectory(
        params, hidden, supervised)
    inference_trajectory, _ = route_microbatch_trajectory(
        params, hidden, inference)
    mx.eval(supervised_trajectory, inference_trajectory)

    for supervised_choice, inference_choice in zip(
            supervised_trajectory, inference_trajectory):
        np.testing.assert_array_equal(
            np.asarray(supervised_choice), np.asarray(inference_choice))


def test_partial_route_supervision_is_not_eligible_for_one_backbone_path():
    rows, plans, targets, masks, _kernel, _hidden = _route_fixture()
    partial_targets = tuple((row[0],) for row in targets)
    partial_masks = tuple({"op": True, "arg": False} for _ in rows)
    assert not route_microbatch_compatible(
        rows, plans, partial_targets, partial_masks)


def test_model_owned_route_feedback_keeps_downstream_feedback_gradient():
    params = _parameters()
    *_prefix, kernel, hidden = _route_fixture()

    def objective(feedback):
        current = {**params, "readout.feedback": feedback}
        return route_microbatch_loss_and_trajectory(current, hidden, kernel)[0]

    gradient = mx.grad(objective)(params["readout.feedback"])
    mx.eval(gradient)
    assert bool(mx.all(mx.isfinite(gradient)))
    assert float(mx.sum(mx.abs(gradient))) > 0


def test_same_model_trajectory_matches_frozen_preflight_loss_and_gradients():
    params = _parameters()
    *_prefix, kernel, hidden = _route_fixture()
    _loss, trajectory = route_microbatch_loss_and_trajectory(
        params, hidden, kernel)
    mx.eval(trajectory)
    first_choice = mx.sum(
        kernel.candidate_vectors[0]
        * (mx.arange(kernel.candidate_vectors[0].shape[1])[None, :]
           == trajectory[0][:, None])[..., None],
        axis=1)
    fixed = replace(
        kernel,
        feedback=(
            mx.zeros_like(first_choice),
            first_choice,
        ),
        dependency_masks=(),
    )

    dynamic_loss, dynamic_gradients = mx.value_and_grad(
        lambda current: route_microbatch_loss_and_trajectory(
            current, hidden, kernel)[0])(params)
    fixed_loss, fixed_gradients = mx.value_and_grad(
        lambda current: route_microbatch_mean_loss(
            current, hidden, fixed))(params)
    mx.eval(dynamic_loss, dynamic_gradients, fixed_loss, fixed_gradients)
    np.testing.assert_allclose(
        np.asarray(dynamic_loss), np.asarray(fixed_loss), rtol=1e-6, atol=1e-7)
    for name in params:
        np.testing.assert_allclose(
            np.asarray(dynamic_gradients[name]), np.asarray(fixed_gradients[name]),
            rtol=1e-5, atol=1e-6)


def test_route_gradient_launch_executes_one_source_backbone_and_no_preflight():
    rows = (object(),) * 4
    snapshot = object()
    plans = tuple(SimpleNamespace(
        generation_binding="generation", snapshot=snapshot) for _ in rows)
    batch = SimpleNamespace(compiled=SimpleNamespace(extents=object()))
    params = {"x": mx.array(1.0, dtype=mx.float32)}

    class Backend:
        topology = object()

        def __post_init__(self):
            return None

    producer = object()
    with patch.object(
            microbatch_execution, "_compiled_microbatch", return_value=batch), patch.object(
                microbatch_execution, "_require_finite_tensor_tree"), patch.object(
                    microbatch_execution, "_gradient_execution_rebinder",
                    return_value=lambda current: object()), patch.object(
                        microbatch, "route_microbatch_compatible",
                        return_value=True), patch.object(
                            microbatch, "microbatch_trace_preflight",
                            side_effect=AssertionError(
                                "route-compatible batch executed full preflight")), patch.object(
                                    microbatch, "_source_producer",
                                    return_value=(producer, None, False)) as source_producer, patch.object(
                                        microbatch, "_finalize_source_hidden",
                                        return_value=mx.zeros(
                                            (4, 1, 1), dtype=mx.float32)) as finalize, patch.object(
                                                microbatch, "prepare_refinement_selections",
                                                return_value=(None,) * 4), patch.object(
                                                        microbatch, "prepare_route_microbatch_kernel",
                                                       return_value=object()), patch.object(
                                                            microbatch, "route_microbatch_loss_and_trajectory",
                                                            side_effect=lambda current, *_args, **_kwargs: (
                                                                current["x"] * 2,
                                                                (mx.zeros((4,), dtype=mx.uint32),),
                                                                (mx.zeros((4, 1), dtype=mx.float32),))), patch.object(
                                                                    microbatch, "microbatch_trace_from_route",
                                                                    return_value=(object(),) * 4) as postflight, patch.object(
                                                                        microbatch, "microbatch_trace_from_hidden",
                                                                        side_effect=AssertionError(
                                                                            "vector route replayed scalar postflight")) as legacy_postflight, patch.object(
                                                                        microbatch_execution, "finalize_microbatch_gradient",
                                                                        return_value="done"), patch.object(
                                                                            mx, "value_and_grad",
                                                                            wraps=mx.value_and_grad) as value_and_grad:
        result = microbatch._bamf_microbatch_value_and_grad_impl(
            Backend(), params, rows, plans, ((),) * 4, ({},) * 4, None)

    assert result == "done"
    assert value_and_grad.call_count == 1
    assert source_producer.call_count == 1
    assert finalize.call_count == 1
    assert postflight.call_count == 1
    assert legacy_postflight.call_count == 0


def test_route_gradient_with_refinement_supervision_stays_vectorized():
    rows = (object(),) * 4
    snapshot = object()
    plans = tuple(SimpleNamespace(
        generation_binding="generation", snapshot=snapshot) for _ in rows)
    batch = SimpleNamespace(compiled=SimpleNamespace(extents=object()))
    params = {"x": mx.array(1.0, dtype=mx.float32)}
    refinement = tuple(
        (object(), (SimpleNamespace(passes=1),)) for _ in rows)

    class Backend:
        topology = object()

        def __post_init__(self):
            return None

    producer = object()
    with patch.object(
            microbatch_execution, "_compiled_microbatch", return_value=batch), patch.object(
                microbatch_execution, "_require_finite_tensor_tree"), patch.object(
                    microbatch_execution, "_gradient_execution_rebinder",
                    return_value=lambda current: object()), patch.object(
                        microbatch, "route_microbatch_compatible",
                        return_value=True), patch.object(
                            microbatch, "microbatch_trace_preflight",
                            side_effect=AssertionError(
                                "refinement-supervised route batch executed full preflight")), patch.object(
                                    microbatch, "_source_producer",
                                    return_value=(producer, None, False)), patch.object(
                                        microbatch, "_finalize_source_hidden",
                                        return_value=mx.zeros((4, 1, 1), dtype=mx.float32)), patch.object(
                                            microbatch, "prepare_refinement_selections",
                                            return_value=refinement), patch.object(
                                                microbatch, "prepare_route_microbatch_kernel",
                                                return_value=object()), patch.object(
                                                    microbatch, "batched_refine_hidden_with_routing",
                                                    side_effect=lambda _p, _r, _producer, hidden, _s: (
                                                        hidden, ((
                                                            mx.zeros((4, 3), dtype=mx.float32),
                                                            mx.ones((4,), dtype=mx.int32),
                                                            mx.ones((4,), dtype=mx.bool_),
                                                        ),))), patch.object(
                                                            microbatch, "batched_refinement_routing_loss",
                                                            return_value=mx.zeros((4,), dtype=mx.float32)), patch.object(
                                                        microbatch, "route_microbatch_loss_and_trajectory",
                                                        side_effect=lambda current, *_args, **_kwargs: (
                                                            current["x"] * 2,
                                                            (mx.zeros((4,), dtype=mx.uint32),),
                                                            (mx.zeros((4, 1), dtype=mx.float32),))), patch.object(
                                                                microbatch, "microbatch_trace_from_route",
                                                                return_value=(object(),) * 4), patch.object(
                                                                    microbatch_execution, "finalize_microbatch_gradient",
                                                                    return_value="done"):
        result = microbatch._bamf_microbatch_value_and_grad_impl(
            Backend(), params, rows, plans, ((),) * 4, ({},) * 4, None)

    assert result == "done"


def test_route_postflight_rebinds_execution_identity_to_original_parameters():
    rows = (object(),) * 4
    snapshot = object()
    plans = tuple(SimpleNamespace(
        generation_binding="generation", snapshot=snapshot) for _ in rows)
    batch = SimpleNamespace(compiled=SimpleNamespace(extents=object()))
    params = {"x": mx.array(1.0, dtype=mx.float32)}
    original_binding = tuple(id(value) for value in params.values())

    class Backend:
        topology = object()

        def __post_init__(self):
            return None

    def rebind(current):
        return tuple(id(current[name]) for name in params)

    def postflight(*args):
        execution_binding = args[-6]
        assert execution_binding == original_binding
        return (object(),) * 4

    with patch.object(
            microbatch_execution, "_compiled_microbatch", return_value=batch), patch.object(
                microbatch_execution, "_require_finite_tensor_tree"), patch.object(
                    microbatch_execution, "_gradient_execution_rebinder",
                    return_value=rebind), patch.object(
                        microbatch, "route_microbatch_compatible",
                        return_value=True), patch.object(
                            microbatch, "_source_producer",
                            return_value=(object(), None, False)), patch.object(
                                microbatch, "_finalize_source_hidden",
                                return_value=mx.zeros((4, 1, 1), dtype=mx.float32)), patch.object(
                                    microbatch, "prepare_refinement_selections",
                                    return_value=(None,) * 4), patch.object(
                                            microbatch, "prepare_route_microbatch_kernel",
                                           return_value=object()), patch.object(
                                                microbatch, "route_microbatch_loss_and_trajectory",
                                                side_effect=lambda current, *_args, **_kwargs: (
                                                    current["x"] * 2,
                                                    (mx.zeros((4,), dtype=mx.uint32),),
                                                    (mx.zeros((4, 1), dtype=mx.float32),))), patch.object(
                                                        microbatch, "microbatch_trace_from_route",
                                                        side_effect=postflight), patch.object(
                                                            microbatch_execution, "finalize_microbatch_gradient",
                                                            return_value="done"):
        result = microbatch._bamf_microbatch_value_and_grad_impl(
            Backend(), params, rows, plans, ((),) * 4, ({},) * 4, None)

    assert result == "done"


def test_learning_first_reuses_prebound_execution_cache_for_gradient_identity():
    cache = object()
    params = {"x": mx.array(1.0, dtype=mx.float32)}
    rows = (object(), object())
    plans = (object(), object())
    batch = SimpleNamespace(compiled=SimpleNamespace(extents=object()))

    class Backend:
        topology = object()

    with patch.object(
            microbatch_execution, "_microbatch_request_context",
            return_value=(batch, None, "generation", object())), patch.object(
                microbatch_execution, "route_microbatch_compatible",
                return_value=True), patch.object(
                    microbatch_execution, "_gradient_execution_rebinder",
                    return_value=lambda current: object()) as rebind, patch.object(
                        microbatch_execution, "prepare_route_microbatch_kernel",
                        return_value=object()), patch.object(
                            microbatch_execution, "_microbatch_objective",
                            return_value=object()), patch.object(
                                microbatch_execution, "_materialize_gradient",
                                return_value=(
                                    mx.array(0.0, dtype=mx.float32),
                                    params,
                                    (object(), object()),
                                    (),
                                    mx.array(True),
                                    {},
                                )), patch.object(
                                    microbatch_execution,
                                    "_require_materialized_finite_witness"), patch.object(
                                        microbatch_execution,
                                        "finalize_microbatch_gradient",
                                        return_value="done"), patch.object(
                                            microbatch_execution,
                                            "attach_performance_observation"):
        result = microbatch_execution._learning_first_microbatch_value_and_grad_impl(
            Backend(), params, rows, plans, ((), ()), ({}, {}), cache, None)

    assert result == "done"
    assert rebind.call_args.args[1] is cache


def test_route_trajectory_drift_fails_closed_after_materialization():
    decision = DecisionSpec(
        "op", None, 0, DecisionKind.OPERATOR, ("op.a", "op.b"))
    plans = (SimpleNamespace(
        decisions=(decision,), execution_order=("op",)),) * 2
    executions = (
        SimpleNamespace(output=SimpleNamespace(
            committed=(DecisionOutput("op", "op.a"),))),
        SimpleNamespace(output=SimpleNamespace(
            committed=(DecisionOutput("op", "op.b"),))),
    )
    trajectory = (mx.array((1, 1), dtype=mx.uint32),)
    with pytest.raises(BilqisError):
        validation._validate_route_trajectory(plans, executions, trajectory)


def test_new_route_kernel_contains_no_host_scalar_extraction():
    import inspect
    source = inspect.getsource(route_microbatch_loss_and_trajectory)
    assert ".item(" not in source
