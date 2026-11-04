"""Source, task and policy authority records for context admission."""
from __future__ import annotations

from dataclasses import dataclass

from .._frame_schema.instances import AtomicFrame, FrameInstance
from .common import (
    ELIGIBILITY_SCHEMA, MEMBER_SCHEMA, GRANT_SCHEMA, FRONTIER_SCHEMA, TASK_SCHEMA,
    POLICY_SCHEMA, PUBLIC_FORMAL, JOIN_PAIR_ARITY, MIN_JOIN_SET_ARITY, _SHA256,
    _epoch, _invalid, _name, _names,
)

@dataclass(frozen=True)
class ContextMember:
    role_id: str
    occurrence_index: int
    source_handle: str
    visible_at_prefix: int
    schema_version: str = MEMBER_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.role_id) or not _epoch(self.occurrence_index)
                or not _name(self.source_handle)
                or not _epoch(self.visible_at_prefix)
                or self.schema_version != MEMBER_SCHEMA):
            _invalid("BAMF_CONTEXT_MEMBER_INVALID")

    @property
    def key(self) -> tuple[str, int]:
        return self.role_id, self.occurrence_index


@dataclass(frozen=True)
class ContextEligibility:
    frame_handle: str
    frame: FrameInstance | AtomicFrame
    source_handle: str
    members: tuple[ContextMember, ...]
    principal_id: str
    tenant_id: str
    purpose: str | None
    source_regime: str
    semantic_release: str
    jurisdiction: str
    scope: str
    join_class: str
    policy_epoch: int
    rights_epoch: int
    correction_generation: int
    observed_at: int
    effective_from: int
    effective_until: int | None
    causal_prefix_end: int
    schema_version: str = ELIGIBILITY_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.frame_handle)
                or not isinstance(self.frame, (FrameInstance, AtomicFrame))
                or not _name(self.source_handle)
                or not isinstance(self.members, tuple)
                or any(not isinstance(item, ContextMember) for item in self.members)
                or not _name(self.principal_id) or not _name(self.tenant_id)
                or (self.purpose is not None and not isinstance(self.purpose, str))
                or not _name(self.source_regime)
                or not isinstance(self.semantic_release, str)
                or not _SHA256.fullmatch(self.semantic_release)
                or not all(_name(item) for item in (
                    self.jurisdiction, self.scope, self.join_class))
                or not all(_epoch(item) for item in (
                    self.policy_epoch, self.rights_epoch,
                    self.correction_generation, self.observed_at,
                    self.effective_from, self.causal_prefix_end))
                or (self.effective_until is not None
                    and (not _epoch(self.effective_until)
                         or self.effective_until <= self.effective_from))
                or self.schema_version != ELIGIBILITY_SCHEMA):
            _invalid("BAMF_CONTEXT_ELIGIBILITY_INVALID")


@dataclass(frozen=True)
class SourceGrant:
    source_handle: str
    principal_id: str
    tenant_id: str
    source_regime: str
    semantic_release: str
    evidence_digest: str
    permitted_purposes: tuple[str, ...]
    permitted_jurisdictions: tuple[str, ...]
    permitted_scopes: tuple[str, ...]
    rights_epoch: int
    correction_generation: int
    observed_at: int
    effective_from: int
    effective_until: int | None = None
    revoked: bool = False
    schema_version: str = GRANT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.source_handle, self.principal_id,
                    self.tenant_id, self.source_regime))
                or not all(_names(item) and bool(item) for item in (
                    self.permitted_purposes, self.permitted_jurisdictions,
                    self.permitted_scopes))
                or not all(isinstance(item, str) and _SHA256.fullmatch(item)
                           for item in (self.semantic_release, self.evidence_digest))
                or not all(_epoch(item) for item in (
                    self.rights_epoch, self.correction_generation,
                    self.observed_at, self.effective_from))
                or (self.effective_until is not None
                    and (not _epoch(self.effective_until)
                         or self.effective_until <= self.effective_from))
                or type(self.revoked) is not bool
                or self.schema_version != GRANT_SCHEMA):
            _invalid("BAMF_CONTEXT_SOURCE_GRANT_INVALID")


@dataclass(frozen=True)
class SourceFrontier:
    rights_epoch: int
    correction_generation: int
    grants: tuple[SourceGrant, ...]
    schema_version: str = FRONTIER_SCHEMA

    def __post_init__(self) -> None:
        if (not _epoch(self.rights_epoch)
                or not _epoch(self.correction_generation)
                or not isinstance(self.grants, tuple)
                or any(not isinstance(item, SourceGrant) for item in self.grants)
                or tuple(item.source_handle for item in self.grants)
                != tuple(sorted({item.source_handle for item in self.grants}))
                or self.schema_version != FRONTIER_SCHEMA):
            _invalid("BAMF_CONTEXT_SOURCE_FRONTIER_INVALID")


@dataclass(frozen=True)
class TaskScope:
    principal_id: str
    tenant_id: str
    purpose: str | None
    semantic_release: str
    jurisdiction: str
    scope: str
    observed_frontier: int
    effective_time: int
    causal_prefix_end: int
    schema_version: str = TASK_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.principal_id, self.tenant_id,
                    self.jurisdiction, self.scope))
                or (self.purpose is not None and not isinstance(self.purpose, str))
                or not isinstance(self.semantic_release, str)
                or not _SHA256.fullmatch(self.semantic_release)
                or not all(_epoch(item) for item in (
                    self.observed_frontier, self.effective_time,
                    self.causal_prefix_end))
                or self.schema_version != TASK_SCHEMA):
            _invalid("BAMF_CONTEXT_TASK_INVALID")


@dataclass(frozen=True)
class ContextPolicy:
    policy_id: str
    policy_epoch: int
    rights_epoch: int
    allowed_purposes: tuple[str, ...]
    allowed_regimes: tuple[str, ...]
    allowed_jurisdictions: tuple[str, ...]
    allowed_scopes: tuple[str, ...]
    allowed_join_classes: tuple[str, ...]
    allowed_join_pairs: tuple[tuple[str, str], ...]
    allowed_join_sets: tuple[tuple[str, ...], ...]
    schema_version: str = POLICY_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.policy_id)
                or not _epoch(self.policy_epoch) or not _epoch(self.rights_epoch)
                or not all(_names(item) for item in (
                    self.allowed_purposes, self.allowed_regimes,
                    self.allowed_jurisdictions, self.allowed_scopes,
                    self.allowed_join_classes))
                or not isinstance(self.allowed_join_pairs, tuple)
                or any(not isinstance(item, tuple) or len(item) != JOIN_PAIR_ARITY
                       or not all(_name(value) for value in item)
                       or item != tuple(sorted(item))
                       for item in self.allowed_join_pairs)
                or self.allowed_join_pairs != tuple(sorted(set(self.allowed_join_pairs)))
                or not isinstance(self.allowed_join_sets, tuple)
                or any(not isinstance(item, tuple) or len(item) < MIN_JOIN_SET_ARITY
                       or not all(_name(value) for value in item)
                       or item != tuple(sorted(item))
                       for item in self.allowed_join_sets)
                or self.allowed_join_sets != tuple(sorted(set(self.allowed_join_sets)))
                or self.schema_version != POLICY_SCHEMA):
            _invalid("BAMF_CONTEXT_POLICY_INVALID")
