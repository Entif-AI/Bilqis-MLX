"""Explicit failure, degraded-read, and ordered-event envelopes."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .model import RecordMeta, WireRecord, is_name, is_names, is_sha256, is_time, require


class UnavailableReason(StrEnum):
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    DENIED = "DENIED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ErrorEnvelope(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.error-envelope/v1"
    RUN_BOUND = False
    meta: RecordMeta
    code: str
    message: str
    related_record_id: str | None

    def __post_init__(self) -> None:
        super().__post_init__()
        require(is_name(self.code) and is_name(self.message), "ERROR_ENVELOPE")
        require(self.related_record_id is None or is_name(self.related_record_id), "ERROR_RELATED")


@dataclass(frozen=True)
class UnavailableEnvelope(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.unavailable-envelope/v1"
    RUN_BOUND = False
    meta: RecordMeta
    resource: str
    reason: UnavailableReason
    detail_ref: str | None

    def __post_init__(self) -> None:
        super().__post_init__()
        require(is_name(self.resource) and type(self.reason) is UnavailableReason,
                "UNAVAILABLE_ENVELOPE")
        require(self.detail_ref is None or is_name(self.detail_ref), "UNAVAILABLE_DETAIL")
        if self.reason is UnavailableReason.DENIED:
            require(not self.meta.source_refs and not self.meta.evidence_refs
                    and not self.meta.receipt_refs, "DENIED_PROVENANCE_LEAK")


@dataclass(frozen=True)
class StaleEnvelope(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.stale-envelope/v1"
    meta: RecordMeta
    stale_record_id: str
    stale_as_of: int
    requested_as_of: int

    def __post_init__(self) -> None:
        super().__post_init__()
        require(is_name(self.stale_record_id), "STALE_RECORD")
        require(is_time(self.stale_as_of) and is_time(self.requested_as_of)
                and self.stale_as_of < self.requested_as_of, "STALE_TIME")


@dataclass(frozen=True)
class PartialEnvelope(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.partial-envelope/v1"
    meta: RecordMeta
    partial_record_id: str
    missing_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        require(is_name(self.partial_record_id), "PARTIAL_RECORD")
        require(is_names(self.missing_fields, allow_empty=False), "PARTIAL_FIELDS")


@dataclass(frozen=True)
class StreamPosition:
    stream_id: str
    epoch_id: str
    ordinal: int
    cursor_sha256: str
    previous_cursor_sha256: str | None

    def __post_init__(self) -> None:
        require(is_name(self.stream_id) and is_name(self.epoch_id), "STREAM_POSITION")
        require(type(self.ordinal) is int and self.ordinal >= 0, "STREAM_ORDINAL")
        require(is_sha256(self.cursor_sha256), "STREAM_CURSOR")
        require(self.previous_cursor_sha256 is None
                or is_sha256(self.previous_cursor_sha256), "PREVIOUS_CURSOR")
        require(self.previous_cursor_sha256 != self.cursor_sha256, "CURSOR_SELF_LINK")


@dataclass(frozen=True)
class EventEnvelope(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.event-envelope/v1"
    meta: RecordMeta
    event_id: str
    position: StreamPosition
    event_family: str
    payload_schema_version: str
    payload_record_id: str
    payload_sha256: str
    payload_ref: str

    def __post_init__(self) -> None:
        super().__post_init__()
        require(is_name(self.event_id) and type(self.position) is StreamPosition,
                "EVENT_IDENTITY")
        require(all(is_name(item) for item in (
            self.event_family, self.payload_schema_version,
            self.payload_record_id, self.payload_ref)), "EVENT_PAYLOAD_REF")
        require(is_sha256(self.payload_sha256), "EVENT_PAYLOAD_DIGEST")
