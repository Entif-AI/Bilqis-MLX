"""C10.1 append-only Akasha projection intents and idempotent SQLite outbox.

Transport is at-least-once; stable event IDs permit semantic deduplication
at the eventual Akasha receiver. C10.2 owns visibility/redaction policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from contextlib import contextmanager
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from ..errors import ErrorBus, SCHOOL


AKASHA_EVENT_SCHEMA = "bilqis.c10.akasha-event/v1"
AKASHA_PROJECTION_SCHEMA = "bilqis.c10.akasha-projection/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DELIVERY_STATUSES = frozenset({"FAILED", "DELIVERED"})


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_AKASHA.INVALID, reason=reason)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        _invalid("BAMF_C10_PAYLOAD_NOT_CANONICAL")


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _time(value: object) -> bool:
    return type(value) is int and value >= 0


class AkashaEventKind(str, Enum):
    SOURCE_CORRECTION = "SOURCE_CORRECTION"
    REVALIDATION = "REVALIDATION"
    REQUALIFICATION = "REQUALIFICATION"
    CAPABILITY_GRADUATION = "CAPABILITY_GRADUATION"
    MOTIF_CANDIDATE = "MOTIF_CANDIDATE"
    PROCESS_FAULT = "PROCESS_FAULT"
    CHECKPOINT_PUBLICATION = "CHECKPOINT_PUBLICATION"


_REQUIRED_FIELDS = {
    AkashaEventKind.SOURCE_CORRECTION: frozenset({
        "correction_event_id", "source_owner", "dependency_key",
        "old_digest", "new_digest"}),
    AkashaEventKind.REVALIDATION: frozenset({
        "artifact_id", "old_digest", "new_digest", "eligible"}),
    AkashaEventKind.REQUALIFICATION: frozenset({
        "capability_id", "retained_generation_sha256", "status"}),
    AkashaEventKind.CAPABILITY_GRADUATION: frozenset({
        "capability_id", "generation_sha256", "assessment_receipt_sha256"}),
    AkashaEventKind.MOTIF_CANDIDATE: frozenset({
        "motif_id", "source_refs", "eligibility_digest"}),
    AkashaEventKind.PROCESS_FAULT: frozenset({
        "fault_id", "original_source_event_id", "correction_event_id",
        "remediation_id", "derived_path"}),
    AkashaEventKind.CHECKPOINT_PUBLICATION: frozenset({
        "checkpoint_digest", "generation_sha256", "manifest_digest"}),
}
_DIGEST_FIELDS = frozenset({
    "old_digest", "new_digest", "retained_generation_sha256",
    "generation_sha256", "assessment_receipt_sha256",
    "eligibility_digest", "checkpoint_digest", "manifest_digest",
})
_NONEMPTY_LIST_FIELDS = frozenset({"source_refs", "derived_path"})


def _payload_for(kind: AkashaEventKind, payload_json: str) -> dict:
    try:
        payload = json.loads(payload_json)
    except (TypeError, ValueError):
        _invalid("BAMF_C10_PAYLOAD_NOT_CANONICAL")
    if (not isinstance(payload, dict)
            or any(not isinstance(key, str) for key in payload)
            or not _REQUIRED_FIELDS[kind].issubset(payload)
            or payload_json != _canonical(payload)):
        _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    for key in _REQUIRED_FIELDS[kind]:
        value = payload[key]
        if value is None or value == "" or value == []:
            _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
        if key in _DIGEST_FIELDS and not _sha(value):
            _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
        if (key in _NONEMPTY_LIST_FIELDS
                and (not isinstance(value, list)
                     or not value
                     or any(not _name(item) for item in value))):
            _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    if (kind is AkashaEventKind.REVALIDATION
            and type(payload["eligible"]) is not bool):
        _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    if (kind is AkashaEventKind.REQUALIFICATION
            and payload["status"] not in (
                "QUALIFIED", "REQUALIFICATION_REQUIRED")):
        _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    return payload


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


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS akasha_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    payload_digest TEXT NOT NULL,
    envelope_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS akasha_delivery_attempts (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES akasha_events(event_id),
    attempt_id TEXT NOT NULL,
    status TEXT NOT NULL,
    receipt_digest TEXT NOT NULL,
    recorded_at INTEGER NOT NULL,
    UNIQUE(event_id, attempt_id)
);
CREATE TRIGGER IF NOT EXISTS akasha_events_no_update
BEFORE UPDATE ON akasha_events
BEGIN SELECT RAISE(ABORT, 'AKASHA_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_events_no_delete
BEFORE DELETE ON akasha_events
BEGIN SELECT RAISE(ABORT, 'AKASHA_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_attempts_no_update
BEFORE UPDATE ON akasha_delivery_attempts
BEGIN SELECT RAISE(ABORT, 'AKASHA_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_attempts_no_delete
BEFORE DELETE ON akasha_delivery_attempts
BEGIN SELECT RAISE(ABORT, 'AKASHA_APPEND_ONLY'); END;
"""


def _open_outbox(path: Path) -> sqlite3.Connection:
    if not isinstance(path, Path) or not path.parent.is_dir():
        _invalid("BAMF_C10_OUTBOX_PATH_INVALID")
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(_SCHEMA_SQL)
    return connection


@contextmanager
def _outbox_connection(path: Path):
    connection = _open_outbox(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def append_outbox(path: Path, event: AkashaEvent) -> bool:
    if not isinstance(event, AkashaEvent):
        _invalid("BAMF_C10_EVENT_ARGUMENT_INVALID")
    event.validate()
    envelope = _canonical({
        **asdict(event), "kind": event.kind.value})
    with _outbox_connection(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        prior = connection.execute(
            "SELECT payload_digest, envelope_json FROM akasha_events "
            "WHERE event_id = ?", (event.event_id,)).fetchone()
        if prior is not None:
            if prior != (event.payload_digest, envelope):
                _invalid("BAMF_C10_EVENT_ID_CONFLICT")
            return False
        connection.execute(
            "INSERT INTO akasha_events (event_id, payload_digest, envelope_json) "
            "VALUES (?, ?, ?)",
            (event.event_id, event.payload_digest, envelope))
        return True


def _read_event(row: tuple[str]) -> AkashaEvent:
    try:
        payload = json.loads(row[0])
        return AkashaEvent(
            **{**payload, "kind": AkashaEventKind(payload["kind"])})
    except (TypeError, ValueError, KeyError):
        _invalid("BAMF_C10_STORED_EVENT_INVALID")


def read_outbox(path: Path) -> tuple[AkashaEvent, ...]:
    if not isinstance(path, Path):
        _invalid("BAMF_C10_OUTBOX_PATH_INVALID")
    if not path.exists():
        return ()
    with _outbox_connection(path) as connection:
        rows = connection.execute(
            "SELECT envelope_json FROM akasha_events ORDER BY seq").fetchall()
    return tuple(_read_event(row) for row in rows)


def pending_events(path: Path) -> tuple[AkashaEvent, ...]:
    if not isinstance(path, Path):
        _invalid("BAMF_C10_OUTBOX_PATH_INVALID")
    if not path.exists():
        return ()
    with _outbox_connection(path) as connection:
        rows = connection.execute(
            "SELECT e.envelope_json FROM akasha_events e "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM akasha_delivery_attempts a "
            "WHERE a.event_id=e.event_id AND a.status='DELIVERED') "
            "ORDER BY e.seq").fetchall()
    return tuple(_read_event(row) for row in rows)


def record_delivery_attempt(
    path: Path, event_id: str, attempt_id: str,
    status: str, receipt_digest: str, recorded_at: int,
) -> bool:
    if (not _sha(event_id) or not _name(attempt_id)
            or status not in _DELIVERY_STATUSES
            or not _sha(receipt_digest) or not _time(recorded_at)):
        _invalid("BAMF_C10_DELIVERY_ATTEMPT_INVALID")
    with _outbox_connection(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM akasha_events WHERE event_id=?",
            (event_id,)).fetchone() is None:
            _invalid("BAMF_C10_DELIVERY_EVENT_UNKNOWN")
        prior = connection.execute(
            "SELECT status, receipt_digest, recorded_at "
            "FROM akasha_delivery_attempts WHERE event_id=? AND attempt_id=?",
            (event_id, attempt_id)).fetchone()
        if prior is not None:
            if prior != (status, receipt_digest, recorded_at):
                _invalid("BAMF_C10_DELIVERY_ATTEMPT_CONFLICT")
            return False
        connection.execute(
            "INSERT INTO akasha_delivery_attempts "
            "(event_id, attempt_id, status, receipt_digest, recorded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, attempt_id, status, receipt_digest, recorded_at))
        return True


def events_from_c09_intent(intent, correction, ledger, authority_registry):
    """Bridge signed C09 source invalidations into C10's durable event IDs."""
    from .atlas_revalidation import CorrectionEvent, SourceAuthorityRegistry
    from .atlas_requalification import (
        C10InvalidationIntent, RequalificationLedger,
        RequalificationStatus,
    )

    if (not isinstance(intent, C10InvalidationIntent)
            or not isinstance(correction, CorrectionEvent)
            or not isinstance(ledger, RequalificationLedger)
            or not isinstance(authority_registry, SourceAuthorityRegistry)):
        _invalid("BAMF_C10_C09_INTENT_ARGUMENT_INVALID")
    authority_registry.verify_correction(correction)
    if (intent.correction_event_id != correction.event_id
            or intent.source_receipt_sha256
            != correction.source_receipt_sha256
            or intent.delivery_state != "PENDING_C10"):
        _invalid("BAMF_C10_C09_INTENT_SOURCE_DRIFT")
    events = []
    for capability_id in intent.capability_ids:
        support = ledger.capability(capability_id)
        if support.status is not RequalificationStatus.REQUALIFICATION_REQUIRED:
            _invalid("BAMF_C10_C09_INTENT_CAPABILITY_NOT_HELD")
        events.append(AkashaEvent.from_payload(
            kind=AkashaEventKind.REQUALIFICATION,
            subject_id=capability_id,
            source_receipt_sha256=correction.source_receipt_sha256,
            payload={
                "capability_id": capability_id,
                "retained_generation_sha256":
                    support.retained_generation_sha256,
                "status": "REQUALIFICATION_REQUIRED",
                "source_intent_event_id": intent.event_id,
                "affected_artifact_ids": list(intent.affected_artifact_ids),
            },
            source_time=correction.source_time,
            effective_time=correction.effective_time,
            observed_at=correction.observed_at,
            recorded_at=correction.recorded_at,
        ))
    return tuple(events)


def append_c09_intent(
    path: Path, intent, correction, ledger, authority_registry,
) -> int:
    """Idempotent C09->C10 outbox enqueue; external Akasha send is separate."""
    events = events_from_c09_intent(
        intent, correction, ledger, authority_registry)
    return sum(append_outbox(path, event) for event in events)
