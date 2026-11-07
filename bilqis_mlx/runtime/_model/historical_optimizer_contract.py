"""Code-owned authority for historical scalar-step B12 migration."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from bilqis_mlx.runtime.historical_optimizer_digests import (
    UINT64_MAX, checkpoint_digest, historical_count_geometry_digest,
    historical_model_state_digest, historical_optimizer_state_digest,
    invalid, is_sha256, parameter_order_tuple,
)


HISTORICAL_MIGRATION_SCHEMA = "bilqis.mlx.historical-adamw-migration-capability/v1"
HISTORICAL_ATTESTATION_SCHEMA = "bilqis.mlx.historical-adamw-update-attestation/v1"
HISTORICAL_FULL_TREE_CONTRACT = (
    "bilqis.mlx.historical-full-tree-shared-scalar-static-count-geometry/v1"
)
_HISTORICAL_MIGRATION_ISSUER = object()
_HISTORICAL_ATTESTATION_FIELDS = frozenset({
    "schema", "architecture_id", "checkpoint_sha256", "model_state_sha256",
    "optimizer_state_sha256", "count_geometry_sha256", "global_optimizer_step",
    "update_contract",
})

# Empty until a BAMF-v2 historical generation has an audited whole-lineage proof.
# The pinned six-layer v1 parent is readable evidence, never v2 migration authority.
_HISTORICAL_UPDATE_ATTESTATIONS = MappingProxyType({})


@dataclass(frozen=True, init=False)
class HistoricalAdamWMigrationCapability:
    """Ephemeral exact-state authority for one shared-scalar migration."""

    attestation_id: str
    architecture_id: str
    checkpoint_sha256: str
    model_state_sha256: str
    optimizer_state_sha256: str
    count_geometry_sha256: str
    global_optimizer_step: int
    update_contract: str
    schema_version: str
    _issuance: object

    def __init__(self, *args, **kwargs):
        invalid()

    def __post_init__(self):
        from bilqis_mlx.runtime.model_topology_v2 import BAMF_ARCHITECTURE_ID

        if (getattr(self, "_issuance", None) is not _HISTORICAL_MIGRATION_ISSUER
                or not isinstance(self.attestation_id, str) or not self.attestation_id
                or self.architecture_id != BAMF_ARCHITECTURE_ID
                or any(not is_sha256(value) for value in (
                    self.checkpoint_sha256, self.model_state_sha256,
                    self.optimizer_state_sha256, self.count_geometry_sha256))
                or type(self.global_optimizer_step) is not int
                or not 0 <= self.global_optimizer_step <= UINT64_MAX
                or self.update_contract != HISTORICAL_FULL_TREE_CONTRACT
                or self.schema_version != HISTORICAL_MIGRATION_SCHEMA):
            invalid()


def historical_update_attestation(attestation_id):
    from bilqis_mlx.runtime.model_topology_v2 import BAMF_ARCHITECTURE_ID

    if type(attestation_id) is not str or not attestation_id:
        invalid()
    attestation = _HISTORICAL_UPDATE_ATTESTATIONS.get(attestation_id)
    if (not isinstance(attestation, Mapping)
            or set(attestation) != _HISTORICAL_ATTESTATION_FIELDS
            or attestation.get("schema") != HISTORICAL_ATTESTATION_SCHEMA
            or attestation.get("architecture_id") != BAMF_ARCHITECTURE_ID
            or attestation.get("update_contract") != HISTORICAL_FULL_TREE_CONTRACT
            or not all(is_sha256(attestation.get(name)) for name in (
                "checkpoint_sha256", "model_state_sha256",
                "optimizer_state_sha256", "count_geometry_sha256"))
            or type(attestation.get("global_optimizer_step")) is not int
            or not 0 <= attestation["global_optimizer_step"] <= UINT64_MAX):
        invalid()
    return attestation


def mint_historical_bamf_migration_capability(
        checkpoint_path, optimizer_state, model_weights, *, parameter_order,
        spec, extents, attestation_id):
    """Issue migration authority only from an exact code-owned attestation."""
    from bilqis_mlx.runtime.model_topology_v2 import (
        BAMF_ARCHITECTURE_ID, GenerationExtents, ModelTopologySpecV2,
        expected_bamf_shapes,
    )
    from bilqis_mlx.runtime.mlx_parity import native_optimizer_to_mlx

    if type(spec) is not ModelTopologySpecV2 or type(extents) is not GenerationExtents:
        invalid()
    attestation = historical_update_attestation(attestation_id)
    declared = expected_bamf_shapes(spec, extents)
    names = parameter_order_tuple(parameter_order, model_weights)
    if (names != tuple(item.name for item in declared)
            or any(tuple(model_weights[item.name].shape) != item.shape for item in declared)):
        invalid()
    observed = {
        "checkpoint_sha256": checkpoint_digest(checkpoint_path),
        "model_state_sha256": historical_model_state_digest(
            model_weights, parameter_order=names),
        "optimizer_state_sha256": historical_optimizer_state_digest(
            optimizer_state, model_weights, parameter_order=names),
        "count_geometry_sha256": historical_count_geometry_digest(declared),
    }
    try:
        receipt, _ = native_optimizer_to_mlx(
            optimizer_state, model_weights, parameter_order=names)
    except (KeyError, TypeError, ValueError):
        invalid()
    if (any(observed[name] != attestation[name] for name in observed)
            or receipt.get("native_step") != attestation["global_optimizer_step"]):
        invalid()
    capability = object.__new__(HistoricalAdamWMigrationCapability)
    values = {
        "attestation_id": attestation_id,
        "architecture_id": BAMF_ARCHITECTURE_ID,
        **observed,
        "global_optimizer_step": attestation["global_optimizer_step"],
        "update_contract": HISTORICAL_FULL_TREE_CONTRACT,
        "schema_version": HISTORICAL_MIGRATION_SCHEMA,
        "_issuance": _HISTORICAL_MIGRATION_ISSUER,
    }
    for name, value in values.items():
        object.__setattr__(capability, name, value)
    capability.__post_init__()
    return capability
