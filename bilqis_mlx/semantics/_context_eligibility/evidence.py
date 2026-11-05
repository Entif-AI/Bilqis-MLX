"""Evidence identities and context boundary validation."""
from __future__ import annotations

from .. import context_eligibility as _api


def _invalid(reason: str) -> None:
    _api.ErrorBus.raise_(
        _api.SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<context>", span_start=0, span_end=0,
    )


def _digest(value: object) -> str:
    return _api.hashlib.sha256(
        (_api.json.dumps(value, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ).hexdigest()


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _epoch(value: object) -> bool:
    return type(value) is int and value >= 0


def _names(value: object) -> bool:
    return (isinstance(value, tuple)
            and all(_api._name(item) for item in value)
            and value == tuple(sorted(set(value))))


def frame_evidence_digest(frame: FrameInstance | AtomicFrame) -> str:
    """Canonical source evidence identity, including lineage and all bindings."""
    if not isinstance(frame, (_api.FrameInstance, _api.AtomicFrame)):
        _api._invalid("BAMF_CONTEXT_FRAME_EVIDENCE_INVALID")
    return _api._digest({"kind": "frame", "frame": _api.asdict(frame)})


def member_evidence_digest(
    frame: FrameInstance | AtomicFrame, member: ContextMember,
) -> str:
    """Bind a member handle to one exact source occurrence and visibility."""
    if not isinstance(frame, (_api.FrameInstance, _api.AtomicFrame)):
        _api._invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
    if not isinstance(member, _api.ContextMember):
        _api._invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
    if isinstance(frame, _api.AtomicFrame):
        if member.key != ("<atomic>", 0):
            _api._invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
        evidence = {"kind": "atomic-member", "frame": _api.asdict(frame)}
    else:
        binding = next(
            (binding for binding in frame.bindings if binding.key == member.key),
            None,
        )
        if binding is None:
            _api._invalid("BAMF_CONTEXT_MEMBER_EVIDENCE_INVALID")
        evidence = {
            "kind": "member",
            "frame_occurrence_id": frame.occurrence_id,
            "binding": _api.asdict(binding),
        }
    return _api._digest({**evidence, "visible_at_prefix": member.visible_at_prefix})


def _envelope_projection(item: ContextEligibility) -> dict:
    """Hash policy-relevant metadata without embedding the source frame."""
    return {
        "frame_handle": item.frame_handle,
        "occurrence_id": item.frame.occurrence_id,
        "content_digest": item.frame.content_digest,
        "source_handle": item.source_handle,
        "members": [_api.asdict(member) for member in item.members],
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
    if isinstance(item.frame, _api.AtomicFrame):
        return True
    for binding in item.frame.bindings:
        concepts = ((binding.concept,) if binding.concept is not None
                    else binding.alternatives)
        if any(concept.semantic_release != item.semantic_release
               for concept in concepts):
            return False
    return True
