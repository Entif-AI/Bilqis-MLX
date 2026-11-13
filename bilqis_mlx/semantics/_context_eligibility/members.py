"""Context member and source envelope records."""
from __future__ import annotations

from dataclasses import dataclass
import bilqis_mlx.semantics.context_eligibility as _api


@dataclass(frozen=True)
class ContextMember:
    role_id: str
    occurrence_index: int
    source_handle: str
    visible_at_prefix: int
    schema_version: str = _api.MEMBER_SCHEMA

    def __post_init__(self) -> None:
        if (not _api._name(self.role_id) or not _api._epoch(self.occurrence_index)
                or not _api._name(self.source_handle)
                or not _api._epoch(self.visible_at_prefix)
                or self.schema_version != _api.MEMBER_SCHEMA):
            _api._invalid("BAMF_CONTEXT_MEMBER_INVALID")

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
    schema_version: str = _api.ELIGIBILITY_SCHEMA

    def __post_init__(self) -> None:
        if (not _api._name(self.frame_handle)
                or not isinstance(self.frame, (_api.FrameInstance, _api.AtomicFrame))
                or not _api._name(self.source_handle)
                or not isinstance(self.members, tuple)
                or any(not isinstance(item, _api.ContextMember) for item in self.members)
                or not _api._name(self.principal_id) or not _api._name(self.tenant_id)
                or (self.purpose is not None and not isinstance(self.purpose, str))
                or not _api._name(self.source_regime)
                or not isinstance(self.semantic_release, str)
                or not _api._SHA256.fullmatch(self.semantic_release)
                or not all(_api._name(item) for item in (
                    self.jurisdiction, self.scope, self.join_class))
                or not all(_api._epoch(item) for item in (
                    self.policy_epoch, self.rights_epoch,
                    self.correction_generation, self.observed_at,
                    self.effective_from, self.causal_prefix_end))
                or (self.effective_until is not None
                    and (not _api._epoch(self.effective_until)
                         or self.effective_until <= self.effective_from))
                or self.schema_version != _api.ELIGIBILITY_SCHEMA):
            _api._invalid("BAMF_CONTEXT_ELIGIBILITY_INVALID")
