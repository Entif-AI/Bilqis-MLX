"""BAMF embedding initialization owner."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from typing import Mapping
import mlx.core as mx
import numpy as np
from lib.ithkuil.src.skos.publication import json_bytes
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes, initialize_bamf_row, initializer_seed
from bilqis_mlx.semantics.atlas_features import AtlasFeatures
from .common import BANK_ROWS, FactorGate, IDENTITY_FACTOR_POLICY, IDENTITY_PROPOSAL_SCHEMA, _invalid
from .requests import FeatureRequest
from .composition import _released_factor_terms, _validate_composer
from .banks import SemanticBankView, _validate_banks


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
    active_digest = hashlib.sha256(json_bytes(next_indices)).hexdigest()
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
