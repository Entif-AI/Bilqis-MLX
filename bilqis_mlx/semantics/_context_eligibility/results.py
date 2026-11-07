"""Context policy, approvals, and hold records."""
from __future__ import annotations

from dataclasses import dataclass
import bilqis_mlx.semantics.context_eligibility as _api


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
    schema_version: str = _api.POLICY_SCHEMA

    def __post_init__(self) -> None:
        if (not _api._name(self.policy_id)
                or not _api._epoch(self.policy_epoch) or not _api._epoch(self.rights_epoch)
                or not all(_api._names(item) for item in (
                    self.allowed_purposes, self.allowed_regimes,
                    self.allowed_jurisdictions, self.allowed_scopes,
                    self.allowed_join_classes))
                or not isinstance(self.allowed_join_pairs, tuple)
                or any(not isinstance(item, tuple) or len(item) != _api.JOIN_PAIR_ARITY
                       or not all(_api._name(value) for value in item)
                       or item != tuple(sorted(item))
                       for item in self.allowed_join_pairs)
                or self.allowed_join_pairs != tuple(sorted(set(self.allowed_join_pairs)))
                or not isinstance(self.allowed_join_sets, tuple)
                or any(not isinstance(item, tuple) or len(item) < _api.MIN_JOIN_SET_ARITY
                       or not all(_api._name(value) for value in item)
                       or item != tuple(sorted(item))
                       for item in self.allowed_join_sets)
                or self.allowed_join_sets != tuple(sorted(set(self.allowed_join_sets)))
                or self.schema_version != _api.POLICY_SCHEMA):
            _api._invalid("BAMF_CONTEXT_POLICY_INVALID")


@dataclass(frozen=True)
class ApprovedFrame:
    frame_handle: str
    source_handle: str
    member_handles: tuple[str, ...]
    occurrence_id: str
    content_digest: str
    join_class: str
    envelope_digest: str
    schema_version: str = _api.APPROVED_FRAME_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_api._name(item) for item in (
                    self.frame_handle, self.source_handle, self.join_class))
                or not isinstance(self.member_handles, tuple)
                or any(not _api._name(item) for item in self.member_handles)
                or not all(isinstance(item, str) and _api._SHA256.fullmatch(item)
                           for item in (
                               self.occurrence_id, self.content_digest,
                               self.envelope_digest))
                or self.schema_version != _api.APPROVED_FRAME_SCHEMA):
            _api._invalid("BAMF_CONTEXT_APPROVED_FRAME_INVALID")


@dataclass(frozen=True)
class EligibleContext:
    frames: tuple[ApprovedFrame, ...]
    allowed_join_classes: tuple[str, ...]
    digest: str
    schema_version: str = _api.ELIGIBLE_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.frames, tuple) or not self.frames
                or any(not isinstance(item, _api.ApprovedFrame) for item in self.frames)
                or tuple(item.frame_handle for item in self.frames)
                != tuple(sorted({item.frame_handle for item in self.frames}))
                or not _api._names(self.allowed_join_classes)
                or not isinstance(self.digest, str)
                or not _api._SHA256.fullmatch(self.digest)
                or self.schema_version != _api.ELIGIBLE_CONTEXT_SCHEMA):
            _api._invalid("BAMF_CONTEXT_APPROVED_VIEW_INVALID")


@dataclass(frozen=True)
class ContextHold:
    reason_codes: tuple[str, ...]
    source_handles: tuple[str, ...]
    diagnostics: tuple[tuple[str, str], ...]
    schema_version: str = _api.CONTEXT_HOLD_SCHEMA

    def __post_init__(self) -> None:
        if (not _api._names(self.reason_codes) or not self.reason_codes
                or not _api._names(self.source_handles)
                or not isinstance(self.diagnostics, tuple)
                or len(self.diagnostics) > _api.MAX_CONTEXT_HOLD_DIAGNOSTICS
                or any(not isinstance(item, tuple) or len(item) != _api.JOIN_PAIR_ARITY
                       or not all(_api._name(value) for value in item)
                       for item in self.diagnostics)
                or self.diagnostics != tuple(sorted(set(self.diagnostics)))
                or self.schema_version != _api.CONTEXT_HOLD_SCHEMA):
            _api._invalid("BAMF_CONTEXT_HOLD_INVALID")
