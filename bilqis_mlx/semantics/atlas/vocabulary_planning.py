"""Source-replayed stable ABI planning for A02 vocabulary growth."""
from __future__ import annotations

from ...vocabulary_growth import digest as semantic_digest
from ...runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from ..atlas_features import (
    AtlasFeatures, FeatureSchema,
    build_feature_manifest, plan_prospective_identity_features,
)
from ..atlas_projection import (
    BANK_SIZE, SHAPE_POLICY, FrozenAtlasSnapshot,
    _canonical_bytes as _atlas_bytes, _digest as _atlas_sha256,
)
from .snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from .vocabulary_contracts import (
    UINT32_MAX, VOCABULARY_EXTENSION_SCHEMA, VOCABULARY_PRIOR_SCHEMA,
    VocabularyAllocation, VocabularyExtension, VocabularyPrior, _invalid,
)

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
