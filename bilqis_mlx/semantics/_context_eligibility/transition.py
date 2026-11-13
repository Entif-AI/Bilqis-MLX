"""Context transitions and C09 invalidation receipts."""
from __future__ import annotations

from dataclasses import dataclass
import bilqis_mlx.semantics.context_eligibility as _api


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
    source_time: int | None = None
    effective_time: int | None = None
    observed_at: int | None = None
    recorded_at: int | None = None
    temporal_authority_sha256: str | None = None
    schema_version: str = _api.C09_INVALIDATION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.old_context_digest, str)
                or not _api._SHA256.fullmatch(self.old_context_digest)
                or (self.new_context_digest is not None
                    and (not isinstance(self.new_context_digest, str)
                         or not _api._SHA256.fullmatch(self.new_context_digest)
                         or self.new_context_digest == self.old_context_digest))
                or not _api._names(self.reason_codes) or not self.reason_codes
                or not all(_api._name(item) for item in (
                    self.principal_id, self.tenant_id, self.scope))
                or not isinstance(self.semantic_release, str)
                or not _api._SHA256.fullmatch(self.semantic_release)
                or not all(_api._epoch(item) for item in (
                    self.policy_epoch, self.rights_epoch,
                    self.correction_generation, self.causal_prefix_end))
                or not _api._names(self.invalidated_handles)
                or not self.invalidated_handles):
            _api._invalid("BAMF_CONTEXT_C09_INVALIDATION_INVALID")
        temporal = (
            self.source_time, self.effective_time,
            self.observed_at, self.recorded_at,
        )
        legacy = (
            self.schema_version == _api.C09_INVALIDATION_SCHEMA_V1
            and temporal == (None, None, None, None)
            and self.temporal_authority_sha256 is None
        )
        current = (
            self.schema_version == _api.C09_INVALIDATION_SCHEMA_V2
            and all(_api._epoch(item) for item in temporal)
            and self.source_time <= self.observed_at <= self.recorded_at
            and isinstance(self.temporal_authority_sha256, str)
            and _api._SHA256.fullmatch(self.temporal_authority_sha256)
        )
        if not (legacy or current):
            _api._invalid("BAMF_CONTEXT_C09_INVALIDATION_INVALID")

    @property
    def event_id(self) -> str:
        if self.schema_version == _api.C09_INVALIDATION_SCHEMA_V1:
            return _api.contract_digest({
                "old_context_digest": self.old_context_digest,
                "new_context_digest": self.new_context_digest,
                "reason_codes": self.reason_codes,
                "principal_id": self.principal_id,
                "tenant_id": self.tenant_id,
                "scope": self.scope,
                "semantic_release": self.semantic_release,
                "policy_epoch": self.policy_epoch,
                "rights_epoch": self.rights_epoch,
                "correction_generation": self.correction_generation,
                "causal_prefix_end": self.causal_prefix_end,
                "invalidated_handles": self.invalidated_handles,
                "schema_version": self.schema_version,
            })
        return _api.contract_digest(self)


@dataclass(frozen=True)
class ContextTransition:
    current: ApprovedContextProjection | ContextHold
    invalidations: tuple[C09ContextInvalidation, ...]
    schema_version: str = _api.CONTEXT_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.current, (_api.ApprovedContextProjection, _api.ContextHold))
                or not isinstance(self.invalidations, tuple)
                or any(not isinstance(item, _api.C09ContextInvalidation)
                       for item in self.invalidations)
                or tuple(item.event_id for item in self.invalidations)
                != tuple(sorted({item.event_id for item in self.invalidations}))
                or any(
                    item.new_context_digest != (
                        self.current.digest
                        if isinstance(self.current, _api.ApprovedContextProjection)
                        else None)
                    for item in self.invalidations)
                or self.schema_version != _api.CONTEXT_TRANSITION_SCHEMA):
            _api._invalid("BAMF_CONTEXT_TRANSITION_INVALID")


def transition_context(
    previous: ApprovedContextProjection | None,
    frames: tuple[ContextEligibility, ...],
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
    *,
    temporal_identity: dict | None = None,
) -> ContextTransition:
    """Compare pinned frontiers and emit C09 on loss/change of eligibility.

    This is a pure local transition. It never calls a policy service or
    mutates a learner, cache, source owner, outbox or external graph.
    """
    current = _api.project_context(
        frames, task_scope, source_frontier, policy)
    if previous is None:
        return _api.ContextTransition(current, ())
    if not isinstance(previous, _api.ApprovedContextProjection):
        _api._invalid("BAMF_CONTEXT_TRANSITION_PRIOR_INVALID")
    if any(
        envelope.principal_id != task_scope.principal_id
        or envelope.tenant_id != task_scope.tenant_id
        or envelope.purpose != task_scope.purpose
        or envelope.jurisdiction != task_scope.jurisdiction
        or envelope.semantic_release != task_scope.semantic_release
        or envelope.scope != task_scope.scope
        for envelope in previous.envelopes
    ):
        _api._invalid("BAMF_CONTEXT_TRANSITION_ACTOR_SCOPE_DRIFT")
    prior = previous.eligible
    new_digest = (
        current.digest if isinstance(current, _api.ApprovedContextProjection)
        else None)
    if prior.digest == new_digest:
        return _api.ContextTransition(current, ())
    reason_codes = (
        current.reason_codes if isinstance(current, _api.ContextHold)
        else ("BAMF_CONTEXT_APPROVED_VIEW_CHANGED",))
    temporal_fields = {}
    if temporal_identity is not None:
        expected = {
            "source_time", "effective_time", "observed_at", "recorded_at",
            "temporal_authority_sha256",
        }
        if (type(temporal_identity) is not dict
                or set(temporal_identity) != expected):
            _api._invalid("BAMF_CONTEXT_C09_TEMPORAL_IDENTITY_INVALID")
        temporal_fields = {
            **temporal_identity,
            "schema_version": _api.C09_INVALIDATION_SCHEMA_V2,
        }
    invalidation = _api.C09ContextInvalidation(
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
        **temporal_fields,
    )
    return _api.ContextTransition(current, (invalidation,))
