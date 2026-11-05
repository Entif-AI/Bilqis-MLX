"""Pure checks used by the combined context eligibility gate."""
from __future__ import annotations

from .. import context_eligibility as _api


def check_task(frames, task_scope, source_frontier, policy, hold):
    if task_scope.purpose is None or not task_scope.purpose:
        hold("BAMF_CONTEXT_PURPOSE_UNRESOLVED", frames[0].source_handle)
    elif task_scope.purpose not in policy.allowed_purposes:
        hold("BAMF_CONTEXT_PURPOSE_FORBIDDEN", frames[0].source_handle)
    if (task_scope.jurisdiction not in policy.allowed_jurisdictions
            or task_scope.scope not in policy.allowed_scopes):
        hold("BAMF_CONTEXT_SCOPE_FORBIDDEN", frames[0].source_handle)
    if source_frontier.rights_epoch != policy.rights_epoch:
        hold("BAMF_CONTEXT_RIGHTS_EPOCH_MISMATCH", frames[0].source_handle)
    if len({item.frame_handle for item in frames}) != len(frames):
        hold("BAMF_CONTEXT_FRAME_DUPLICATE", frames[0].source_handle)


def check_envelope(item, task_scope, source_frontier, policy, hold):
    handle = item.source_handle
    if (item.semantic_release != task_scope.semantic_release
            or not _api._frame_release_matches(item)):
        hold("BAMF_CONTEXT_RELEASE_MISMATCH", handle)
    if (item.principal_id != task_scope.principal_id
            or item.tenant_id != task_scope.tenant_id
            or item.jurisdiction != task_scope.jurisdiction
            or item.scope != task_scope.scope):
        hold("BAMF_CONTEXT_SCOPE_FORBIDDEN", handle)
    if item.purpose is None or not item.purpose:
        hold("BAMF_CONTEXT_PURPOSE_UNRESOLVED", handle)
    elif item.purpose != task_scope.purpose:
        hold("BAMF_CONTEXT_PURPOSE_FORBIDDEN", handle)
    if item.source_regime not in policy.allowed_regimes:
        hold("BAMF_CONTEXT_SOURCE_REGIME_FORBIDDEN", handle)
    if item.join_class not in policy.allowed_join_classes:
        hold("BAMF_CONTEXT_FORBIDDEN_JOIN", handle)
    if item.policy_epoch != policy.policy_epoch:
        hold("BAMF_CONTEXT_POLICY_EPOCH_MISMATCH", handle)
    if item.rights_epoch != source_frontier.rights_epoch:
        hold("BAMF_CONTEXT_RIGHTS_EPOCH_MISMATCH", handle)
    if item.correction_generation != source_frontier.correction_generation:
        hold("BAMF_CONTEXT_CORRECTION_STALE", handle)
    if (item.observed_at > task_scope.observed_frontier
            or item.effective_from > task_scope.effective_time
            or (item.effective_until is not None
                and task_scope.effective_time >= item.effective_until)):
        hold("BAMF_CONTEXT_TEMPORAL_MISMATCH", handle)
    if (item.frame.source_span.end > task_scope.causal_prefix_end
            or item.frame.causal_prefix_end > task_scope.causal_prefix_end
            or item.causal_prefix_end > task_scope.causal_prefix_end):
        hold("BAMF_CONTEXT_INVISIBLE_PREFIX", handle)


def member_evidence(item, task_scope, hold):
    handle = item.source_handle
    expected = (
        tuple(binding.key for binding in item.frame.bindings)
        if isinstance(item.frame, _api.FrameInstance) else (("<atomic>", 0),)
    )
    if tuple(member.key for member in item.members) != expected:
        hold("BAMF_CONTEXT_MEMBER_MISMATCH", handle)
    expected_evidence = {handle: _api.frame_evidence_digest(item.frame)}
    for member in item.members:
        if member.key in expected:
            if member.source_handle in expected_evidence:
                hold("BAMF_CONTEXT_HANDLE_REUSED", member.source_handle)
            else:
                expected_evidence[member.source_handle] = _api.member_evidence_digest(
                    item.frame, member)
        if member.visible_at_prefix > task_scope.causal_prefix_end:
            hold("BAMF_CONTEXT_INVISIBLE_PREFIX", member.source_handle)
    return expected_evidence


def check_grants(item, task_scope, source_frontier, grants, used_handles, expected_evidence, hold):
    handle = item.source_handle
    for source_handle in (handle, *(member.source_handle for member in item.members)):
        used_handles.add(source_handle)
        grant = grants.get(source_handle)
        if grant is None:
            hold("BAMF_CONTEXT_SOURCE_UNKNOWN", source_handle)
            continue
        if grant.evidence_digest != expected_evidence.get(source_handle):
            hold("BAMF_CONTEXT_EVIDENCE_MISMATCH", source_handle)
        if grant.semantic_release != item.semantic_release:
            hold("BAMF_CONTEXT_RELEASE_MISMATCH", source_handle)
        if grant.revoked:
            hold("BAMF_CONTEXT_SOURCE_REVOKED", source_handle)
        if (grant.principal_id != task_scope.principal_id
                or grant.tenant_id != task_scope.tenant_id
                or task_scope.jurisdiction not in grant.permitted_jurisdictions
                or task_scope.scope not in grant.permitted_scopes):
            hold("BAMF_CONTEXT_SCOPE_FORBIDDEN", source_handle)
        if (task_scope.purpose is None
                or task_scope.purpose not in grant.permitted_purposes):
            hold("BAMF_CONTEXT_PURPOSE_FORBIDDEN", source_handle)
        if grant.source_regime != item.source_regime:
            hold("BAMF_CONTEXT_SOURCE_REGIME_FORBIDDEN", source_handle)
        if grant.rights_epoch != source_frontier.rights_epoch:
            hold("BAMF_CONTEXT_RIGHTS_EPOCH_MISMATCH", source_handle)
        if grant.correction_generation != source_frontier.correction_generation:
            hold("BAMF_CONTEXT_CORRECTION_STALE", source_handle)
        if (grant.observed_at > task_scope.observed_frontier
                or grant.effective_from > task_scope.effective_time
                or (grant.effective_until is not None
                    and task_scope.effective_time >= grant.effective_until)):
            hold("BAMF_CONTEXT_TEMPORAL_MISMATCH", source_handle)


def check_joins(frames, policy, hold):
    join_classes = tuple(sorted({item.join_class for item in frames}))
    if len(frames) > 1:
        for index, left in enumerate(frames):
            for right in frames[index + 1:]:
                pair = tuple(sorted((left.join_class, right.join_class)))
                if pair not in policy.allowed_join_pairs:
                    hold("BAMF_CONTEXT_FORBIDDEN_JOIN", left.source_handle)
                    hold("BAMF_CONTEXT_FORBIDDEN_JOIN", right.source_handle)
    join_multiset = tuple(sorted(item.join_class for item in frames))
    if len(frames) > _api.JOIN_PAIR_ARITY and join_multiset not in policy.allowed_join_sets:
        for item in frames:
            hold("BAMF_CONTEXT_FORBIDDEN_JOIN", item.source_handle)

    return join_classes
