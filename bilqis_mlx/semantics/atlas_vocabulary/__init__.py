"""A02 source-bound staging for prospective semantic identity factors.

This module deliberately depends only on the A06 feature authority and the B01
model-topology projection primitive. B02 consumes activated semantic banks later;
it is not an authority provider for A02 admission or row initialization.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ...errors import ErrorBus, SEMANTIC_FRAME
from ...vocabulary_growth import digest as semantic_digest

from ..atlas_features import (
    AtlasFeatures,
    FeatureSchema,
    ProspectiveIdentityFeatureSet,
    build_feature_manifest,
    plan_prospective_identity_features,
)
from ..atlas_projection import (
    BANK_SIZE, SHAPE_POLICY, FrozenAtlasSnapshot,
    _canonical_bytes as _atlas_bytes, _digest as _atlas_sha256,
)
from ..atlas_snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from ...runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    initialize_bamf_row, project_identity_source_factor,
)

VOCABULARY_PRIOR_SCHEMA = "bilqis.atlas-vocabulary-prior/v1"
VOCABULARY_EXTENSION_SCHEMA = "bilqis.atlas-vocabulary-extension/v1"
VOCABULARY_CANDIDATE_SCHEMA = "bilqis.atlas-vocabulary-candidate/v1"
STAGED_ONLY = "STAGED_NOT_ADMITTED"
UINT32_MAX = (1 << 32) - 1
FP32_BYTES = 4
ADAMW_ARRAYS_PER_ROW = 3


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<atlas-vocabulary>",
        span_start=0, span_end=0,
    )


@dataclass(frozen=True)
class VocabularyPrior:
    """A source selection and a predecessor generation, not an admission grant."""

    source_selection: AtlasArtifactSelection
    extents: GenerationExtents
    features: AtlasFeatures
    feature_schema: FeatureSchema
    active_semantic_ids: tuple[str, ...]
    generation_id: str
    schema_version: str = VOCABULARY_PRIOR_SCHEMA


@dataclass(frozen=True, order=True)
class VocabularyAllocation:
    semantic_id: str
    abi_index: int
    bank: int
    row: int
    source_status: str


@dataclass(frozen=True)
class VocabularyExtension:
    """Replayable allocation proposal. Its contents confer no source rights."""

    parent_generation_id: str
    parent_extents_digest: str
    source_bundle_id: str
    semantic_release: str
    source_allocation_digest: str
    prospective_feature_digest: str
    shape_policy_digest: str
    allocations: tuple[VocabularyAllocation, ...]
    active_indices: tuple[int, ...]
    active_semantic_digest: str
    bank_count: int
    status: str = STAGED_ONLY
    schema_version: str = VOCABULARY_EXTENSION_SCHEMA


@dataclass(frozen=True)
class VocabularyBankParent:
    """Only the B01 identity-bank slice; full Factory custody remains downstream."""

    prior: VocabularyPrior
    weights: tuple[object, ...]
    moments_m: tuple[object, ...]
    moments_v: tuple[object, ...]
    row_counts: tuple[tuple[int, int], ...]
    feature_parameters: Mapping[str, object]
    run_seed: int
    resource_budget_bytes: int


@dataclass(frozen=True)
class CandidateState:
    """Detached, in-memory bank candidate; not a committed student generation."""

    parent_generation_id: str
    source_allocation_digest: str
    extents: GenerationExtents
    weights: tuple[object, ...]
    moments_m: tuple[object, ...]
    moments_v: tuple[object, ...]
    row_counts: tuple[tuple[int, int], ...]
    active_indices: tuple[int, ...]
    active_mask: bytes
    output_domain: tuple[tuple[int, str], ...]
    registry_mirror_delta: tuple[VocabularyAllocation, ...]
    estimated_new_bank_bytes: int
    status: str = STAGED_ONLY
    schema_version: str = VOCABULARY_CANDIDATE_SCHEMA


def _verified_prior(prior: VocabularyPrior) -> FrozenAtlasSnapshot:
    """Reload A01's repository-pinned artifact instead of trusting a dataclass."""
    if (type(prior) is not VocabularyPrior
            or prior.schema_version != VOCABULARY_PRIOR_SCHEMA
            or type(prior.source_selection) is not AtlasArtifactSelection
            or type(prior.extents) is not GenerationExtents
            or type(prior.features) is not AtlasFeatures
            or type(prior.feature_schema) is not FeatureSchema
            or not isinstance(prior.active_semantic_ids, tuple)
            or not isinstance(prior.generation_id, str)
            or len(prior.generation_id) != 64
            or any(char not in "0123456789abcdef" for char in prior.generation_id)):
        _invalid("BAMF_VOCABULARY_PRIOR_INVALID")
    # A successor feature-map predecessor must be authenticated by the
    # accepted generation/checkpoint owner, not by a caller's digest pair.
    # Until that owner supplies a sealed predecessor receipt, only A01's
    # source-replayable first-generation map is eligible for this API.
    if prior.feature_schema.predecessor is not None:
        _invalid("BAMF_VOCABULARY_PREDECESSOR_FEATURE_AUTHORITY_REQUIRED")
    snapshot = load_pinned_atlas_snapshot(prior.source_selection)
    if build_feature_manifest(snapshot, prior.feature_schema) != prior.features:
        _invalid("BAMF_VOCABULARY_FEATURE_SOURCE_REPLAY_MISMATCH")
    if (snapshot.shape_policy_sha256 != _atlas_sha256(_atlas_bytes(SHAPE_POLICY))
            or snapshot.bundle_id != prior.features.atlas_bundle_id
            or snapshot.release_sha256 != prior.features.semantic_release
            or snapshot.source_bundle_id != prior.features.source_bundle_id
            or prior.extents.factor_map_digest != prior.features.digest):
        _invalid("BAMF_VOCABULARY_SOURCE_LINEAGE_INVALID")
    abi = {entry.semantic_id: entry for entry in snapshot.abi_entries}
    if len(abi) != len(snapshot.abi_entries):
        _invalid("BAMF_VOCABULARY_ABI_DUPLICATE")
    try:
        active = tuple(abi[name].index for name in prior.active_semantic_ids)
    except (KeyError, TypeError):
        _invalid("BAMF_VOCABULARY_PRIOR_ACTIVE_ID_UNKNOWN")
    if (active != tuple(sorted(set(active)))
            or any(index > UINT32_MAX for index in active)
            or tuple(item.semantic_id for item in prior.features.concepts)
            != tuple(sorted(prior.active_semantic_ids, key=lambda name: name.encode("utf-8")))
            or _atlas_sha256(_atlas_bytes(list(active))) != prior.extents.active_semantic_digest
            or any(index >= prior.extents.semantic_bank_count * BANK_SIZE for index in active)):
        _invalid("BAMF_VOCABULARY_PRIOR_ACTIVE_SET_DRIFT")
    return snapshot


def _plan_from_snapshot(
    prior: VocabularyPrior,
    admissions: tuple[str, ...],
    shape_policy: ModelTopologySpecV2,
    snapshot: FrozenAtlasSnapshot,
) -> VocabularyExtension:
    """Pure source-derived allocation, also exercised by large boundary fixtures."""
    if (type(shape_policy) is not ModelTopologySpecV2
            or shape_policy.semantic_bank_rows != BANK_SIZE
            or not isinstance(admissions, tuple) or not admissions
            or any(not isinstance(name, str) or not name for name in admissions)):
        _invalid("BAMF_VOCABULARY_ADMISSIONS_INVALID")
    if len(set(admissions)) != len(admissions):
        _invalid("BAMF_VOCABULARY_ADMISSIONS_DUPLICATE")
    active_ids = set(prior.active_semantic_ids)
    if active_ids.intersection(admissions):
        _invalid("BAMF_VOCABULARY_ALREADY_ACTIVE")
    from ..atlas_features import plan_prospective_identity_features
    prospective = plan_prospective_identity_features(
        snapshot, prior.features, admissions,
        expected_feature_digest=prior.extents.factor_map_digest)
    allocations = tuple(sorted((
        VocabularyAllocation(
            item.semantic_id, item.abi_index,
            item.abi_index // BANK_SIZE, item.abi_index % BANK_SIZE,
            item.source_status,
        ) for item in prospective.identities
    ), key=lambda item: item.abi_index))
    if any(item.abi_index > UINT32_MAX for item in allocations):
        _invalid("BAMF_VOCABULARY_UINT32_EXHAUSTED")
    by_id = {entry.semantic_id: entry for entry in snapshot.abi_entries}
    active_indices = tuple(sorted(
        [by_id[name].index for name in prior.active_semantic_ids]
        + [item.abi_index for item in allocations]))
    bank_count = max(
        prior.extents.semantic_bank_count,
        allocations[-1].bank + 1,
    )
    allocation_source_digest = semantic_digest({
        "schema": VOCABULARY_EXTENSION_SCHEMA,
        "parent_generation_id": prior.generation_id,
        "parent_extents_digest": prior.extents.digest,
        "source_bundle_id": snapshot.source_bundle_id,
        "atlas_bundle_id": snapshot.bundle_id,
        "semantic_release": snapshot.release_sha256,
        "prospective_feature_digest": prospective.digest,
        "allocations": [(item.semantic_id, item.abi_index)
                        for item in allocations],
    })
    return VocabularyExtension(
        parent_generation_id=prior.generation_id,
        parent_extents_digest=prior.extents.digest,
        source_bundle_id=snapshot.source_bundle_id,
        semantic_release=snapshot.release_sha256,
        source_allocation_digest=allocation_source_digest,
        prospective_feature_digest=prospective.digest,
        shape_policy_digest=shape_policy.shape_policy_digest,
        allocations=allocations,
        active_indices=active_indices,
        active_semantic_digest=_atlas_sha256(_atlas_bytes(list(active_indices))),
        bank_count=bank_count,
    )


def plan_vocabulary_extension(
    prior: VocabularyPrior,
    admissions: tuple[str, ...],
    shape_policy: ModelTopologySpecV2,
) -> VocabularyExtension:
    """Plan stable A01 ABI slots; no row or neural state is activated here."""
    snapshot = _verified_prior(prior)
    return _plan_from_snapshot(prior, admissions, shape_policy, snapshot)


def _mask(indices: tuple[int, ...], capacity: int) -> bytes:
    mask = bytearray((capacity + 7) // 8)
    for index in indices:
        if not 0 <= index < capacity:
            _invalid("BAMF_VOCABULARY_MASK_INDEX_INVALID")
        mask[index // 8] |= 1 << (index % 8)
    return bytes(mask)


def _validate_bank_parent(parent: VocabularyBankParent) -> None:
    import mlx.core as mx

    if (type(parent) is not VocabularyBankParent
            or type(parent.prior) is not VocabularyPrior
            or type(parent.run_seed) is not int or parent.run_seed < 0
            or type(parent.resource_budget_bytes) is not int
            or parent.resource_budget_bytes < 0
            or not isinstance(parent.feature_parameters, Mapping)
            or any(not isinstance(part, tuple) for part in (
                parent.weights, parent.moments_m, parent.moments_v))
            or not isinstance(parent.row_counts, tuple)):
        _invalid("BAMF_VOCABULARY_BANK_PARENT_INVALID")
    count = parent.prior.extents.semantic_bank_count
    if any(len(part) != count for part in (
            parent.weights, parent.moments_m, parent.moments_v)):
        _invalid("BAMF_VOCABULARY_BANK_COUNT_INVALID")
    shape = (BANK_SIZE, ModelTopologySpecV2.width)
    for bank in range(count):
        for part in (parent.weights, parent.moments_m, parent.moments_v):
            value = part[bank]
            if (not isinstance(value, mx.array)
                    or value.dtype != mx.float32 or value.shape != shape):
                _invalid("BAMF_VOCABULARY_BANK_SHAPE_INVALID")
    if (any(not isinstance(item, tuple) or len(item) != 2
            or type(item[0]) is not int or type(item[1]) is not int
            or item[1] < 0 for item in parent.row_counts)
            or tuple(index for index, _ in parent.row_counts)
            != tuple(sorted(set(index for index, _ in parent.row_counts)))):
        _invalid("BAMF_VOCABULARY_ROW_COUNTS_INVALID")


def apply_vocabulary_extension(
    parent: VocabularyBankParent,
    plan: VocabularyExtension,
) -> CandidateState:
    """Build a detached bank candidate without adopting a source or student."""
    import mlx.core as mx
    import numpy as np

    _validate_bank_parent(parent)
    if (type(plan) is not VocabularyExtension
            or not isinstance(plan.allocations, tuple)
            or any(type(item) is not VocabularyAllocation
                   for item in plan.allocations)):
        _invalid("BAMF_VOCABULARY_PLAN_INVALID")
    snapshot = _verified_prior(parent.prior)
    expected = _plan_from_snapshot(
        parent.prior,
        tuple(item.semantic_id for item in plan.allocations),
        ModelTopologySpecV2(), snapshot,
    )
    if plan != expected:
        _invalid("BAMF_VOCABULARY_PLAN_SOURCE_REPLAY_MISMATCH")
    old_active = tuple(
        snapshot.abi_for_semantic(name).index
        for name in parent.prior.active_semantic_ids)
    if tuple(index for index, _ in parent.row_counts) != old_active:
        _invalid("BAMF_VOCABULARY_ROW_COUNTS_ACTIVE_SET_MISMATCH")
    old_count = parent.prior.extents.semantic_bank_count
    estimated_bytes = (
        (plan.bank_count - old_count) * BANK_SIZE * ModelTopologySpecV2.width
        * FP32_BYTES * ADAMW_ARRAYS_PER_ROW
    )
    if estimated_bytes > parent.resource_budget_bytes:
        _invalid("BAMF_VOCABULARY_BANK_RESOURCE_BUDGET_EXCEEDED")
    source_plan, factors = prepare_identity_factors(
        snapshot, parent.prior.features,
        tuple(item.semantic_id for item in plan.allocations),
        parent.feature_parameters,
        extents=parent.prior.extents,
    )
    if (source_plan.digest != plan.prospective_feature_digest
            or tuple(name for name, _ in factors)
            != tuple(item.semantic_id for item in plan.allocations)):
        _invalid("BAMF_VOCABULARY_FACTOR_SOURCE_MISMATCH")
    if source_plan.type_map != parent.prior.features.type_map:
        _invalid("BAMF_VOCABULARY_FACTOR_TABLE_EXTENSION_REQUIRED")

    # Copy only affected banks. Unchanged MLX arrays are shared read-only;
    # parent tensors and native AdamW state are never modified in place.
    touched = {item.bank for item in plan.allocations}
    weights, moments_m, moments_v = [], [], []
    shape = (BANK_SIZE, ModelTopologySpecV2.width)
    for bank in range(plan.bank_count):
        if bank < old_count and bank not in touched:
            weights.append(parent.weights[bank])
            moments_m.append(parent.moments_m[bank])
            moments_v.append(parent.moments_v[bank])
        elif bank < old_count:
            weights.append(np.asarray(parent.weights[bank]).copy())
            moments_m.append(np.asarray(parent.moments_m[bank]).copy())
            moments_v.append(np.asarray(parent.moments_v[bank]).copy())
        else:
            weights.append(np.zeros(shape, dtype=np.float32))
            moments_m.append(np.zeros(shape, dtype=np.float32))
            moments_v.append(np.zeros(shape, dtype=np.float32))

    staged_extents = GenerationExtents(
        plan.bank_count, parent.prior.extents.motif_page_count,
        plan.active_semantic_digest,
        parent.prior.extents.motif_key_map_digest,
        parent.prior.extents.factor_map_digest,
    )
    identity_specs = {
        item.name: item for item in expected_bamf_shapes(
            ModelTopologySpecV2(), staged_extents)
        if item.name.startswith("identity.bank.")
    }
    for item, (_, factor) in zip(plan.allocations, factors):
        parameter = identity_specs[f"identity.bank.{item.bank}"]
        weights[item.bank][item.row] = initialize_bamf_row(
            parameter, run_seed=parent.run_seed,
            row_id=item.semantic_id, factor=factor)
        moments_m[item.bank][item.row] = 0
        moments_v[item.bank][item.row] = 0
    staged_weights = tuple(
        mx.array(value, dtype=mx.float32) if bank in touched else value
        for bank, value in enumerate(weights))
    staged_m = tuple(
        mx.array(value, dtype=mx.float32) if bank in touched else value
        for bank, value in enumerate(moments_m))
    staged_v = tuple(
        mx.array(value, dtype=mx.float32) if bank in touched else value
        for bank, value in enumerate(moments_v))
    mx.eval(staged_weights, staged_m, staged_v)
    by_index = {entry.index: entry.semantic_id for entry in snapshot.abi_entries}
    counts = tuple(sorted(
        (*parent.row_counts, *((item.abi_index, 0) for item in plan.allocations))))
    return CandidateState(
        parent_generation_id=parent.prior.generation_id,
        source_allocation_digest=plan.source_allocation_digest,
        extents=staged_extents,
        weights=staged_weights, moments_m=staged_m, moments_v=staged_v,
        row_counts=counts,
        active_indices=plan.active_indices,
        active_mask=_mask(plan.active_indices, plan.bank_count * BANK_SIZE),
        output_domain=tuple(
            (index, by_index[index]) for index in plan.active_indices),
        registry_mirror_delta=plan.allocations,
        estimated_new_bank_bytes=estimated_bytes,
    )


def staged_tied_logits(
    candidate: CandidateState,
    hidden: object,
) -> tuple[tuple[int, ...], object]:
    """Only active ABI rows compete, in global index order without modulo alias."""
    import mlx.core as mx

    if (type(candidate) is not CandidateState
            or candidate.status != STAGED_ONLY
            or not isinstance(hidden, mx.array)
            or hidden.dtype != mx.float32
            or hidden.shape != (ModelTopologySpecV2.width,)
            or len(candidate.weights) != candidate.extents.semantic_bank_count
            or tuple(index for index, _ in candidate.output_domain)
            != candidate.active_indices
            or candidate.active_mask != _mask(
                candidate.active_indices,
                candidate.extents.semantic_bank_count * BANK_SIZE)):
        _invalid("BAMF_VOCABULARY_READOUT_INVALID")
    logits = []
    for bank, weights in enumerate(candidate.weights):
        rows = tuple(
            index % BANK_SIZE for index in candidate.active_indices
            if index // BANK_SIZE == bank)
        if rows:
            logits.append(mx.take(
                weights, mx.array(rows, dtype=mx.int32), axis=0) @ hidden)
    if not logits:
        _invalid("BAMF_VOCABULARY_READOUT_EMPTY")
    output = mx.concatenate(logits)
    mx.eval(output)
    return candidate.active_indices, output


def prepare_identity_factors(
    release: FrozenAtlasSnapshot,
    current_features: AtlasFeatures,
    semantic_ids: tuple[str, ...],
    feature_parameters: Mapping[str, object],
    *,
    extents: GenerationExtents,
) -> tuple[ProspectiveIdentityFeatureSet, tuple[tuple[str, object], ...]]:
    """Stage source-bound 768-wide factors without activating or training rows."""
    plan = plan_prospective_identity_features(
        release, current_features, semantic_ids,
        expected_feature_digest=extents.factor_map_digest)
    factors = tuple(
        (item.semantic_id, project_identity_source_factor(
            feature_parameters,
            type_rows=item.type_rows,
            type_overflow=item.type_overflow,
            graph64=item.graph64,
            extents=extents,
            predecessor_feature_digest=plan.predecessor_feature_digest))
        for item in plan.identities
    )
    return plan, factors
