"""Append-only SQLite outbox and delivery receipts."""
from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from .contracts import OWNER_FIXTURE_KINDS, _canonical, _digest, _invalid, _name, _sha, _time, _DELIVERY_STATUSES
from .events import AkashaEvent
from .contracts import AkashaEventKind

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS akasha_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    payload_digest TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    projection_binding_json TEXT,
    owner_source_key TEXT
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
    if "projection_binding_json" not in {row[1] for row in connection.execute("PRAGMA table_info(akasha_events)")}:
        connection.execute("ALTER TABLE akasha_events ADD COLUMN projection_binding_json TEXT")
    if "owner_source_key" not in {row[1] for row in connection.execute("PRAGMA table_info(akasha_events)")}:
        connection.execute("ALTER TABLE akasha_events ADD COLUMN owner_source_key TEXT")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS akasha_owner_source_identity ON akasha_events(owner_source_key)")
    return connection


@contextmanager
def _outbox_connection(path: Path):
    connection = _open_outbox(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _prepare_outbox_entry(event: AkashaEvent, projection_binding):
    if not isinstance(event, AkashaEvent):
        _invalid("BAMF_C10_EVENT_ARGUMENT_INVALID")
    event.validate()
    owner_source_key = None
    if event.kind in OWNER_FIXTURE_KINDS:
        fields = json.loads(event.payload_json)
        owner_source_key = _digest(_canonical([event.kind.value, fields["producer_id"], fields["owner_source_event_id"]]).encode())
    binding_json = None
    if projection_binding is not None:
        from ..bamf_projection import BamfProjectionEvent
        BamfProjectionEvent(event=event, **projection_binding)
        binding_json = _canonical(projection_binding)
    envelope = _canonical({
        **asdict(event), "kind": event.kind.value})
    return event, envelope, binding_json, owner_source_key


def append_outbox_batch(path: Path, entries: tuple) -> int:
    """Append a complete batch in one transaction, or leave all rows unchanged."""
    prepared = tuple(_prepare_outbox_entry(event, binding) for event, binding in entries)
    if not prepared:
        return 0
    appended = 0
    with _outbox_connection(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for event, envelope, binding_json, owner_source_key in prepared:
            if owner_source_key is not None:
                source_prior = connection.execute("SELECT event_id FROM akasha_events WHERE owner_source_key = ?", (owner_source_key,)).fetchone()
                if source_prior is not None and source_prior[0] != event.event_id:
                    _invalid("BAMF_C10_OWNER_SOURCE_EVENT_CONFLICT")
            prior = connection.execute(
                "SELECT payload_digest, envelope_json, projection_binding_json FROM akasha_events "
                "WHERE event_id = ?", (event.event_id,)).fetchone()
            if prior is not None:
                if prior != (event.payload_digest, envelope, binding_json):
                    _invalid("BAMF_C10_EVENT_ID_CONFLICT")
                continue
            connection.execute(
                "INSERT INTO akasha_events (event_id, payload_digest, envelope_json, projection_binding_json, owner_source_key) "
                "VALUES (?, ?, ?, ?, ?)",
                (event.event_id, event.payload_digest, envelope, binding_json, owner_source_key))
            appended += 1
    return appended


def append_outbox(path: Path, event: AkashaEvent, *, projection_binding=None) -> bool:
    return bool(append_outbox_batch(path, ((event, projection_binding),)))


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
