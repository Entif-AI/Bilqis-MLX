"""Source grants, frontiers, and task scope records."""
from __future__ import annotations

from dataclasses import dataclass
from .. import context_eligibility as _api


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
    schema_version: str = _api.GRANT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_api._name(item) for item in (
                    self.source_handle, self.principal_id,
                    self.tenant_id, self.source_regime))
                or not all(_api._names(item) and bool(item) for item in (
                    self.permitted_purposes, self.permitted_jurisdictions,
                    self.permitted_scopes))
                or not all(isinstance(item, str) and _api._SHA256.fullmatch(item)
                           for item in (self.semantic_release, self.evidence_digest))
                or not all(_api._epoch(item) for item in (
                    self.rights_epoch, self.correction_generation,
                    self.observed_at, self.effective_from))
                or (self.effective_until is not None
                    and (not _api._epoch(self.effective_until)
                         or self.effective_until <= self.effective_from))
                or type(self.revoked) is not bool
                or self.schema_version != _api.GRANT_SCHEMA):
            _api._invalid("BAMF_CONTEXT_SOURCE_GRANT_INVALID")


@dataclass(frozen=True)
class SourceFrontier:
    rights_epoch: int
    correction_generation: int
    grants: tuple[SourceGrant, ...]
    schema_version: str = _api.FRONTIER_SCHEMA

    def __post_init__(self) -> None:
        if (not _api._epoch(self.rights_epoch)
                or not _api._epoch(self.correction_generation)
                or not isinstance(self.grants, tuple)
                or any(not isinstance(item, _api.SourceGrant) for item in self.grants)
                or tuple(item.source_handle for item in self.grants)
                != tuple(sorted({item.source_handle for item in self.grants}))
                or self.schema_version != _api.FRONTIER_SCHEMA):
            _api._invalid("BAMF_CONTEXT_SOURCE_FRONTIER_INVALID")


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
    schema_version: str = _api.TASK_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_api._name(item) for item in (
                    self.principal_id, self.tenant_id,
                    self.jurisdiction, self.scope))
                or (self.purpose is not None and not isinstance(self.purpose, str))
                or not isinstance(self.semantic_release, str)
                or not _api._SHA256.fullmatch(self.semantic_release)
                or not all(_api._epoch(item) for item in (
                    self.observed_frontier, self.effective_time,
                    self.causal_prefix_end))
                or self.schema_version != _api.TASK_SCHEMA):
            _api._invalid("BAMF_CONTEXT_TASK_INVALID")
