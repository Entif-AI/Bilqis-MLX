"""A02 production-quality vocabulary staging through accepted B13 custody."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import shutil

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning._atlas_candidate.state import (
    _issue_parameter_extension_state,
)
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from bilqis_mlx.semantics.atlas_projection import (
    _canonical_bytes as _atlas_bytes, _digest as _atlas_sha256,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.semantics.atlas.vocabulary import VocabularyBankParent, VocabularyPrior
from bilqis_mlx.semantics.atlas.vocabulary_planning import (
    _plan_authenticated_vocabulary_extension,
)
from bilqis_mlx.semantics.atlas.vocabulary_resources import (
    _build_authenticated_registry_mirror_delta,
)
from bilqis_mlx.semantics.atlas.vocabulary_transaction import (
    FullVocabularyParent, _stage_authenticated_full_vocabulary_extension,
)
from ._feature_authority_records import _feature_schema
from ._vocabulary_admission_records import (
    A02StagedVocabularyExtension, A02VocabularyStagingReceipt, STAGED_EVENT,
)
from .feature_authority import read_accepted_generation_feature_lineage
from .publication import load_bamf_generation_authority
from .records import BamfBundleCandidate, canonical, invalid, sha


def _accepted_active_ids(parent, snapshot) -> tuple[str, ...]:
    """Recover the active semantic ABI from accepted B12/B13 custody."""
    indices = tuple(sorted(
        row.bank_index * ModelTopologySpecV2.semantic_bank_rows + row.row_index
        for row in parent.retained_state.policy.row_ages))
    if (indices != tuple(sorted(set(indices)))
            or any(index >= parent.extents.semantic_bank_count
                   * ModelTopologySpecV2.semantic_bank_rows for index in indices)
            or _atlas_sha256(_atlas_bytes(list(indices)))
            != parent.extents.active_semantic_digest
            or parent.semantic_abi.get("active_set_sha256")
            != parent.extents.active_semantic_digest):
        invalid("BAMF_A02_PARENT_ACTIVE_SET_DRIFT")
    by_index = {entry.index: entry.semantic_id for entry in snapshot.abi_entries}
    if len(by_index) != len(snapshot.abi_entries):
        invalid("BAMF_A02_PARENT_ACTIVE_SET_DRIFT")
    try:
        return tuple(by_index[index] for index in indices)
    except KeyError:
        invalid("BAMF_A02_PARENT_ACTIVE_SET_DRIFT")


def _bank_parent(parent, prior, available: int) -> VocabularyBankParent:
    optimizer = parent.retained_state.optimizer
    banks = range(parent.extents.semantic_bank_count)
    weights = tuple(optimizer.parameters[f"identity.bank.{bank}"] for bank in banks)
    moments_m = tuple(optimizer.m[f"identity.bank.{bank}"] for bank in banks)
    moments_v = tuple(optimizer.v[f"identity.bank.{bank}"] for bank in banks)
    counts = []
    snapshot = load_pinned_atlas_snapshot(prior.source_selection)
    for semantic_id in prior.active_semantic_ids:
        entry = snapshot.abi_for_semantic(semantic_id)
        name = f"identity.bank.{entry.index // ModelTopologySpecV2.semantic_bank_rows}"
        count = optimizer.update_counts[name][entry.index % ModelTopologySpecV2.semantic_bank_rows]
        counts.append((entry.index, int(np.asarray(count))))
    feature_names = (
        "features.type", "features.project_type",
        "features.project_graph", "features.gates",
    )
    return VocabularyBankParent(
        prior, weights, moments_m, moments_v, tuple(counts),
        {name: optimizer.parameters[name] for name in feature_names},
        parent.topology.default_run_seed, available)


def _full_parent(parent, prior, available: int) -> FullVocabularyParent:
    optimizer = parent.retained_state.optimizer
    state = {
        "step": mx.array(parent.retained_state.optimizer_step, dtype=mx.uint64),
        "learning_rate": mx.array(
            parent.optimizer_hyperparameters.learning_rate, dtype=mx.float32),
        **{name: {"m": optimizer.m[name], "v": optimizer.v[name]}
           for name in optimizer.parameters},
    }
    return FullVocabularyParent(
        _bank_parent(parent, prior, available), parent.topology,
        optimizer.parameters, state, observed_available_bytes=available)


def _successor_state(parent, prepared):
    prior = parent.retained_state.optimizer
    counts = {}
    for name, parameter in prepared.parameters.items():
        if name in prior.update_counts:
            counts[name] = prior.update_counts[name]
        elif name.startswith("identity.bank."):
            counts[name] = mx.zeros((parameter.shape[0],), dtype=mx.uint64)
        else:
            invalid("BAMF_A02_UNEXPECTED_PARAMETER_EXTENSION")
    optimizer = AdamWStateTree(
        prepared.parameters,
        {name: prepared.optimizer_state[name]["m"] for name in prepared.parameters},
        {name: prepared.optimizer_state[name]["v"] for name in prepared.parameters},
        counts)
    ages = {row.identity: row for row in parent.retained_state.policy.row_ages}
    for item in prepared.bank_candidate.registry_mirror_delta:
        ages.setdefault((item.bank, item.row), IdentityRowAge(item.bank, item.row, 0))
    old_policy = parent.retained_state.policy
    policy = PlasticityPolicy(
        old_policy.mode, old_policy.accepted_fast_since_full,
        tuple(ages[key] for key in sorted(ages)),
        old_policy.policy_version, old_policy.schema_version)
    return _issue_parameter_extension_state(
        parent.retained_state, optimizer, policy)


def _digest_record(value) -> str:
    return sha(canonical(value))


def _resource_requirement(resource) -> dict:
    """Stable admission requirement; live free bytes are checked, not identity."""
    record = asdict(resource)
    record.pop("observed_available_bytes")
    record.pop("fits")
    return record


def stage_vocabulary_extension(
        run_dir: Path, artifact_path: str, source_bundle_path: Path,
        admissions: tuple[str, ...]) -> A02StagedVocabularyExtension:
    """Prepare one exact A02 successor without granting C07 admission authority."""
    run_dir = Path(run_dir)
    pointer_path = run_dir / "bamf-state.json"
    parent_receipt, features, predecessor = read_accepted_generation_feature_lineage(
        pointer_path, artifact_path)
    if predecessor is None:
        invalid("BAMF_VOCABULARY_PREDECESSOR_FEATURE_AUTHORITY_REQUIRED")
    parent, parent_manifest = load_bamf_generation_authority(pointer_path)
    if parent_manifest != parent_receipt.generation_manifest_sha256:
        invalid("BAMF_A02_PARENT_AUTHORITY_DRIFT")
    selection = AtlasArtifactSelection(
        str(artifact_path), features.atlas_bundle_id,
        features.semantic_release, features.source_bundle_id)
    snapshot = load_pinned_atlas_snapshot(selection)
    recorded = _feature_schema(parent.compiler_features)
    schema = FeatureSchema(
        recorded.role_ids, recorded.schema_ids, predecessor,
        recorded.source_bindings)
    active_ids = _accepted_active_ids(parent, snapshot)
    prior = VocabularyPrior(
        selection, parent.extents, features, schema, active_ids,
        parent_manifest)
    plan = _plan_authenticated_vocabulary_extension(
        prior, admissions, parent.topology, features, predecessor)
    available = int(shutil.disk_usage(run_dir).free)
    prepared = _stage_authenticated_full_vocabulary_extension(
        _full_parent(parent, prior, available), plan,
        accepted_features=features, predecessor=predecessor)
    mirror = _build_authenticated_registry_mirror_delta(
        prior, plan, source_bundle_path=Path(source_bundle_path),
        accepted_features=features, predecessor=predecessor)
    successor_state = _successor_state(parent, prepared)
    resource_record = _resource_requirement(prepared.resource_estimate)
    receipt = A02VocabularyStagingReceipt(
        run_id=parent.run_id, generation=parent.generation + 1,
        parent_manifest_sha256=parent_manifest,
        parent_feature_receipt_sha256=parent_receipt.digest,
        candidate_identity_sha256=candidate_identity_digest(successor_state),
        source_allocation_sha256=plan.source_allocation_digest,
        plan_sha256=sha(canonical(asdict(plan))),
        prepared_extents_sha256=prepared.extents_digest,
        active_mask_sha256=prepared.active_mask_sha256,
        registry_mirror_sha256=mirror.digest,
        resource_estimate_sha256=_digest_record(resource_record),
        active_set_sha256=prepared.bank_candidate.extents.active_semantic_digest,
        feature_sha256=features.digest,
        semantic_bank_count=prepared.bank_candidate.extents.semantic_bank_count,
    )
    event = {
        "event": STAGED_EVENT,
        "staging_receipt": receipt.to_record(),
        "plan": asdict(plan), "registry_mirror": asdict(mirror),
        "resource_estimate": resource_record,
    }
    semantic = dict(parent.semantic_abi)
    semantic.update({
        "active_set_sha256": prepared.bank_candidate.extents.active_semantic_digest,
        "semantic_bank_count": prepared.bank_candidate.extents.semantic_bank_count,
        "bank_identities": [
            f"bank:{index}" for index in range(
                prepared.bank_candidate.extents.semantic_bank_count)],
    })
    candidate = BamfBundleCandidate(
        parent.run_id, parent.generation + 1, parent_manifest,
        parent.implementation_sha256, parent.topology,
        prepared.bank_candidate.extents, successor_state,
        parent.optimizer_hyperparameters, parent.provenance,
        semantic, dict(parent.compiler_features),
        dict(parent.correction_frontier), dict(parent.teacher_state),
        dict(parent.evaluation_contract),
        {"schema": "bilqis.mlx.bamf-generation-transition/v1",
         "kind": "PARAMETER_EXTENSION", "invalidate_derived_caches": True},
        (event,))
    return A02StagedVocabularyExtension(candidate, receipt)
