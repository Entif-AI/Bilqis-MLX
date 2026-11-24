"""#1566 learning-first microbatch execution witnesses."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.runtime.atlas_model_microbatch as microbatch
import bilqis_mlx.runtime.microbatch.execution as microbatch_execution
import bilqis_mlx.runtime.microbatch.route_evidence as route_evidence

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
                                                            route_evidence,
                                                            "microbatch_participation_from_route",
                                                            return_value=(object(),) * 4) as postflight, patch.object(
                                                                        microbatch, "microbatch_trace_from_hidden",
                                                                        side_effect=AssertionError(
                                                                            "vector route replayed scalar postflight")) as legacy_postflight, patch.object(
                                                                        microbatch_execution, "finalize_microbatch_gradient",
                                                                        return_value="done"), patch.object(
                                                                            mx, "value_and_grad",
                                                                            wraps=mx.value_and_grad) as value_and_grad, patch.object(
                                                                                mx, "eval", wraps=mx.eval) as evaluate:
        result = microbatch._bamf_microbatch_value_and_grad_impl(
            Backend(), params, rows, plans, ((),) * 4, ({},) * 4, None)

    assert result == "done"
    assert value_and_grad.call_count == 1
    assert source_producer.call_count == 1
    assert finalize.call_count == 1
    assert postflight.call_count == 1
    assert isinstance(postflight.call_args.args[-3], mx.array)
    assert evaluate.call_count == 1
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
                                                                route_evidence,
                                                                "microbatch_participation_from_route",
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
        execution_binding = args[-3]
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
                                                        route_evidence,
                                                        "microbatch_participation_from_route",
                                                        side_effect=postflight), patch.object(
                                                            microbatch_execution, "finalize_microbatch_gradient",
                                                            return_value="done"):
        result = microbatch._bamf_microbatch_value_and_grad_impl(
            Backend(), params, rows, plans, ((),) * 4, ({},) * 4, None)

    assert result == "done"


def test_learning_first_ignores_accepted_cache_for_gradient_identity():
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
                    microbatch_execution, "learning_first_compiled_route",
                    return_value=(None, "disabled")), patch.object(
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
                                    {
                                        "b11_materialization_barrier_count": 1,
                                        "b11_host_readback_count": 1,
                                    },
                                )), patch.object(
                                    microbatch_execution,
                                    "_require_materialized_finite_witness"), patch.object(
                                        microbatch_execution,
                                        "finalize_microbatch_gradient",
                                        return_value="done"), patch.object(
                                            microbatch_execution,
                                            "attach_performance_observation") as observe:
        result = microbatch_execution._learning_first_microbatch_value_and_grad_impl(
            Backend(), params, rows, plans, ((), ()), ({}, {}), cache, None)

    assert result == "done"
    assert rebind.call_args.args[1] is None
    observe.assert_not_called()

