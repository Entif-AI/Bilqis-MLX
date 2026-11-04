"""Approved and held context-admission result records."""
from __future__ import annotations

from dataclasses import dataclass

from .common import (APPROVED_FRAME_SCHEMA, ELIGIBLE_CONTEXT_SCHEMA,
                     CONTEXT_HOLD_SCHEMA, JOIN_PAIR_ARITY,
                     MAX_CONTEXT_HOLD_DIAGNOSTICS,
                     _SHA256, _invalid, _name, _names)

@dataclass(frozen=True)
class ApprovedFrame:
    frame_handle: str
    source_handle: str
    member_handles: tuple[str, ...]
    occurrence_id: str
    content_digest: str
    join_class: str
    envelope_digest: str
    schema_version: str = APPROVED_FRAME_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.frame_handle, self.source_handle, self.join_class))
                or not isinstance(self.member_handles, tuple)
                or any(not _name(item) for item in self.member_handles)
                or not all(isinstance(item, str) and _SHA256.fullmatch(item)
                           for item in (
                               self.occurrence_id, self.content_digest,
                               self.envelope_digest))
                or self.schema_version != APPROVED_FRAME_SCHEMA):
            _invalid("BAMF_CONTEXT_APPROVED_FRAME_INVALID")


@dataclass(frozen=True)
class EligibleContext:
    frames: tuple[ApprovedFrame, ...]
    allowed_join_classes: tuple[str, ...]
    digest: str
    schema_version: str = ELIGIBLE_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.frames, tuple) or not self.frames
                or any(not isinstance(item, ApprovedFrame) for item in self.frames)
                or tuple(item.frame_handle for item in self.frames)
                != tuple(sorted({item.frame_handle for item in self.frames}))
                or not _names(self.allowed_join_classes)
                or not isinstance(self.digest, str)
                or not _SHA256.fullmatch(self.digest)
                or self.schema_version != ELIGIBLE_CONTEXT_SCHEMA):
            _invalid("BAMF_CONTEXT_APPROVED_VIEW_INVALID")


@dataclass(frozen=True)
class ContextHold:
    reason_codes: tuple[str, ...]
    source_handles: tuple[str, ...]
    diagnostics: tuple[tuple[str, str], ...]
    schema_version: str = CONTEXT_HOLD_SCHEMA

    def __post_init__(self) -> None:
        if (not _names(self.reason_codes) or not self.reason_codes
                or not _names(self.source_handles)
                or not isinstance(self.diagnostics, tuple)
                or len(self.diagnostics) > MAX_CONTEXT_HOLD_DIAGNOSTICS
                or any(not isinstance(item, tuple) or len(item) != JOIN_PAIR_ARITY
                       or not all(_name(value) for value in item)
                       for item in self.diagnostics)
                or self.diagnostics != tuple(sorted(set(self.diagnostics)))
                or self.schema_version != CONTEXT_HOLD_SCHEMA):
            _invalid("BAMF_CONTEXT_HOLD_INVALID")

