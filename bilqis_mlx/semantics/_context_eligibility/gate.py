"""Combined source-bound context eligibility gate."""
from __future__ import annotations

from .. import context_eligibility as _api
from .checks import check_envelope, check_grants, check_joins, check_task, member_evidence


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
            or any(not isinstance(item, _api.ContextEligibility) for item in frames)
            or not isinstance(task_scope, _api.TaskScope)
            or not isinstance(source_frontier, _api.SourceFrontier)
            or not isinstance(policy, _api.ContextPolicy)):
        _api._invalid("BAMF_CONTEXT_ARGUMENT_INVALID")

    if not frames:
        return _api.ContextHold(("BAMF_CONTEXT_EMPTY",), (), ())

    reasons: set[str] = set()
    blocked: set[str] = set()
    diagnostics: set[tuple[str, str]] = set()

    def hold(reason: str, handle: str) -> None:
        reasons.add(reason)
        blocked.add(handle)
        diagnostics.add((reason, handle))

    grants = {grant.source_handle: grant for grant in source_frontier.grants}
    used_handles: set[str] = set()
    check_task(frames, task_scope, source_frontier, policy, hold)
    for item in frames:
        check_envelope(item, task_scope, source_frontier, policy, hold)
        expected_evidence = member_evidence(item, task_scope, hold)
        check_grants(
            item, task_scope, source_frontier, grants, used_handles,
            expected_evidence, hold)
    join_classes = check_joins(frames, policy, hold)

    if reasons:
        return _api.ContextHold(
            reason_codes=tuple(sorted(reasons)),
            source_handles=tuple(sorted(blocked)),
            diagnostics=tuple(sorted(diagnostics))[:_api.MAX_CONTEXT_HOLD_DIAGNOSTICS],
        )

    approved = tuple(sorted((
        _api.ApprovedFrame(
            frame_handle=item.frame_handle,
            source_handle=item.source_handle,
            member_handles=tuple(member.source_handle for member in item.members),
            occurrence_id=item.frame.occurrence_id,
            content_digest=item.frame.content_digest,
            join_class=item.join_class,
            envelope_digest=_api._digest(_api._envelope_projection(item)),
        )
        for item in frames
    ), key=lambda item: item.frame_handle))
    return _api.EligibleContext(
        frames=approved,
        allowed_join_classes=join_classes,
        digest=_api._digest({
            "schema_version": _api.ELIGIBLE_CONTEXT_SCHEMA,
            "task": _api.asdict(task_scope),
            "policy": _api.asdict(policy),
            "source_frontier": {
                "schema_version": source_frontier.schema_version,
                "rights_epoch": source_frontier.rights_epoch,
                "correction_generation": source_frontier.correction_generation,
                "grants": [
                    _api.asdict(grants[handle]) for handle in sorted(used_handles)
                ],
            },
            "approved": [_api.asdict(item) for item in approved],
            "allowed_join_classes": join_classes,
        }),
    )
