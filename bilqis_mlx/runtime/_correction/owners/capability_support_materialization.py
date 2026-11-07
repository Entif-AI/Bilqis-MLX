"""Accepted-source provenance materialization for C09 capability support."""
from __future__ import annotations

from typing import NamedTuple

from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.domains import contract_digest

from .atlas_requalification_contracts import (
    CapabilitySupport, RequalificationStatus,
)
from .atlas_revalidation_common import _invalid


class _SourceAnchor(NamedTuple):
    capability_id: str
    source_row_id: str
    source_row_sha256: str
    source_family_id: str
    episode_id: str
    release_sha256: str
    training_batch_sha256: str
    generation_binding: str
    training_authority_sha256: str


def _source_anchor(anchor) -> _SourceAnchor:
    try:
        return _SourceAnchor(*anchor)
    except (TypeError, ValueError):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_SOURCE_INVALID")


def _anchor_dependencies(anchors, policy_sha256, manifest_sha256):
    dependencies = {
        DependencyRef(DependencyKind.POLICY, "retention-policy:" + policy_sha256),
        DependencyRef(DependencyKind.RELEASE, "generation:" + manifest_sha256),
    }
    for anchor in anchors:
        source = _source_anchor(anchor)
        dependencies.update((
            DependencyRef(DependencyKind.SOURCE, source.source_row_id),
            DependencyRef(
                DependencyKind.RELEASE,
                "source-release:" + source.release_sha256,
            ),
        ))
    return tuple(sorted(dependencies))


def _verify_anchor_proofs(binding, student, capability_id):
    anchors = tuple(anchor for anchor in binding.source_anchors
                    if _source_anchor(anchor).capability_id == capability_id)
    if not anchors:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_SOURCE_MISSING")
    proofs = {proof.training_authority_sha256: proof
              for proof in student.retained_state.step_proofs}
    if None in proofs or len(proofs) != len(student.retained_state.step_proofs):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_PROOF_DRIFT")
    for anchor in anchors:
        source = _source_anchor(anchor)
        proof = proofs.get(source.training_authority_sha256)
        if (proof is None
                or proof.source_release_sha256 != source.release_sha256
                or proof.training_batch_sha256 != source.training_batch_sha256
                or proof.target_capability_id != source.capability_id
                or proof.source_family_id != source.source_family_id
                or proof.episode_id != source.episode_id):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_PROOF_DRIFT")
    return anchors


def materialized_support(binding, student, manifest_sha256, capability_id):
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
        source_anchor_ids=tuple(sorted({
            _source_anchor(anchor).source_row_id for anchor in anchors
        })),
        retained_generation_sha256=manifest_sha256,
        observation_ids=tuple(sorted((
            "acceptance:" + binding.digest,
            "decision:" + binding.decision_sha256,
            "evidence:" + binding.evidence_sha256,
        ))),
        status=RequalificationStatus.QUALIFIED,
    )
    generation_bindings = tuple(sorted({
        _source_anchor(anchor).generation_binding for anchor in anchors
    }))
    if len(generation_bindings) != 1:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_GENERATION_AMBIGUOUS")
    return support, node, generation_bindings

