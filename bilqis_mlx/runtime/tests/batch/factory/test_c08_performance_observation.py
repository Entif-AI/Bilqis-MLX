"""#1266 non-neural B11 observation aggregation at the C08 boundary."""
from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.runtime.c08_gradient_accumulation as accumulation
from bilqis_mlx.runtime.c08_gradient_accumulation import (
    _add_b11_observation, _vectorized_group,
)


def _empty_observation():
    return {
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
        "b11_materialization_barrier_count": 0,
        "b11_host_readback_count": 0,
        "b11_validation_sync_count": 0,
        "b11_provider_draw_count": 0,
        "b11_atlas_reload_count": 0,
    }


def _sample_execution():
    return SimpleNamespace(_performance_observation={
        "b11_preflight_wall_seconds": 0.2,
        "b11_finite_validation_wall_seconds": 0.01,
        "b11_execution_rebinding_wall_seconds": 0.02,
        "b11_refinement_selection_wall_seconds": 0.03,
        "b11_route_compatibility_wall_seconds": 0.04,
        "b11_route_kernel_prepare_wall_seconds": 0.05,
        "b11_fallback_trace_preflight_wall_seconds": 0.0,
        "b11_preflight_other_wall_seconds": 0.05,
        "b11_autodiff_wall_seconds": 0.4,
        "b11_autodiff_dispatch_wall_seconds": 0.03,
        "b11_autodiff_dispatch_rebind_wall_seconds": 0.001,
        "b11_autodiff_dispatch_source_producer_wall_seconds": 0.002,
        "b11_autodiff_dispatch_source_hidden_graph_wall_seconds": 0.003,
        "b11_autodiff_dispatch_refinement_graph_wall_seconds": 0.004,
        "b11_autodiff_dispatch_route_graph_wall_seconds": 0.005,
        "b11_autodiff_dispatch_transform_other_wall_seconds": 0.015,
        "b11_autodiff_materialization_wall_seconds": 0.31,
        "b11_route_evidence_wall_seconds": 0.04,
        "b11_autodiff_other_wall_seconds": 0.02,
        "b11_gradient_finite_validation_wall_seconds": 0.06,
        "b11_postflight_validation_wall_seconds": 0.07,
        "b11_postflight_trajectory_validation_wall_seconds": 0.01,
        "b11_postflight_output_attestation_wall_seconds": 0.02,
        "b11_postflight_loss_validation_wall_seconds": 0.01,
        "b11_postflight_gradient_structure_wall_seconds": 0.01,
        "b11_postflight_result_construction_wall_seconds": 0.02,
        "b11_materialization_barrier_count": 1,
        "b11_host_readback_count": 2,
        "b11_validation_sync_count": 0,
        "b11_provider_draw_count": 8,
        "b11_atlas_reload_count": 2,
    })


def _doubled_observation():
    return {
        name: value * 2
        for name, value in _sample_execution()._performance_observation.items()
    }


def test_b11_observation_aggregation_is_pure_host_accounting():
    total = _empty_observation()
    execution = _sample_execution()

    _add_b11_observation(total, execution)
    _add_b11_observation(total, execution)

    assert total == _doubled_observation()


def test_full_batch_vector_group_reuses_materialized_mean_without_scaling_tree():
    gradients = {"weight": mx.array((1.0, 2.0), dtype=mx.float32)}
    mean_loss = mx.array(0.25, dtype=mx.float32)
    executions = tuple(
        SimpleNamespace(output=SimpleNamespace(generation_binding="generation"))
        for _ in range(4))
    microbatch = SimpleNamespace(
        gradients=gradients, mean_loss=mean_loss, executions=executions,
        _performance_observation={})
    microbatch.__post_init__ = lambda: None
    plan = SimpleNamespace(generation_binding="generation")
    losses = []
    observed = {
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
        "b11_materialization_barrier_count": 0,
        "b11_host_readback_count": 0,
        "b11_validation_sync_count": 0,
        "b11_provider_draw_count": 0,
        "b11_atlas_reload_count": 0,
    }

    with patch.object(accumulation, "BamfMicrobatchGradientExecution", SimpleNamespace):
        aggregate, weighted = _vectorized_group(
            (0, 1, 2, 3), microbatch, plan, 4, None,
            mx.array(0.0, dtype=mx.float32), losses, observed)

    assert aggregate is gradients
    assert weighted is mean_loss
    assert losses == list(executions)
