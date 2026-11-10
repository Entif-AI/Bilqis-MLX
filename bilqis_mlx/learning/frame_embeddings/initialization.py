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
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from bilqis_mlx.semantics.atlas.vocabulary import (
    CandidateState, VocabularyBankParent, VocabularyExtension,
)
from bilqis_mlx.semantics.atlas.vocabulary_factors import prepare_identity_factors
from bilqis_mlx.semantics.atlas.vocabulary_planning import _plan_from_snapshot
from .common import BANK_ROWS, FactorGate, IDENTITY_FACTOR_POLICY, IDENTITY_PROPOSAL_SCHEMA, _invalid
from .requests import FeatureRequest
from .composition import _released_factor_terms, _validate_composer
from .banks import (
    SemanticBankView, _validate_banks,
    semantic_bank_views_from_vocabulary_candidate,
)


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


def qualify_staged_identity_initialization(
        parent: VocabularyBankParent,
        candidate: CandidateState,
        plan: VocabularyExtension,
        snapshot: FrozenAtlasSnapshot) -> tuple[IdentityRowInitialization, ...]:
    """Prove A02's staged rows satisfy B02.2 without mutating staging custody."""
    if (type(parent) is not VocabularyBankParent
            or type(candidate) is not CandidateState
            or type(plan) is not VocabularyExtension
            or type(snapshot) is not FrozenAtlasSnapshot
            or parent.prior.generation_id != plan.parent_generation_id
            or candidate.parent_generation_id != plan.parent_generation_id
            or plan.parent_extents_digest != parent.prior.extents.digest
            or snapshot.bundle_id != parent.prior.source_selection.bundle_id
            or snapshot.release_sha256 != parent.prior.source_selection.release_sha256
            or snapshot.source_bundle_id != parent.prior.source_selection.source_bundle_id):
        _invalid()
    semantic_ids = tuple(item.semantic_id for item in plan.allocations)
    if plan != _plan_from_snapshot(
            parent.prior, semantic_ids, ModelTopologySpecV2(), snapshot):
        _invalid()
    semantic_bank_views_from_vocabulary_candidate(candidate, plan)
    source_plan, factors = prepare_identity_factors(
        snapshot, parent.prior.features, semantic_ids,
        parent.feature_parameters, extents=parent.prior.extents)
    if (source_plan.digest != plan.prospective_feature_digest
            or tuple(name for name, _ in factors) != semantic_ids):
        _invalid()
    for semantic_id in parent.prior.active_semantic_ids:
        entry = snapshot.abi_for_semantic(semantic_id)
        if not np.array_equal(
                np.asarray(parent.weights[entry.bank][entry.row]),
                np.asarray(candidate.weights[entry.bank][entry.row])):
            _invalid()
    declared = {
        item.name: item for item in expected_bamf_shapes(
            ModelTopologySpecV2(), candidate.extents)
        if item.name.startswith("identity.bank.")
    }
    proposals = []
    for allocation, (semantic_id, factor) in zip(plan.allocations, factors):
        if (semantic_id != allocation.semantic_id
                or allocation.abi_index != allocation.bank * BANK_ROWS + allocation.row):
            _invalid()
        parameter = declared.get(f"identity.bank.{allocation.bank}")
        if parameter is None:
            _invalid()
        weights = initialize_bamf_row(
            parameter, run_seed=parent.run_seed,
            row_id=semantic_id, factor=factor)
        if not np.array_equal(
                weights, np.asarray(candidate.weights[allocation.bank][allocation.row])):
            _invalid()
        weights.setflags(write=False)
        proposals.append(IdentityRowInitialization(
            semantic_id, allocation.abi_index, weights,
            plan.semantic_release, parent.prior.features.digest, (),
            parent.run_seed,
            initializer_seed(parent.run_seed, parameter.name, semantic_id)))
    return tuple(proposals)
