"""A02 production vocabulary admission through accepted B13 custody."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import shutil

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_acceptance import (
    candidate_identity_digest, mint_parameter_extension_binding,
)
from bilqis_mlx.learning._atlas_candidate.state import (
    _issue_parameter_extension_state,
)
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
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
from bilqis_mlx.vocabulary_growth import digest as semantic_digest

from ._feature_authority_records import _feature_schema
from ._vocabulary_admission_records import (
    A02ProductionAdmissionReceipt, EVENT, issue_vocabulary_admission_decision,
)
from .feature_authority import (
    read_accepted_generation_feature_lineage,
    read_accepted_generation_feature_receipt,
)
from .publication import (
    _pointer_lock, _read_pointer, load_bamf_generation_authority,
    publish_bamf_generation,
)
from .records import BamfBundleCandidate, _hex, canonical, invalid, sha

_ADMISSION_OWNER_ISSUER = object()


@dataclass(frozen=True, init=False)
class _VocabularyAdmissionEvaluation:
    """Opaque proof that the A02 production owner derived an exact successor."""

    run_id: str
    generation: int
    parent_manifest_sha256: str
    parent_feature_receipt_sha256: str
    source_allocation_sha256: str
    prepared_extents_sha256: str
    active_mask_sha256: str
    registry_mirror_sha256: str
    resource_estimate_sha256: str
    candidate_identity_sha256: str
    parent_candidate_identity_sha256: str
    feature_sha256: str
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        invalid("BAMF_A02_ADMISSION_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self) -> None:
        values = (
            self.parent_manifest_sha256, self.parent_feature_receipt_sha256,
            self.source_allocation_sha256, self.prepared_extents_sha256,
            self.active_mask_sha256, self.registry_mirror_sha256,
            self.resource_estimate_sha256, self.candidate_identity_sha256,
            self.parent_candidate_identity_sha256, self.feature_sha256,
        )
        if (getattr(self, "_issuance", None) is not _ADMISSION_OWNER_ISSUER
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 1
                or any(not _hex(value) for value in values)):
            invalid("BAMF_A02_ADMISSION_OWNER_EVALUATION_INVALID")


def _issue_vocabulary_admission_evaluation(
        parent, parent_manifest: str, parent_receipt, plan, prepared, mirror,
        resource_record: dict, successor_state, features,
) -> _VocabularyAdmissionEvaluation:
    """Derive admission authority from the exact objects produced by A02/B13."""
    from bilqis_mlx.learning.atlas_candidate import CandidateState
    from bilqis_mlx.semantics.atlas.vocabulary import VocabularyExtension
    from bilqis_mlx.semantics.atlas.vocabulary_resources import RegistryMirrorDelta
    from bilqis_mlx.semantics.atlas.vocabulary_transaction import PreparedVocabularyCandidate
    from bilqis_mlx.semantics.atlas_features import AtlasFeatures
    from ._feature_authority_records import AcceptedGenerationFeatureReceipt
    from .records import CompleteStudent

    if (type(parent) is not CompleteStudent
            or type(parent_receipt) is not AcceptedGenerationFeatureReceipt
            or type(plan) is not VocabularyExtension
            or type(prepared) is not PreparedVocabularyCandidate
            or type(mirror) is not RegistryMirrorDelta
            or type(successor_state) is not CandidateState
            or type(features) is not AtlasFeatures
            or not isinstance(resource_record, dict)):
        invalid("BAMF_A02_ADMISSION_OWNER_INPUT_INVALID")
    item = object.__new__(_VocabularyAdmissionEvaluation)
    values = (
        ("run_id", parent.run_id), ("generation", parent.generation + 1),
        ("parent_manifest_sha256", parent_manifest),
        ("parent_feature_receipt_sha256", parent_receipt.digest),
        ("source_allocation_sha256", plan.source_allocation_digest),
        ("prepared_extents_sha256", prepared.extents_digest),
        ("active_mask_sha256", prepared.active_mask_sha256),
        ("registry_mirror_sha256", mirror.digest),
        ("resource_estimate_sha256", _digest_record(resource_record)),
        ("candidate_identity_sha256", candidate_identity_digest(successor_state)),
        ("parent_candidate_identity_sha256",
         candidate_identity_digest(parent.retained_state)),
        ("feature_sha256", features.digest),
        ("_issuance", _ADMISSION_OWNER_ISSUER),
    )
    for name, value in values:
        object.__setattr__(item, name, value)
    item.__post_init__()
    return item


def _active_ids(snapshot) -> tuple[str, ...]:
    return tuple(entry.semantic_id for entry in sorted(
        (entry for entry in snapshot.abi_entries if entry.active),
        key=lambda item: item.index))


def _bank_parent(parent, prior, available: int) -> VocabularyBankParent:
    optimizer = parent.retained_state.optimizer
    banks = range(parent.extents.semantic_bank_count)
    weights = tuple(optimizer.parameters[f"identity.bank.{bank}"] for bank in banks)
    moments_m = tuple(optimizer.m[f"identity.bank.{bank}"] for bank in banks)
    moments_v = tuple(optimizer.v[f"identity.bank.{bank}"] for bank in banks)
    snapshot = load_pinned_atlas_snapshot(prior.source_selection)
    counts = []
    for entry in sorted((entry for entry in snapshot.abi_entries if entry.active),
                        key=lambda item: item.index):
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


def admit_vocabulary_extension(
        run_dir: Path, artifact_path: str, source_bundle_path: Path,
        admissions: tuple[str, ...]) -> A02ProductionAdmissionReceipt:
    """Source-admit, atomically publish and read back one A02 parameter extension."""
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
    prior = VocabularyPrior(
        selection, parent.extents, features, schema, _active_ids(snapshot),
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
    evaluation = _issue_vocabulary_admission_evaluation(
        parent, parent_manifest, parent_receipt, plan, prepared, mirror,
        resource_record, successor_state, features)
    decision = issue_vocabulary_admission_decision(evaluation)
    event = {
        "event": EVENT,
        "decision": decision.to_record(), "decision_sha256": decision.digest,
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
    binding = mint_parameter_extension_binding(decision, successor_state)
    pointer = publish_bamf_generation(run_dir, candidate, acceptance=binding)
    if pointer["manifest_sha256"] == parent_manifest:
        invalid("BAMF_A02_SUCCESSOR_NOT_PUBLISHED")
    return read_vocabulary_admission_receipt(pointer_path, artifact_path)


def read_vocabulary_admission_receipt(
        pointer_path: Path, artifact_path: str) -> A02ProductionAdmissionReceipt:
    """Derive the A02 receipt from the accepted B13 generation and its outbox."""
    pointer_path = Path(pointer_path)
    student, manifest = load_bamf_generation_authority(pointer_path)
    feature = read_accepted_generation_feature_receipt(pointer_path, artifact_path)
    events = [event for event in student.outbox if event.get("event") == EVENT]
    if len(events) != 1:
        invalid("BAMF_A02_ADMISSION_EVENT_MISSING")
    event = events[0]
    decision = event.get("decision")
    if (not isinstance(decision, dict)
            or event.get("decision_sha256") != sha(canonical(decision))
            or decision.get("run_id") != student.run_id
            or decision.get("generation") != student.generation
            or decision.get("feature_sha256") != feature.feature_sha256
            or decision.get("candidate_identity_sha256")
            != candidate_identity_digest(student.retained_state)
            or decision.get("prepared_extents_sha256") != student.extents.digest
            or student.transition.get("kind") != "PARAMETER_EXTENSION"):
        invalid("BAMF_A02_ADMISSION_RECEIPT_DRIFT")
    mirror = event.get("registry_mirror")
    resources = event.get("resource_estimate")
    if (not isinstance(mirror, dict) or not isinstance(resources, dict)
            or semantic_digest(mirror) != decision.get("registry_mirror_sha256")
            or sha(canonical(resources)) != decision.get("resource_estimate_sha256")):
        invalid("BAMF_A02_ADMISSION_RECEIPT_DRIFT")
    with _pointer_lock(pointer_path.parent):
        pointer = _read_pointer(pointer_path)
    if pointer is None or pointer["manifest_sha256"] != manifest:
        invalid("BAMF_A02_ADMISSION_RECEIPT_DRIFT")
    return A02ProductionAdmissionReceipt(
        run_id=student.run_id, generation=student.generation,
        parent_manifest_sha256=student.parent_manifest_sha256,
        successor_manifest_sha256=manifest,
        acceptance_sha256=pointer["acceptance_sha256"],
        feature_receipt_sha256=feature.digest,
        decision_sha256=event["decision_sha256"],
        source_allocation_sha256=decision["source_allocation_sha256"],
        registry_mirror_sha256=decision["registry_mirror_sha256"],
        resource_estimate_sha256=decision["resource_estimate_sha256"],
        active_set_sha256=student.extents.active_semantic_digest,
        feature_sha256=feature.feature_sha256,
        semantic_bank_count=student.extents.semantic_bank_count)
