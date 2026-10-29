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
    initialize_bamf_row, initializer_seed,
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


def _released_factor_terms(parameters, row):
    overflow_types = dict(row.type_overflow)
    types = [_factor_vector(parameters["features.type"], index, overflow_types.get(type_id))
             for type_id, index in zip(row.type_ids, row.type_rows)]
    type_mean = mx.mean(mx.stack(types), axis=0) if types else parameters["features.type"][FEATURE_NONE_ROW]
    role = _factor_vector(parameters["features.role"], row.role_row, row.role_overflow)
    schema = _factor_vector(parameters["features.schema"], row.schema_row, row.schema_overflow)
    gates = mx.sigmoid(parameters["features.gates"])
    return (gates[FactorGate.TYPE] * (type_mean @ parameters["features.project_type"].T),
            gates[FactorGate.ROLE] * (role @ parameters["features.project_role"].T),
            gates[FactorGate.SCHEMA] * (schema @ parameters["features.project_schema"].T),
            gates[FactorGate.GRAPH] * (mx.array(row.graph64, dtype=mx.float32) @
                                      parameters["features.project_graph"].T))


def _compose_one(parameters, request, features):
    row = features.features_for(request.concept, request.role_id, request.schema_id, request.scope)
    terms = _released_factor_terms(parameters, row)
    type_role = terms[FactorGate.TYPE] + terms[FactorGate.ROLE]
    factors = (type_role + terms[FactorGate.SCHEMA] + terms[FactorGate.GRAPH] +
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


ATOM_EMBEDDING_RANK = 3
CONSTITUENT_INDEX_RANK = 3
IDENTITY_FACTOR_POLICY = "bilqis.mlx.identity-factor/type-graph-v1"
IDENTITY_PROPOSAL_SCHEMA = "bilqis.mlx.identity-row-initialization/v1"


@dataclass(frozen=True)
class SourceFactorWitness:
    context_digest: str
    frame_handle: str
    member_handle: str


@dataclass(frozen=True)
class IdentityRowInitialization:
    """Source-computed proposal; publication and optimizer custody stay with A02."""

    semantic_id: str
    abi_index: int
    weights: np.ndarray
    semantic_release: str
    feature_digest: str
    source_witnesses: tuple[SourceFactorWitness, ...]
    run_seed: int
    initialization_seed: int
    factor_policy: str = IDENTITY_FACTOR_POLICY
    schema_version: str = IDENTITY_PROPOSAL_SCHEMA


def plan_identity_initialization(parameters: Mapping[str, mx.array], requests: tuple[tuple[FeatureRequest, ...], ...],
                                 features: AtlasFeatures, *, current_banks: tuple[SemanticBankView, ...],
                                 extents: GenerationExtents, run_seed: int) -> tuple[IdentityRowInitialization, ...]:
    """Compute only new rows, preserving all existing arrays and optimizer state.

    Identity factors use released type and graph projections. Role, schema and
    local occurrence are contextual additions at lookup, not semantic identity.
    A source-qualified concept can therefore be planned before physical row
    activation. No candidate is admitted or installed by this pure operation.
    """
    _validate_composer(parameters, requests, features, extents)
    _validate_banks(current_banks)
    if (len(current_banks) > extents.semantic_bank_count or
            any(bank.weights is not parameters.get(f"identity.bank.{bank.bank_index}") for bank in current_banks)):
        _invalid()
    existing = {bank.bank_index * BANK_ROWS + row for bank in current_banks for row in bank.active_rows}
    selected = {}
    for batch in requests:
        for request in batch:
            index = request.concept.abi_index
            if index in existing or index >= extents.semantic_bank_count * BANK_ROWS:
                _invalid()
            if index in selected and selected[index][0].concept.semantic_id != request.concept.semantic_id:
                _invalid()
            selected.setdefault(index, []).append(request)
    next_indices = sorted(existing | set(selected))
    active_digest = hashlib.sha256(json.dumps(next_indices, separators=(",", ":")).encode()).hexdigest()
    if active_digest != extents.active_semantic_digest:
        _invalid()
    declared = {item.name: item for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
    proposals = []
    for index, occurrences in sorted(selected.items()):
        key = lambda request: (request.projection.digest, request.frame_handle, request.member_handle)
        request = min(occurrences, key=key)
        witnesses = tuple(SourceFactorWitness(*value) for value in sorted({key(item) for item in occurrences}))
        row = features.features_for(request.concept, "NONE", "NONE", request.scope)
        terms = _released_factor_terms(parameters, row)
        factor = np.asarray(terms[FactorGate.TYPE] + terms[FactorGate.GRAPH])
        parameter = declared[f"identity.bank.{index // BANK_ROWS}"]
        weights = initialize_bamf_row(parameter, run_seed=run_seed, row_id=request.concept.semantic_id, factor=factor)
        weights.setflags(write=False)
        proposals.append(IdentityRowInitialization(
            request.concept.semantic_id, index, weights, features.semantic_release, features.digest,
            witnesses, run_seed, initializer_seed(run_seed, parameter.name, request.concept.semantic_id)))
    return tuple(proposals)


def gather_constituents(embeddings: mx.array, indices: mx.array, valid: mx.array) -> mx.array:
    """Gather exact [B,F,M] sidecar addresses, leaving the float path differentiable."""
    if (not isinstance(embeddings, mx.array) or embeddings.ndim != ATOM_EMBEDDING_RANK or
            embeddings.shape[-1] != WIDTH or min(embeddings.shape) < 1 or embeddings.dtype != mx.float32 or
            not isinstance(indices, mx.array) or indices.ndim != CONSTITUENT_INDEX_RANK or
            not mx.issubdtype(indices.dtype, mx.integer) or indices.shape[0] != embeddings.shape[0] or
            min(indices.shape) < 1 or not isinstance(valid, mx.array) or valid.shape != indices.shape or
            valid.dtype != mx.bool_):
        _invalid()
    if bool(mx.any(valid & ((indices < 0) | (indices >= embeddings.shape[1])))):
        _invalid()
    batch, frames, members = indices.shape
    safe = mx.where(valid, indices, 0).astype(mx.int32).reshape(batch, frames*members)
    values = mx.take_along_axis(embeddings, safe[:, :, None], axis=1).reshape(batch, frames, members, WIDTH)
    return mx.where(valid[:, :, :, None], values, 0)


def masked_semantic_loss(indexed: IndexedLogits, targets: mx.array, legal: mx.array) -> mx.array:
    """Stable supervised loss; global target IDs never enter the inference feature path."""
    if (type(indexed) is not IndexedLogits or indexed.schema_version != INDEXED_LOGITS_SCHEMA or
            not isinstance(indexed.logits, mx.array) or indexed.logits.ndim < 1 or
            min(indexed.logits.shape) < 1 or
            indexed.logits.dtype != mx.float32 or type(indexed.indices) is not tuple or not indexed.indices or
            indexed.indices != tuple(sorted(set(indexed.indices))) or
            any(type(index) is not int or not 0 <= index <= UINT32_MAX for index in indexed.indices) or
            indexed.logits.shape[-1] != len(indexed.indices) or
            not isinstance(targets, mx.array) or not mx.issubdtype(targets.dtype, mx.integer) or
            targets.shape != indexed.logits.shape[:-1] or
            not isinstance(legal, mx.array) or legal.dtype != mx.bool_ or legal.shape != indexed.logits.shape):
        _invalid()
    target_ids = targets.astype(mx.int64)
    target_mask = target_ids[..., None] == mx.array(indexed.indices, dtype=mx.int64)
    checks = (mx.all((target_ids >= 0) & (target_ids <= UINT32_MAX)), mx.all(mx.any(legal, axis=-1)),
              mx.all(mx.any(target_mask & legal, axis=-1)), mx.all(~legal | mx.isfinite(indexed.logits)))
    mx.eval(*checks)
    if not all(bool(check) for check in checks):
        _invalid()
    masked = mx.where(legal, indexed.logits, -mx.inf)
    shifted = masked - mx.max(masked, axis=-1, keepdims=True)
    target_score = mx.sum(mx.where(target_mask, shifted, 0), axis=-1)
    return mx.mean(mx.logsumexp(shifted, axis=-1) - target_score)
