"""C09 local context invalidation and transition receipts."""
from __future__ import annotations

from dataclasses import dataclass

from ..foundation.domains import contract_digest
from .authority import ContextEligibility, ContextPolicy, SourceFrontier, TaskScope
from .common import (C09_INVALIDATION_SCHEMA, CONTEXT_TRANSITION_SCHEMA, _SHA256,
                     _epoch, _invalid, _name, _names)
from .projection import ApprovedContextProjection, project_context
from .results import ContextHold

@dataclass(frozen=True)
class C09ContextInvalidation:
    """Local invalidation receipt; downstream C09 owns durable outbox delivery."""
    old_context_digest: str
    new_context_digest: str | None
    reason_codes: tuple[str, ...]
    principal_id: str
    tenant_id: str
    scope: str
    semantic_release: str
    policy_epoch: int
    rights_epoch: int
    correction_generation: int
    causal_prefix_end: int
    invalidated_handles: tuple[str, ...]
    schema_version: str = C09_INVALIDATION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.old_context_digest, str)
                or not _SHA256.fullmatch(self.old_context_digest)
                or (self.new_context_digest is not None
                    and (not isinstance(self.new_context_digest, str)
                         or not _SHA256.fullmatch(self.new_context_digest)
                         or self.new_context_digest == self.old_context_digest))
                or not _names(self.reason_codes) or not self.reason_codes
                or not all(_name(item) for item in (
                    self.principal_id, self.tenant_id, self.scope))
                or not isinstance(self.semantic_release, str)
                or not _SHA256.fullmatch(self.semantic_release)
                or not all(_epoch(item) for item in (
                    self.policy_epoch, self.rights_epoch,
                    self.correction_generation, self.causal_prefix_end))
                or not _names(self.invalidated_handles)
                or not self.invalidated_handles
                or self.schema_version != C09_INVALIDATION_SCHEMA):
            _invalid("BAMF_CONTEXT_C09_INVALIDATION_INVALID")

    @property
    def event_id(self) -> str:
        return contract_digest(self)


@dataclass(frozen=True)
class ContextTransition:
    current: ApprovedContextProjection | ContextHold
    invalidations: tuple[C09ContextInvalidation, ...]
    schema_version: str = CONTEXT_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.current, (ApprovedContextProjection, ContextHold))
                or not isinstance(self.invalidations, tuple)
                or any(not isinstance(item, C09ContextInvalidation)
                       for item in self.invalidations)
                or tuple(item.event_id for item in self.invalidations)
                != tuple(sorted({item.event_id for item in self.invalidations}))
                or any(
                    item.new_context_digest != (
                        self.current.digest
                        if isinstance(self.current, ApprovedContextProjection)
                        else None)
                    for item in self.invalidations)
                or self.schema_version != CONTEXT_TRANSITION_SCHEMA):
            _invalid("BAMF_CONTEXT_TRANSITION_INVALID")

def transition_context(
    previous: ApprovedContextProjection | None,
    frames: tuple[ContextEligibility, ...],
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
) -> ContextTransition:
    """Compare pinned frontiers and emit C09 on loss/change of eligibility.

    This is a pure local transition. It never calls a policy service or
    mutates a learner, cache, source owner, outbox or external graph.
    """
    current = project_context(
        frames, task_scope, source_frontier, policy)
    if previous is None:
        return ContextTransition(current, ())
    if not isinstance(previous, ApprovedContextProjection):
        _invalid("BAMF_CONTEXT_TRANSITION_PRIOR_INVALID")
    if any(
        envelope.principal_id != task_scope.principal_id
        or envelope.tenant_id != task_scope.tenant_id
        or envelope.purpose != task_scope.purpose
        or envelope.jurisdiction != task_scope.jurisdiction
        or envelope.semantic_release != task_scope.semantic_release
        or envelope.scope != task_scope.scope
        for envelope in previous.envelopes
    ):
        _invalid("BAMF_CONTEXT_TRANSITION_ACTOR_SCOPE_DRIFT")
    prior = previous.eligible
    new_digest = (
        current.digest if isinstance(current, ApprovedContextProjection)
        else None)
    if prior.digest == new_digest:
        return ContextTransition(current, ())
    reason_codes = (
        current.reason_codes if isinstance(current, ContextHold)
        else ("BAMF_CONTEXT_APPROVED_VIEW_CHANGED",))
    invalidation = C09ContextInvalidation(
        old_context_digest=prior.digest,
        new_context_digest=new_digest,
        reason_codes=tuple(sorted(set(reason_codes))),
        principal_id=task_scope.principal_id,
        tenant_id=task_scope.tenant_id,
        scope=task_scope.scope,
        semantic_release=task_scope.semantic_release,
        policy_epoch=policy.policy_epoch,
        rights_epoch=source_frontier.rights_epoch,
        correction_generation=source_frontier.correction_generation,
        causal_prefix_end=task_scope.causal_prefix_end,
        invalidated_handles=tuple(sorted({
            handle for frame in prior.frames
            for handle in (frame.frame_handle, *frame.member_handles)
        })),
    )
    return ContextTransition(current, (invalidation,))
