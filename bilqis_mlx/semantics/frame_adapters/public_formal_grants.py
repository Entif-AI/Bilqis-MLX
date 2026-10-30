"""Create collision-checked grants for already verified source frame trees."""
from ...generated_assessment import digest
from ..context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextHold, ContextMember, SourceFrontier,
    SourceGrant, frame_evidence_digest, member_evidence_digest, project_context,
)
from ..frame_schema import FrameInstance
from .common import PUBLIC_FORMAL_TIMELESS_EPOCH, _adapter_fail


def _walk(node):
    yield node.root
    for child in node.children:
        yield from _walk(child)


def _envelope(frame, prefix, task, frontier, policy):
    members = (
        tuple(ContextMember(
            binding.role_id, binding.occurrence_index,
            prefix + ":member:" + binding.role_id + ":" + str(binding.occurrence_index),
            frame.causal_prefix_end) for binding in frame.bindings)
        if isinstance(frame, FrameInstance)
        else (ContextMember("<atomic>", 0, prefix + ":member:<atomic>:0", frame.causal_prefix_end),))
    return ContextEligibility(
        frame_handle=prefix + ":frame", frame=frame,
        source_handle=prefix + ":source", members=members,
        principal_id=task.principal_id, tenant_id=task.tenant_id,
        purpose=task.purpose, source_regime=PUBLIC_FORMAL,
        semantic_release=task.semantic_release,
        jurisdiction=task.jurisdiction, scope=task.scope,
        join_class=PUBLIC_FORMAL, policy_epoch=policy.policy_epoch,
        rights_epoch=frontier.rights_epoch, correction_generation=frontier.correction_generation,
        observed_at=PUBLIC_FORMAL_TIMELESS_EPOCH,
        effective_from=PUBLIC_FORMAL_TIMELESS_EPOCH, effective_until=None,
        causal_prefix_end=frame.causal_prefix_end)


def admit_tree(tree, row, source_adapter_id, task, source_frontier, policy, source_span):
    envelopes = []
    grants = {item.source_handle: item for item in source_frontier.grants}
    visible_digest = digest({
        "source_id": row.get("source_id") or row.get("id"),
        "record": row.get("record"), "tokens": row.get("tokens")})
    for frame in _walk(tree):
        prefix = "public-formal:" + source_adapter_id + ":" + visible_digest + ":" + frame.occurrence_id
        envelope = _envelope(frame, prefix, task, source_frontier, policy)
        evidence = {envelope.source_handle: frame_evidence_digest(frame)}
        evidence.update({member.source_handle: member_evidence_digest(frame, member)
                         for member in envelope.members})
        for handle, evidence_sha in evidence.items():
            grant = SourceGrant(
                handle, task.principal_id, task.tenant_id, PUBLIC_FORMAL,
                task.semantic_release, evidence_sha,
                (task.purpose,), (task.jurisdiction,), (task.scope,),
                source_frontier.rights_epoch, source_frontier.correction_generation,
                PUBLIC_FORMAL_TIMELESS_EPOCH, PUBLIC_FORMAL_TIMELESS_EPOCH)
            prior = grants.get(handle)
            if prior is not None and prior != grant:
                _adapter_fail("BAMF_CONTEXT_PUBLIC_FORMAL_GRANT_COLLISION",
                              source_adapter_id, source_span, "<public-formal>")
            grants[handle] = grant
        envelopes.append(envelope)
    frontier = SourceFrontier(
        source_frontier.rights_epoch, source_frontier.correction_generation,
        tuple(sorted(grants.values(), key=lambda grant: grant.source_handle)))
    projected = project_context(tuple(envelopes), task, frontier, policy)
    return projected if isinstance(projected, ContextHold) else (projected, frontier)
