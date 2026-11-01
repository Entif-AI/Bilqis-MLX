"""BAMF embedding composition owner."""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Mapping
import mlx.core as mx
import numpy as np
from bilqis_mlx.runtime.model_topology_v2 import FEATURE_NONE_ROW, GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.semantics.atlas_features import AtlasFeatures, _factor_overflow
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.frame_adapters.common import (
    BOOLEAN_COMPOSITE_ADAPTER, BOOLEAN_CONNECTIVE_ADAPTER,
    BOOLEAN_IDENTIFICATION_ADAPTER, FINITE_NUMERIC_ADAPTER,
    MICRO_PREDICATE_ADAPTER,
)
from bilqis_mlx.semantics.frame_schema import FrameInstance
from bilqis_mlx.semantics.released_frame_schemas import (
    lookup_source_pinned_frame_schema,
)
from .common import COMPOSITION_SCHEMA, FactorGate, POSITION_BASE, WIDTH, _SINUSOID_PAIR_WIDTH, _invalid
from .requests import FeatureRequest


@dataclass(frozen=True)
class FactorComposition:
    """Differentiable values with recomputable release and request provenance."""

    type_role: mx.array
    all_factors: mx.array
    feature_digest: str
    semantic_release: str
    requests: tuple[tuple[FeatureRequest, ...], ...]
    schema_version: str = COMPOSITION_SCHEMA

def _factor_vector(table, row, overflow):
    value = table[row]
    return value if overflow is None else value + mx.array(overflow, dtype=mx.float32)

def _local_position(table, slot):
    if slot < table.shape[0]:
        return table[slot]
    frequencies = np.power(POSITION_BASE, -np.arange(0, WIDTH, _SINUSOID_PAIR_WIDTH) / WIDTH)
    angles = float(slot) * frequencies
    values = np.empty((WIDTH,), dtype=np.float32)
    values[0::_SINUSOID_PAIR_WIDTH] = np.sin(angles)
    values[1::_SINUSOID_PAIR_WIDTH] = np.cos(angles)
    return mx.array(values)

def _validate_feature_parameters(parameters, features, extents):
    if (not isinstance(parameters, Mapping) or type(features) is not AtlasFeatures or
            type(extents) is not GenerationExtents or extents.factor_map_digest != features.digest):
        _invalid()
    for item in expected_bamf_shapes(ModelTopologySpecV2(), extents):
        if item.name.startswith("features."):
            value = parameters.get(item.name)
            if not isinstance(value, mx.array) or value.shape != item.shape or value.dtype != mx.float32:
                _invalid()

def _validate_composer(parameters, requests, features, extents):
    _validate_feature_parameters(parameters, features, extents)
    if (type(requests) is not tuple or not requests or type(requests[0]) is not tuple or
            not requests[0] or any(type(row) is not tuple or len(row) != len(requests[0]) or
                                  any(type(item) is not FeatureRequest for item in row) for row in requests)):
        _invalid()

def _released_categorical_factors(parameters, row):
    overflow_types = dict(row.type_overflow)
    types = [_factor_vector(parameters["features.type"], index, overflow_types.get(type_id))
             for type_id, index in zip(row.type_ids, row.type_rows)]
    type_mean = mx.mean(mx.stack(types), axis=0) if types else parameters["features.type"][FEATURE_NONE_ROW]
    role = _factor_vector(parameters["features.role"], row.role_row, row.role_overflow)
    schema = _factor_vector(parameters["features.schema"], row.schema_row, row.schema_overflow)
    return type_mean, role, schema


_SOURCE_FAMILIES = (
    (MICRO_PREDICATE_ADAPTER, "micro"),
    (BOOLEAN_CONNECTIVE_ADAPTER, "boolean"),
    (BOOLEAN_COMPOSITE_ADAPTER, "boolean"),
    (BOOLEAN_IDENTIFICATION_ADAPTER, "boolean"),
    (FINITE_NUMERIC_ADAPTER, "numeric"),
)


def _pinned_source_types(
    features: AtlasFeatures,
    request: FeatureRequest,
    atlas_selection: AtlasArtifactSelection | None,
) -> tuple[str, ...]:
    """Independently rederive a formal terminal's types from A01/A03 authority."""
    if type(atlas_selection) is not AtlasArtifactSelection:
        _invalid()
    atlas_selection.__post_init__()
    if (atlas_selection.bundle_id != features.atlas_bundle_id
            or atlas_selection.release_sha256 != features.semantic_release
            or atlas_selection.source_bundle_id != features.source_bundle_id):
        _invalid()
    reference = request.concept.source_reference
    if not isinstance(reference, str) or ":" not in reference:
        _invalid()
    adapter_id, _symbol = reference.split(":", 1)
    source_family = next((family for owner, family in _SOURCE_FAMILIES
                          if owner == adapter_id), None)
    if source_family is None:
        _invalid()
    frame = request.projection.frame(request.frame_handle)
    if type(frame) is not FrameInstance:
        _invalid()
    schema, _witness = lookup_source_pinned_frame_schema(
        frame.frame_schema_id, frame.frame_schema_revision,
        source_family=source_family, atlas_selection=atlas_selection,
    )
    role = next((item for item in schema.roles
                 if item.role_id == request.role_id), None)
    if role is None or request.concept.type_ids != role.allowed_type_ids:
        _invalid()
    return role.allowed_type_ids


def _source_qualified_feature_row(
    features: AtlasFeatures,
    request: FeatureRequest,
    atlas_selection: AtlasArtifactSelection | None = None,
):
    """Compose A06 authority with A13-owned formal source-signature types.

    A06 remains authoritative for admitted semantic identity, ABI index, role,
    schema and graph factors.  Formal ABI identities that A06 deliberately marks
    ``ADMITTED_FORMAL_ABI_UNTYPED`` have no A06-owned categorical type row.  For
    those identities only, consume the exact A13-approved ``ConceptRef.type_ids``
    already bound into ``FeatureRequest`` and encode missing categorical IDs via
    the same deterministic UNKNOWN+overflow rule used by typed child frames.

    The derived row is composition-local: it does not mutate the A06 manifest or
    promote source-signature metadata into A06 provenance authority.
    """
    if type(request) is not FeatureRequest:
        _invalid()
    request.__post_init__()
    concept = request.concept
    admitted = next(
        (item for item in features.concepts
         if item.semantic_id == concept.semantic_id),
        None,
    )
    if admitted is None or admitted.source_status != "ADMITTED_FORMAL_ABI_UNTYPED":
        return features.features_for(
            concept, request.role_id, request.schema_id, request.scope)

    row = features.features_for(
        concept.semantic_id, request.role_id, request.schema_id, request.scope)
    if (concept.semantic_release != features.semantic_release
            or concept.abi_index != row.abi_index):
        _invalid()
    source_types = _pinned_source_types(features, request, atlas_selection)
    types = dict(features.type_map)
    type_rows = tuple(types.get(identifier, 0) for identifier in source_types)
    return replace(
        row,
        type_ids=source_types,
        type_rows=type_rows,
        type_overflow=tuple(
            (identifier, _factor_overflow("type", identifier))
            for identifier, factor_row in zip(source_types, type_rows)
            if factor_row == 0
        ),
    )

def _released_factor_terms(parameters, row):
    type_mean, role, schema = _released_categorical_factors(parameters, row)
    gates = mx.sigmoid(parameters["features.gates"])
    return (gates[FactorGate.TYPE] * (type_mean @ parameters["features.project_type"].T),
            gates[FactorGate.ROLE] * (role @ parameters["features.project_role"].T),
            gates[FactorGate.SCHEMA] * (schema @ parameters["features.project_schema"].T),
            gates[FactorGate.GRAPH] * (mx.array(row.graph64, dtype=mx.float32) @
                                      parameters["features.project_graph"].T))

def _compose_one(parameters, request, features, atlas_selection=None):
    row = _source_qualified_feature_row(features, request, atlas_selection)
    terms = _released_factor_terms(parameters, row)
    type_role = terms[FactorGate.TYPE] + terms[FactorGate.ROLE]
    factors = (type_role + terms[FactorGate.SCHEMA] + terms[FactorGate.GRAPH] +
               _local_position(parameters["features.local_slot"], request.local_slot))
    return type_role, factors

def compose_factor_features(parameters: Mapping[str, mx.array], requests: tuple[tuple[FeatureRequest, ...], ...],
                            features: AtlasFeatures, *, extents: GenerationExtents,
                            atlas_selection: AtlasArtifactSelection | None = None) -> FactorComposition:
    """Use actual A06 rows and shared B01 tables; never accept anonymous feature tensors.

    Each projected type/role/schema/graph term has its learned sigmoid gate.
    Categorical overflow is UNKNOWN plus the released exact-ID vector. Multiple
    types use their arithmetic mean. Extended local slots use a fixed base-10000
    alternating sine/cosine encoding, retaining role and occurrence separately.
    Identity-bank activation and model-generation admission remain upstream.
    """
    _validate_composer(parameters, requests, features, extents)
    composed = [[_compose_one(parameters, request, features, atlas_selection)
                 for request in batch] for batch in requests]
    type_role = mx.stack([mx.stack([item[0] for item in batch]) for batch in composed])
    all_factors = mx.stack([mx.stack([item[1] for item in batch]) for batch in composed])
    return FactorComposition(type_role, all_factors, features.digest, features.semantic_release,
                             requests)
