"""Canonical context evidence and envelope projections."""
from __future__ import annotations

from dataclasses import asdict

from .._frame_schema.instances import AtomicFrame, FrameInstance
from .authority import ContextEligibility, ContextMember
from .common import _digest, _invalid

def frame_evidence_digest(frame: FrameInstance | AtomicFrame) -> str:
    """Canonical source evidence identity, including lineage and all bindings."""
    if not isinstance(frame, (FrameInstance, AtomicFrame)):
        _invalid("BAMF_CONTEXT_FRAME_EVIDENCE_INVALID")
    return _digest({"kind": "frame", "frame": asdict(frame)})


def member_evidence_digest(
    frame: FrameInstance | AtomicFrame, member: ContextMember,
) -> str:
    """Bind a member handle to one exact source occurrence and visibility."""
    if not isinstance(frame, (FrameInstance, AtomicFrame)):
        _invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
    if not isinstance(member, ContextMember):
        _invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
    if isinstance(frame, AtomicFrame):
        if member.key != ("<atomic>", 0):
            _invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
        evidence = {"kind": "atomic-member", "frame": asdict(frame)}
    else:
        binding = next(
            (binding for binding in frame.bindings if binding.key == member.key),
            None,
        )
        if binding is None:
            _invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
        evidence = {
            "kind": "member",
            "frame_occurrence_id": frame.occurrence_id,
            "binding": asdict(binding),
        }
    return _digest({**evidence, "visible_at_prefix": member.visible_at_prefix})

def _envelope_projection(item: ContextEligibility) -> dict:
    """Hash policy-relevant metadata without embedding the source frame."""
    return {
        "frame_handle": item.frame_handle,
        "occurrence_id": item.frame.occurrence_id,
        "content_digest": item.frame.content_digest,
        "source_handle": item.source_handle,
        "members": [asdict(member) for member in item.members],
        "principal_id": item.principal_id,
        "tenant_id": item.tenant_id,
        "purpose": item.purpose,
        "source_regime": item.source_regime,
        "semantic_release": item.semantic_release,
        "jurisdiction": item.jurisdiction,
        "scope": item.scope,
        "join_class": item.join_class,
        "policy_epoch": item.policy_epoch,
        "rights_epoch": item.rights_epoch,
        "correction_generation": item.correction_generation,
        "observed_at": item.observed_at,
        "effective_from": item.effective_from,
        "effective_until": item.effective_until,
        "causal_prefix_end": item.causal_prefix_end,
        "schema_version": item.schema_version,
    }


def _frame_release_matches(item: ContextEligibility) -> bool:
    if item.semantic_release == "":
        return False
    if isinstance(item.frame, AtomicFrame):
        return True
    for binding in item.frame.bindings:
        concepts = ((binding.concept,) if binding.concept is not None
                    else binding.alternatives)
        if any(concept.semantic_release != item.semantic_release
               for concept in concepts):
            return False
    return True
