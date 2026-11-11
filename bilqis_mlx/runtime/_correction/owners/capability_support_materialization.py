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
from .atlas_revalidation_common import _invalid, owner_priority


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
    immediate_dependencies: tuple[DependencyRef, ...]


def _source_anchor(anchor) -> _SourceAnchor:
    try:
        values = tuple(anchor)
        dependencies = tuple(
            DependencyRef(DependencyKind(kind), key)
            for kind, key in values[9])
        if dependencies != tuple(sorted(set(dependencies))):
            raise ValueError
        return _SourceAnchor(*values[:9], dependencies)
    except (TypeError, ValueError, IndexError):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_SOURCE_INVALID")


def _anchor_dependencies(anchors, policy_sha256, manifest_sha256):
    dependencies = {
        DependencyRef(DependencyKind.POLICY, "retention-policy:" + policy_sha256),
        DependencyRef(DependencyKind.RELEASE, "generation:" + manifest_sha256),
    }
    for anchor in anchors:
        source = _source_anchor(anchor)
        dependencies.update(source.immediate_dependencies)
        dependencies.update((
            DependencyRef(DependencyKind.SOURCE, source.source_row_id),
            DependencyRef(
                DependencyKind.SOURCE,
                "source-row-digest:" + source.source_row_sha256,
            ),
            DependencyRef(
                DependencyKind.SOURCE,
                "training-batch:" + source.training_batch_sha256,
            ),
            DependencyRef(
                DependencyKind.SOURCE,
                "source-proof:" + source.training_authority_sha256,
            ),
            DependencyRef(
                DependencyKind.RELEASE,
                "source-release:" + source.release_sha256,
            ),
            DependencyRef(
                DependencyKind.RELEASE,
                "source-generation:" + source.generation_binding,
            ),
        ))
    return tuple(sorted(dependencies))


def _verify_anchor_proofs(binding, student, capability_id):
    proofs = student.retained_state.step_proofs
    if len(proofs) != len(binding.source_anchors):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_PROOF_DRIFT")
    anchors = []
    for index, (anchor, proof) in enumerate(zip(binding.source_anchors, proofs), 1):
        source = _source_anchor(anchor)
        if (proof.step_index != index
                or proof.training_authority_sha256 != source.training_authority_sha256
                or proof.source_release_sha256 != source.release_sha256
                or proof.training_batch_sha256 != source.training_batch_sha256
                or proof.target_capability_id != source.capability_id
                or proof.source_family_id != source.source_family_id
                or proof.episode_id != source.episode_id):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_PROOF_DRIFT")
        if source.capability_id == capability_id:
            anchors.append(anchor)
    if not anchors:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_SOURCE_MISSING")
    return tuple(anchors)


def materialized_support(binding, student, manifest_sha256, capability_id):
    anchors = _verify_anchor_proofs(binding, student, capability_id)
    dependencies = _anchor_dependencies(
        anchors, binding.policy_sha256, manifest_sha256)
    impact, exigency = owner_priority(ArtifactKind.CAPABILITY_SUPPORT)
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
        impact=impact,
        exigency=exigency,
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


def retained_closure_nodes(binding, student, capability_id):
    """Recover only closures bound to this capability's executed proofs."""
    from bilqis_mlx.learning._retention._atlas_acceptance_records import require_closure_proofs
    from bilqis_mlx.semantics.dependencies.closure import decode_closure_nodes
    require_closure_proofs(binding, student.retained_state.step_proofs)
    proofs = {proof.step_index: proof for proof in student.retained_state.step_proofs}
    nodes = {}
    for entry in getattr(binding, 'artifact_closures', ()) or ():
        proof = proofs[entry['step_index']]
        if proof.target_capability_id != capability_id:
            continue
        for node in decode_closure_nodes(entry['nodes']):
            previous = nodes.get(node.artifact_id)
            if previous is not None and previous != node:
                _invalid('BAMF_C09_CAPABILITY_SUPPORT_CLOSURE_CONFLICT')
            nodes[node.artifact_id] = node
    return tuple(sorted(nodes.values(), key=lambda node: node.artifact_id))
