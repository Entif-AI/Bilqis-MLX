"""Source-bound shared feature composition for BAMF embeddings and depth selection."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import hashlib
import json
import math
from typing import Mapping

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.model_topology_v2 import (
    FEATURE_NONE_ROW, GenerationExtents, ModelTopologySpecV2, SHA256_HEX_LENGTH, expected_bamf_shapes,
)
from bilqis_mlx.semantics.atlas_features import AtlasFeatures
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection
from bilqis_mlx.semantics.frame_schema import ConceptRef, FrameInstance


WIDTH = ModelTopologySpecV2.width
COMPOSITION_SCHEMA = "bilqis.mlx.factor-composition/v1"
FEATURE_REQUEST_SCHEMA = "bilqis.mlx.factor-request/v1"
ACTIVE_BANK_SCHEMA = "bilqis.mlx.semantic-bank-view/v1"
EMBEDDING_INPUT_SCHEMA = "bilqis.mlx.concept-batch/v1"
INDEXED_LOGITS_SCHEMA = "bilqis.mlx.indexed-logits/v1"
POSITION_BASE = 10000.0
_SINUSOID_PAIR_WIDTH = 2


class FactorGate(IntEnum):
    TYPE = 0
    ROLE = 1
    SCHEMA = 2
    GRAPH = 3


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _source_coordinates(projection, frame_handle, member_handle):
    if type(projection) is not ApprovedContextProjection:
        _invalid()
    envelope = next((item for item in projection.envelopes if item.frame_handle == frame_handle), None)
    if envelope is None or type(envelope.frame) is not FrameInstance:
        _invalid()
    member = next((item for item in envelope.members if item.source_handle == member_handle), None)
    if member is None:
        _invalid()
    for slot, binding in enumerate(envelope.frame.bindings):
        if binding.key == member.key and binding.concept is not None:
            return (binding.concept, binding.role_id, envelope.frame.frame_schema_id, envelope.scope, slot)
    _invalid()


@dataclass(frozen=True)
class FeatureRequest:
    """Target-free source coordinates for one visible atomic occurrence."""

    concept: ConceptRef
    role_id: str
    schema_id: str
    scope: str
    local_slot: int
    projection: ApprovedContextProjection
    frame_handle: str
    member_handle: str
    schema_version: str = FEATURE_REQUEST_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != FEATURE_REQUEST_SCHEMA or
                type(self.concept) is not ConceptRef or type(self.local_slot) is not int or
                self.local_slot < 0 or any(not isinstance(value, str) or not value
                                          for value in (self.role_id, self.schema_id, self.scope))):
            _invalid()
        try:
            if not math.isfinite(float(self.local_slot)):
                _invalid()
        except OverflowError:
            _invalid()
        if (self.concept, self.role_id, self.schema_id, self.scope, self.local_slot) != _source_coordinates(
                self.projection, self.frame_handle, self.member_handle):
            _invalid()

    @classmethod
    def from_context(cls, projection: ApprovedContextProjection, frame_handle: str,
                     member_handle: str) -> "FeatureRequest":
        coordinates = _source_coordinates(projection, frame_handle, member_handle)
        return cls(*coordinates, projection, frame_handle, member_handle)


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


def _validate_composer(parameters, requests, features, extents):
    if (not isinstance(parameters, Mapping) or type(features) is not AtlasFeatures or
            type(extents) is not GenerationExtents or extents.factor_map_digest != features.digest or
            type(requests) is not tuple or not requests or type(requests[0]) is not tuple or
            not requests[0] or any(type(row) is not tuple or len(row) != len(requests[0]) or
                                  any(type(item) is not FeatureRequest for item in row) for row in requests)):
        _invalid()
    for item in expected_bamf_shapes(ModelTopologySpecV2(), extents):
        if item.name.startswith("features."):
            value = parameters.get(item.name)
            if not isinstance(value, mx.array) or value.shape != item.shape or value.dtype != mx.float32:
                _invalid()


def _compose_one(parameters, request, features):
    row = features.features_for(request.concept, request.role_id, request.schema_id, request.scope)
    overflow_types = dict(row.type_overflow)
    types = [_factor_vector(parameters["features.type"], index, overflow_types.get(type_id))
             for type_id, index in zip(row.type_ids, row.type_rows)]
    type_mean = mx.mean(mx.stack(types), axis=0) if types else parameters["features.type"][FEATURE_NONE_ROW]
    role = _factor_vector(parameters["features.role"], row.role_row, row.role_overflow)
    schema = _factor_vector(parameters["features.schema"], row.schema_row, row.schema_overflow)
    gates = mx.sigmoid(parameters["features.gates"])
    type_role = (gates[FactorGate.TYPE] * (type_mean @ parameters["features.project_type"].T) +
                 gates[FactorGate.ROLE] * (role @ parameters["features.project_role"].T))
    factors = (type_role + gates[FactorGate.SCHEMA] * (schema @ parameters["features.project_schema"].T) +
               gates[FactorGate.GRAPH] * (mx.array(row.graph64, dtype=mx.float32) @
                                         parameters["features.project_graph"].T) +
               _local_position(parameters["features.local_slot"], request.local_slot))
    return type_role, factors


def compose_factor_features(parameters: Mapping[str, mx.array], requests: tuple[tuple[FeatureRequest, ...], ...],
                            features: AtlasFeatures, *, extents: GenerationExtents) -> FactorComposition:
    """Use actual A06 rows and shared B01 tables; never accept anonymous feature tensors.

    Each projected type/role/schema/graph term has its learned sigmoid gate.
    Categorical overflow is UNKNOWN plus the released exact-ID vector. Multiple
    types use their arithmetic mean. Extended local slots use a fixed base-10000
    alternating sine/cosine encoding, retaining role and occurrence separately.
    Identity-bank activation and model-generation admission remain upstream.
    """
    _validate_composer(parameters, requests, features, extents)
    composed = [[_compose_one(parameters, request, features) for request in batch] for batch in requests]
    type_role = mx.stack([mx.stack([item[0] for item in batch]) for batch in composed])
    all_factors = mx.stack([mx.stack([item[1] for item in batch]) for batch in composed])
    return FactorComposition(type_role, all_factors, features.digest, features.semantic_release,
                             requests)


BANK_ROWS = ModelTopologySpecV2.semantic_bank_rows
UINT32_MAX = int(np.iinfo(np.uint32).max)


@dataclass(frozen=True)
class SemanticBankView:
    """Read-only adapter input from allocation custody, not an admission grant."""

    bank_index: int
    weights: mx.array
    active_rows: tuple[int, ...]
    semantic_release: str
    active_semantic_digest: str
    schema_version: str = ACTIVE_BANK_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != ACTIVE_BANK_SCHEMA or
                type(self.bank_index) is not int or self.bank_index < 0 or
                (self.bank_index + 1) * BANK_ROWS - 1 > UINT32_MAX or
                not isinstance(self.weights, mx.array) or self.weights.shape != (BANK_ROWS, WIDTH) or
                self.weights.dtype != mx.float32 or type(self.active_rows) is not tuple or
                any(type(row) is not int or not 0 <= row < BANK_ROWS for row in self.active_rows) or
                self.active_rows != tuple(sorted(set(self.active_rows))) or
                any(not isinstance(value, str) or len(value) != SHA256_HEX_LENGTH or
                    any(character not in "0123456789abcdef" for character in value)
                    for value in (self.semantic_release, self.active_semantic_digest))):
            _invalid()


@dataclass(frozen=True)
class ConceptBatch:
    requests: tuple[tuple[FeatureRequest, ...], ...]
    banks: tuple[SemanticBankView, ...]
    extents: GenerationExtents
    schema_version: str = EMBEDDING_INPUT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != EMBEDDING_INPUT_SCHEMA or type(self.extents) is not GenerationExtents:
            _invalid()


@dataclass(frozen=True)
class IndexedLogits:
    logits: mx.array
    indices: tuple[int, ...]
    schema_version: str = INDEXED_LOGITS_SCHEMA


def _validate_banks(banks):
    if (type(banks) is not tuple or not banks or any(type(bank) is not SemanticBankView for bank in banks) or
            tuple(bank.bank_index for bank in banks) != tuple(range(len(banks))) or
            any((bank.semantic_release, bank.active_semantic_digest) !=
                (banks[0].semantic_release, banks[0].active_semantic_digest) for bank in banks)):
        _invalid()
    # A01's active-set receipt hashes the canonical ordered global ABI index list.
    indices = [bank.bank_index * BANK_ROWS + row for bank in banks for row in bank.active_rows]
    digest = hashlib.sha256(json.dumps(indices, separators=(",", ":")).encode("utf-8")).hexdigest()
    if banks[0].active_semantic_digest != digest:
        _invalid()


def embed_atoms(parameters: Mapping[str, mx.array], batch: ConceptBatch, features: AtlasFeatures) -> mx.array:
    """Gather active identities and add the actual released factor composition."""
    if (type(batch) is not ConceptBatch or type(batch.extents) is not GenerationExtents or
            type(features) is not AtlasFeatures or not isinstance(parameters, Mapping)):
        _invalid()
    _validate_banks(batch.banks)
    if (len(batch.banks) != batch.extents.semantic_bank_count or
            batch.banks[0].semantic_release != features.semantic_release or
            batch.banks[0].active_semantic_digest != batch.extents.active_semantic_digest or
            any(bank.weights is not parameters.get(f"identity.bank.{bank.bank_index}") for bank in batch.banks)):
        _invalid()
    factors = compose_factor_features(parameters, batch.requests, features, extents=batch.extents)
    identities = []
    active = tuple(frozenset(bank.active_rows) for bank in batch.banks)
    for row in batch.requests:
        values = []
        for request in row:
            bank_index, bank_row = divmod(request.concept.abi_index, BANK_ROWS)
            if bank_index >= len(batch.banks) or bank_row not in active[bank_index]:
                _invalid()
            values.append(batch.banks[bank_index].weights[bank_row])
        identities.append(mx.stack(values))
    combined = mx.stack(identities) + factors.all_factors
    return combined * mx.rsqrt(mx.mean(combined*combined, axis=-1, keepdims=True) +
                                ModelTopologySpecV2.rms_norm_epsilon) * parameters["features.norm"]


def semantic_logits(hidden: mx.array, active_banks: tuple[SemanticBankView, ...]) -> IndexedLogits:
    """Project only legal active rows, preserving their full global ABI addresses."""
    _validate_banks(active_banks)
    if (not isinstance(hidden, mx.array) or hidden.ndim < 1 or hidden.shape[-1] != WIDTH or
            hidden.dtype != mx.float32):
        _invalid()
    logits, indices = [], []
    for bank in active_banks:
        if bank.active_rows:
            rows = mx.array(bank.active_rows, dtype=mx.int32)
            logits.append(hidden @ bank.weights[rows].T)
            indices.extend(bank.bank_index * BANK_ROWS + row for row in bank.active_rows)
    if not indices:
        _invalid()
    return IndexedLogits(mx.concatenate(logits, axis=-1), tuple(indices))
