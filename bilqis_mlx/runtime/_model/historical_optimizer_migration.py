"""Fail-closed historical scalar-step migration into B12 count state."""
from __future__ import annotations

import mlx.core as mx

from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.historical_optimizer_contract import (
    HistoricalAdamWMigrationCapability, historical_update_attestation,
)
from bilqis_mlx.runtime.historical_optimizer_digests import (
    UINT64_MAX, historical_count_geometry_digest, historical_model_state_digest,
    historical_optimizer_state_digest, invalid, parameter_order_tuple,
)
from bilqis_mlx.runtime.optimizer_count_geometry import declared_update_count_shape


def migrate_historical_bamf_optimizer(
        optimizer_state, model_weights, *, parameter_order, spec, extents,
        capability):
    """Map one attested all-together historical scalar into B12 counts."""
    from bilqis_mlx.runtime.model_topology_v2 import (
        GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    )
    from bilqis_mlx.runtime.mlx_parity import native_optimizer_to_mlx

    if (type(spec) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or type(capability) is not HistoricalAdamWMigrationCapability):
        invalid()
    capability.__post_init__()
    attestation = historical_update_attestation(capability.attestation_id)
    for field in (
            "architecture_id", "checkpoint_sha256", "model_state_sha256",
            "optimizer_state_sha256", "count_geometry_sha256",
            "global_optimizer_step", "update_contract"):
        if getattr(capability, field) != attestation[field]:
            invalid()
    declared = expected_bamf_shapes(spec, extents)
    names = tuple(item.name for item in declared)
    ordered = parameter_order_tuple(parameter_order, model_weights)
    if (ordered != names
            or any(tuple(model_weights[item.name].shape) != item.shape for item in declared)):
        invalid()
    observed_model = historical_model_state_digest(
        model_weights, parameter_order=ordered)
    observed_optimizer = historical_optimizer_state_digest(
        optimizer_state, model_weights, parameter_order=ordered)
    observed_geometry = historical_count_geometry_digest(declared)
    if (observed_model != capability.model_state_sha256
            or observed_optimizer != capability.optimizer_state_sha256
            or observed_geometry != capability.count_geometry_sha256):
        invalid()
    try:
        receipt, mapped = native_optimizer_to_mlx(
            optimizer_state, model_weights, parameter_order=ordered)
    except (KeyError, TypeError, ValueError):
        invalid()
    step = receipt.get("native_step")
    if (type(step) is not int or step != capability.global_optimizer_step
            or not 0 <= step <= UINT64_MAX):
        invalid()
    try:
        parameters = {
            item.name: mx.array(
                model_weights[item.name].detach().cpu().numpy(), dtype=mx.float32)
            for item in declared
        }
        first = {item.name: mapped.state[item.name]["m"] for item in declared}
        second = {item.name: mapped.state[item.name]["v"] for item in declared}
        counts = {
            item.name: mx.full(declared_update_count_shape(item), step, dtype=mx.uint64)
            for item in declared
        }
    except (AttributeError, KeyError, TypeError, ValueError):
        invalid()
    state = AdamWStateTree(parameters, first, second, counts)
    mx.eval(state.parameters, state.m, state.v, state.update_counts)
    return state, {
        **receipt,
        "historical_attestation_id": capability.attestation_id,
        "historical_checkpoint_sha256": capability.checkpoint_sha256,
        "historical_update_contract": capability.update_contract,
        "historical_all_parameters_updated_together": True,
        "b12_count_entries": len(counts),
    }
