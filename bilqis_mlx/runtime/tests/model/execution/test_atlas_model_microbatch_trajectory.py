"""#1265 one-backbone model-owned trajectory witnesses."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import mlx.core as mx
import numpy as np
import pytest

import bilqis_mlx.runtime.atlas_model_forward_validation as validation
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
