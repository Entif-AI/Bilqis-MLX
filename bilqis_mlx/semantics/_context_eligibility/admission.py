"""Whole-context source, rights, temporal and join admission."""
from __future__ import annotations

from dataclasses import asdict

from .._frame_schema.instances import FrameInstance
from .authority import ContextEligibility, ContextPolicy, SourceFrontier, TaskScope
from .common import (ELIGIBLE_CONTEXT_SCHEMA, JOIN_PAIR_ARITY,
                     MAX_CONTEXT_HOLD_DIAGNOSTICS, _digest, _invalid)
from .evidence import (_envelope_projection, _frame_release_matches,
                       frame_evidence_digest, member_evidence_digest)
from .results import ApprovedFrame, ContextHold, EligibleContext

def check_context_eligibility(
    frames: tuple[ContextEligibility, ...],
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
) -> EligibleContext | ContextHold:
    """Admit the whole proposed context, or return handles-only hold reasons.

    Individual grants are necessary but insufficient. Every pair and the
    entire multi-frame join must be explicitly permitted before a handle is
    exposed to a solver, cache, neural position or motif reader.
    """
    if (not isinstance(frames, tuple)
            or any(not isinstance(item, ContextEligibility) for item in frames)
            or not isinstance(task_scope, TaskScope)
            or not isinstance(source_frontier, SourceFrontier)
            or not isinstance(policy, ContextPolicy)):
        _invalid("BAMF_CONTEXT_ARGUMENT_INVALID")

    if not frames:
        return ContextHold(("BAMF_CONTEXT_EMPTY",), (), ())

    reasons: set[str] = set()
    blocked: set[str] = set()
    diagnostics: set[tuple[str, str]] = set()

    def hold(reason: str, handle: str) -> None:
        reasons.add(reason)
        blocked.add(handle)
        diagnostics.add((reason, handle))

    grants = {grant.source_handle: grant for grant in source_frontier.grants}
    used_handles: set[str] = set()
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

    for item in frames:
        handle = item.source_handle
        if (item.semantic_release != task_scope.semantic_release
                or not _frame_release_matches(item)):
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

        expected = (
            tuple(binding.key for binding in item.frame.bindings)
            if isinstance(item.frame, FrameInstance) else (("<atomic>", 0),)
        )
        if tuple(member.key for member in item.members) != expected:
            hold("BAMF_CONTEXT_MEMBER_MISMATCH", handle)
        expected_evidence = {handle: frame_evidence_digest(item.frame)}
        for member in item.members:
            if member.key in expected:
                if member.source_handle in expected_evidence:
                    hold("BAMF_CONTEXT_HANDLE_REUSED", member.source_handle)
                else:
                    expected_evidence[member.source_handle] = member_evidence_digest(
                        item.frame, member)
            if member.visible_at_prefix > task_scope.causal_prefix_end:
                hold("BAMF_CONTEXT_INVISIBLE_PREFIX", member.source_handle)
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

    join_classes = tuple(sorted({item.join_class for item in frames}))
    if len(frames) > 1:
        for index, left in enumerate(frames):
            for right in frames[index + 1:]:
                pair = tuple(sorted((left.join_class, right.join_class)))
                if pair not in policy.allowed_join_pairs:
                    hold("BAMF_CONTEXT_FORBIDDEN_JOIN", left.source_handle)
                    hold("BAMF_CONTEXT_FORBIDDEN_JOIN", right.source_handle)
    join_multiset = tuple(sorted(item.join_class for item in frames))
    if len(frames) > JOIN_PAIR_ARITY and join_multiset not in policy.allowed_join_sets:
        for item in frames:
            hold("BAMF_CONTEXT_FORBIDDEN_JOIN", item.source_handle)

    if reasons:
        return ContextHold(
            reason_codes=tuple(sorted(reasons)),
            source_handles=tuple(sorted(blocked)),
            diagnostics=tuple(sorted(diagnostics))[:MAX_CONTEXT_HOLD_DIAGNOSTICS],
        )

    approved = tuple(sorted((
        ApprovedFrame(
            frame_handle=item.frame_handle,
            source_handle=item.source_handle,
            member_handles=tuple(member.source_handle for member in item.members),
            occurrence_id=item.frame.occurrence_id,
            content_digest=item.frame.content_digest,
            join_class=item.join_class,
            envelope_digest=_digest(_envelope_projection(item)),
        )
        for item in frames
    ), key=lambda item: item.frame_handle))
    return EligibleContext(
        frames=approved,
        allowed_join_classes=join_classes,
        digest=_digest({
            "schema_version": ELIGIBLE_CONTEXT_SCHEMA,
            "task": asdict(task_scope),
            "policy": asdict(policy),
            "source_frontier": {
                "schema_version": source_frontier.schema_version,
                "rights_epoch": source_frontier.rights_epoch,
                "correction_generation": source_frontier.correction_generation,
                "grants": [
                    asdict(grants[handle]) for handle in sorted(used_handles)
                ],
            },
            "approved": [asdict(item) for item in approved],
            "allowed_join_classes": join_classes,
        }),
    )
