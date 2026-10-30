"""Validated immutable event envelopes and projections."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json
from .contracts import (
    AKASHA_EVENT_SCHEMA, AKASHA_PROJECTION_SCHEMA, AkashaEventKind,
    NATIVE_EVENT_KINDS, OWNER_FIXTURE_KINDS, _payload_for, _invalid,
    _name, _sha, _time, _digest, _canonical,
)

@dataclass(frozen=True)
class AkashaEvent:
    event_id: str
    payload_digest: str
    kind: AkashaEventKind
    subject_id: str
    source_receipt_sha256: str
    payload_json: str
    source_time: int
    effective_time: int
    observed_at: int
    recorded_at: int
    schema_version: str = AKASHA_EVENT_SCHEMA

    @classmethod
    def from_payload(
        cls, *, kind: AkashaEventKind, subject_id: str,
        source_receipt_sha256: str, payload: dict,
        source_time: int, effective_time: int,
        observed_at: int, recorded_at: int,
    ) -> "AkashaEvent":
        if not isinstance(kind, AkashaEventKind):
            _invalid("BAMF_C10_EVENT_KIND_INVALID")
        payload_json = _canonical(payload)
        payload_digest = _digest(payload_json.encode("utf-8"))
        fields = {
            "schema_version": AKASHA_EVENT_SCHEMA,
            "kind": kind.value,
            "subject_id": subject_id,
            "source_receipt_sha256": source_receipt_sha256,
            "payload_digest": payload_digest,
            "source_time": source_time,
            "effective_time": effective_time,
            "observed_at": observed_at,
            "recorded_at": recorded_at,
        }
        return cls(
            event_id=_digest(_canonical(fields).encode("utf-8")),
            payload_digest=payload_digest,
            kind=kind, subject_id=subject_id,
            source_receipt_sha256=source_receipt_sha256,
            payload_json=payload_json, source_time=source_time,
            effective_time=effective_time, observed_at=observed_at,
            recorded_at=recorded_at)

    def validate(self) -> None:
        if (not isinstance(self.kind, AkashaEventKind)
                or not _sha(self.event_id)
                or not _sha(self.payload_digest)
                or not _name(self.subject_id)
                or not _sha(self.source_receipt_sha256)
                or not isinstance(self.payload_json, str)
                or not all(_time(value) for value in (
                    self.source_time, self.effective_time,
                    self.observed_at, self.recorded_at))
                or self.observed_at > self.recorded_at
                or self.schema_version != AKASHA_EVENT_SCHEMA):
            _invalid("BAMF_C10_EVENT_IDENTITY_INVALID")
        _payload_for(self.kind, self.payload_json)
        expected_payload_digest = _digest(self.payload_json.encode("utf-8"))
        identity = {
            "schema_version": self.schema_version,
            "kind": self.kind.value,
            "subject_id": self.subject_id,
            "source_receipt_sha256": self.source_receipt_sha256,
            "payload_digest": expected_payload_digest,
            "source_time": self.source_time,
            "effective_time": self.effective_time,
            "observed_at": self.observed_at,
            "recorded_at": self.recorded_at,
        }
        if (self.payload_digest != expected_payload_digest
                or self.event_id != _digest(
                    _canonical(identity).encode("utf-8"))):
            _invalid("BAMF_C10_EVENT_IDENTITY_INVALID")

    def __post_init__(self) -> None:
        self.validate()


@dataclass(frozen=True)
class AkashaProjection:
    event_id: str
    kind: AkashaEventKind
    subject_id: str
    source_receipt_sha256: str
    payload_digest: str
    payload_json: str
    visibility: str = "INTERNAL_ONLY"
    schema_version: str = AKASHA_PROJECTION_SCHEMA

    def __post_init__(self) -> None:
        if (not _sha(self.event_id)
                or not isinstance(self.kind, AkashaEventKind)
                or not _name(self.subject_id)
                or not _sha(self.source_receipt_sha256)
                or not _sha(self.payload_digest)
                or not isinstance(self.payload_json, str)
                or self.visibility != "INTERNAL_ONLY"
                or self.schema_version != AKASHA_PROJECTION_SCHEMA):
            _invalid("BAMF_C10_PROJECTION_INVALID")
        _payload_for(self.kind, self.payload_json)
        if self.payload_digest != _digest(self.payload_json.encode("utf-8")):
            _invalid("BAMF_C10_PROJECTION_INVALID")


def project_event(event: AkashaEvent) -> AkashaProjection:
    if not isinstance(event, AkashaEvent):
        _invalid("BAMF_C10_EVENT_ARGUMENT_INVALID")
    event.validate()
    return AkashaProjection(
        event_id=event.event_id, kind=event.kind,
        subject_id=event.subject_id,
        source_receipt_sha256=event.source_receipt_sha256,
        payload_digest=event.payload_digest,
        payload_json=event.payload_json)
