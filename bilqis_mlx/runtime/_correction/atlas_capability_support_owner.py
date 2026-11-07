"""Production C09 ownership for learned capability support from accepted B13 custody."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    ACCEPTANCE_SCHEMA, AcceptedCandidateBinding, candidate_identity_digest,
)
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.domains import contract_digest

from .atlas_requalification_contracts import (
    CapabilitySupport, RequalificationLedger, RequalificationStatus,
)
from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from .atlas_revalidation_queue import RevalidationProgress, RevalidationQueue
from .atlas_revalidation_runtime import (
    advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, revalidate_node,
)
from .atlas_source_authority import SourceAuthorityRegistry


_ISSUER = object()


def _anchor_dependencies(anchors, policy_sha256, manifest_sha256):
    dependencies = {
        DependencyRef(DependencyKind.POLICY, "retention-policy:" + policy_sha256),
        DependencyRef(DependencyKind.RELEASE, "generation:" + manifest_sha256),
    }
    for anchor in anchors:
        dependencies.update((
            DependencyRef(DependencyKind.SOURCE, anchor[1]),
            DependencyRef(DependencyKind.RELEASE, "source-release:" + anchor[5]),
        ))
    return tuple(sorted(dependencies))


def _verify_anchor_proofs(binding, student, capability_id):
    anchors = tuple(anchor for anchor in binding.source_anchors
                    if anchor[0] == capability_id)
    if not anchors:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_SOURCE_MISSING")
    proofs = {proof.training_authority_sha256: proof
              for proof in student.retained_state.step_proofs}
    if None in proofs or len(proofs) != len(student.retained_state.step_proofs):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_PROOF_DRIFT")
    for anchor in anchors:
        proof = proofs.get(anchor[8])
        if (proof is None
                or proof.source_release_sha256 != anchor[5]
                or proof.training_batch_sha256 != anchor[6]
                or proof.target_capability_id != anchor[0]
                or proof.source_family_id != anchor[3]
                or proof.episode_id != anchor[4]):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_PROOF_DRIFT")
    return anchors


def _materialized_support(binding, student, manifest_sha256, capability_id):
    anchors = _verify_anchor_proofs(binding, student, capability_id)
    dependencies = _anchor_dependencies(
        anchors, binding.policy_sha256, manifest_sha256)
    node = ArtifactNode(
        artifact_id="capability-support:" + capability_id,
        kind=ArtifactKind.CAPABILITY_SUPPORT,
        content_digest=contract_digest({
            "capability": capability_id,
            "accepted_generation": manifest_sha256,
            "acceptance": binding.digest,
            "decision": binding.decision_sha256,
            "evidence": binding.evidence_sha256,
            "policy": binding.policy_sha256,
            "source_anchors": anchors,
        }),
        eligible=True,
        immediate_dependencies=dependencies,
        impact=0,
        exigency=0,
    )
    support = CapabilitySupport(
        capability_id=capability_id,
        support_artifact_ids=(node.artifact_id,),
        source_anchor_ids=tuple(sorted({anchor[1] for anchor in anchors})),
        retained_generation_sha256=manifest_sha256,
        observation_ids=tuple(sorted((
            "acceptance:" + binding.digest,
            "decision:" + binding.decision_sha256,
            "evidence:" + binding.evidence_sha256,
        ))),
        status=RequalificationStatus.QUALIFIED,
    )
    return support, node


class CapabilitySupportArtifactOwner:
    """Stateful before-read hold owner for one source-qualified learned capability."""

    def __init__(self, *args, **kwargs):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_OWNER_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _ISSUER
                or not isinstance(self._support, CapabilitySupport)
                or not isinstance(self._index, DependencyIndex)
                or self._index.node(self._support.support_artifact_ids[0]).kind
                is not ArtifactKind.CAPABILITY_SUPPORT):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_OWNER_INVALID")

    @property
    def capability_id(self) -> str:
        return self._support.capability_id

    @property
    def support(self) -> CapabilitySupport:
        return self._support

    @property
    def ledger(self) -> RequalificationLedger:
        return RequalificationLedger((self._support,))

    @property
    def current_node(self) -> ArtifactNode:
        return self._index.node(self._support.support_artifact_ids[0])

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    def require(self, capability_id: str) -> CapabilitySupport:
        if capability_id != self.capability_id:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_OWNER_MISMATCH")
        if self._support.status is not RequalificationStatus.QUALIFIED:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_REQUALIFICATION_REQUIRED")
        if self._queue is not None:
            read_artifact(self._index, self._queue, self.current_node.artifact_id)
        elif not self.current_node.eligible:
            _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
        return self._support

    def apply_correction(
        self, event: CorrectionEvent, authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationQueue:
        self._queue = apply_correction(event, self._index, authority_registry)
        return self._queue

    def advance(
        self, frontier: RevalidationFrontier,
        authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationProgress:
        if self._queue is None:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_REVALIDATION_NOT_HELD")
        task = next_revalidation_task(self._index, self._queue)
        if task is None:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_REVALIDATION_NOT_PENDING")
        transition = revalidate_node(
            self._index.node(task.artifact_id), frontier, authority_registry)
        progress = advance_revalidation(
            self._index, self._queue, transition, authority_registry)
        self._index = progress.index
        self._queue = progress.queue
        if transition.changed:
            self._support = replace(
                self._support,
                status=RequalificationStatus.REQUALIFICATION_REQUIRED)
        return progress


def _issue_owner(support, node):
    owner = object.__new__(CapabilitySupportArtifactOwner)
    owner._support = support
    owner._index = DependencyIndex.build((node,))
    owner._queue = None
    owner._issuance = _ISSUER
    owner.__post_init__()
    return owner


def load_capability_support_owner(
    run_dir: Path, capability_id: str,
) -> CapabilitySupportArtifactOwner:
    """Materialize current support only from accepted B13 custody and v3 source anchors."""
    from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle
    from bilqis_mlx.runtime.bamf_bundle.publication import (
        ACCEPTANCE_DIR, _live_bundle_manifest, _pointer_lock, _read_pointer,
    )

    run_dir = Path(run_dir)
    with _pointer_lock(run_dir):
        pointer = _read_pointer(run_dir / "bamf-state.json")
        if pointer is None:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_GENERATION_MISSING")
        manifest_sha256 = pointer["manifest_sha256"]
        _live_bundle_manifest(run_dir, pointer)
        student = load_bamf_bundle(
            run_dir / "bamf-bundles" / manifest_sha256,
            expected_manifest_sha256=manifest_sha256)
        path = run_dir / ACCEPTANCE_DIR / f"{manifest_sha256}.json"
        if path.is_symlink() or not path.is_file():
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTANCE_MISSING")
        try:
            binding = AcceptedCandidateBinding.from_record(json.loads(path.read_bytes()))
        except (UnicodeDecodeError, json.JSONDecodeError, BilqisError):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTANCE_INVALID")
        if (binding.schema_version != ACCEPTANCE_SCHEMA
                or binding.digest != pointer.get("acceptance_sha256")
                or binding.run_id != student.run_id
                or binding.generation != student.generation
                or binding.feature_sha256 != student.extents.factor_map_digest
                or binding.optimizer_step != student.retained_state.optimizer_step
                or binding.candidate_identity_sha256
                != candidate_identity_digest(student.retained_state)
                or binding.step_proof_sha256 != tuple(
                    proof.digest for proof in student.retained_state.step_proofs)):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTANCE_DRIFT")
    support, node = _materialized_support(
        binding, student, manifest_sha256, capability_id)
    return _issue_owner(support, node)


__all__ = ("CapabilitySupportArtifactOwner", "load_capability_support_owner")
