"""Disposable CP06 SQLite projection over accepted Mission Control records."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Iterable

from bilqis_mlx.errors import ErrorBus, SCHOOL

from .codec import canonical_json, decode_json
from .envelopes import EventEnvelope
from .model import (
    MissionControlContractError, WireRecord, is_name, is_sha256,
    is_wire_integer,
)
from .query_catalog import MissionControlQueryCatalog


PROJECTION_SCHEMA = "bilqis.bamf.mission-control.projection-index/v1"
PROJECTION_SCHEMA_VERSION = 1


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_CONTROL_PLANE.INVALID, reason=reason)


class ProjectionFrontierState(StrEnum):
    EMPTY = "EMPTY"
    CURRENT = "CURRENT"
    STALE = "STALE"
    DIVERGED = "DIVERGED"


@dataclass(frozen=True)
class ProjectionStats:
    active_records: int
    revisions: int
    references: int
    events: int


@dataclass(frozen=True)
class ProjectionFrontierStatus:
    state: ProjectionFrontierState
    stream_id: str
    projected_epoch_id: str | None
    projected_next_ordinal: int | None
    authoritative_epoch_id: str
    authoritative_next_ordinal: int


_SCHEMA_SQL = f"""
CREATE TABLE projection_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;
INSERT INTO projection_meta(key, value)
VALUES ('schema_version', '{PROJECTION_SCHEMA_VERSION}');
INSERT INTO projection_meta(key, value)
VALUES ('schema_id', '{PROJECTION_SCHEMA}');

CREATE TABLE record_revisions (
    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    run_id TEXT,
    generation INTEGER,
    materialized_at INTEGER NOT NULL,
    observed_at INTEGER,
    as_of INTEGER,
    event_id TEXT,
    payload_json TEXT NOT NULL,
    active INTEGER NOT NULL CHECK(active IN (0, 1)),
    UNIQUE(record_id, payload_sha256)
);
CREATE UNIQUE INDEX active_record_by_id
ON record_revisions(record_id) WHERE active = 1;
CREATE INDEX records_by_schema
ON record_revisions(schema_version, active);
CREATE INDEX records_by_run_generation
ON record_revisions(run_id, generation, active);
CREATE UNIQUE INDEX event_identity_unique
ON record_revisions(event_id) WHERE event_id IS NOT NULL;

CREATE TABLE record_refs (
    revision_id INTEGER NOT NULL REFERENCES record_revisions(revision_id)
        ON DELETE CASCADE,
    relation TEXT NOT NULL,
    ref TEXT NOT NULL,
    PRIMARY KEY(revision_id, relation, ref)
) WITHOUT ROWID;
CREATE INDEX refs_by_target ON record_refs(ref, relation);

CREATE TABLE event_frontiers (
    stream_id TEXT PRIMARY KEY,
    epoch_id TEXT NOT NULL,
    next_ordinal INTEGER NOT NULL,
    latest_cursor_sha256 TEXT
) WITHOUT ROWID;
"""


def _rank(record: WireRecord, digest: str) -> tuple:
    run = record.meta.run
    return (
        -1 if run is None else run.generation,
        -1 if record.meta.as_of is None else record.meta.as_of,
        -1 if record.meta.observed_at is None else record.meta.observed_at,
        record.meta.materialized_at,
        digest,
    )


def _row_rank(row: sqlite3.Row) -> tuple:
    return (
        -1 if row["generation"] is None else row["generation"],
        -1 if row["as_of"] is None else row["as_of"],
        -1 if row["observed_at"] is None else row["observed_at"],
        row["materialized_at"],
        row["payload_sha256"],
    )


class MissionControlProjection:
    """Rebuildable local index; CP02 records and durable artifacts remain truth."""

    def __init__(self, path: Path, *, _create: bool = False):
        self.path = Path(path)
        if self.path.is_symlink():
            _invalid("PROJECTION_PATH_UNSAFE")
        if not self.path.exists():
            if not _create:
                _invalid("PROJECTION_MISSING_REBUILD_REQUIRED")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._create()
        elif not self.path.is_file():
            _invalid("PROJECTION_PATH_UNSAFE")
        self._validate()

    @classmethod
    def create_empty(cls, path: Path) -> "MissionControlProjection":
        target = Path(path)
        if target.exists() or target.is_symlink():
            _invalid("PROJECTION_ALREADY_EXISTS")
        return cls(target, _create=True)

    def _connect(self) -> sqlite3.Connection:
        if self.path.is_symlink():
            _invalid("PROJECTION_PATH_UNSAFE")
        if not self.path.exists():
            _invalid("PROJECTION_MISSING_REBUILD_REQUIRED")
        if not self.path.is_file():
            _invalid("PROJECTION_PATH_UNSAFE")
        try:
            db = sqlite3.connect(self.path)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            return db
        except sqlite3.Error:
            _invalid("PROJECTION_CORRUPT_REBUILD_REQUIRED")

    def _create(self) -> None:
        try:
            db = sqlite3.connect(self.path)
            try:
                db.executescript(_SCHEMA_SQL)
                db.commit()
            finally:
                db.close()
            os.chmod(self.path, 0o600)
        except (OSError, sqlite3.Error):
            _invalid("PROJECTION_CREATE_FAILED")

    def _validate(self) -> None:
        try:
            with self._connect() as db:
                integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    _invalid("PROJECTION_CORRUPT_REBUILD_REQUIRED")
                rows = dict(db.execute(
                    "SELECT key, value FROM projection_meta").fetchall())
        except sqlite3.Error:
            _invalid("PROJECTION_CORRUPT_REBUILD_REQUIRED")
        if rows.get("schema_id") != PROJECTION_SCHEMA:
            _invalid("PROJECTION_SCHEMA_INCOMPATIBLE_REBUILD_REQUIRED")
        if rows.get("schema_version") != str(PROJECTION_SCHEMA_VERSION):
            _invalid("PROJECTION_SCHEMA_INCOMPATIBLE_REBUILD_REQUIRED")

    @classmethod
    def rebuild(
        cls, path: Path, records: Iterable[WireRecord], *,
        frontiers: Iterable[tuple[str, str, int, str | None]] = (),
    ) -> "MissionControlProjection":
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or (target.exists() and not target.is_file()):
            _invalid("PROJECTION_PATH_UNSAFE")
        handle, temp_name = tempfile.mkstemp(
            prefix=target.name + ".rebuild-", dir=target.parent)
        os.close(handle)
        temp = Path(temp_name)
        try:
            temp.unlink()
            candidate = cls(temp, _create=True)
            candidate.ingest_records(records)
            for frontier in frontiers:
                candidate.record_frontier(*frontier)
            os.replace(temp, target)
            return cls(target)
        finally:
            if temp.exists():
                temp.unlink()

    def ingest_records(self, records: Iterable[WireRecord]) -> ProjectionStats:
        material = tuple(records)
        if not all(isinstance(record, WireRecord) for record in material):
            _invalid("PROJECTION_RECORD_REQUIRED")
        try:
            with self._connect() as db:
                for record in material:
                    self._ingest_record(db, record)
                db.commit()
                return self._stats(db)
        except sqlite3.Error:
            _invalid("PROJECTION_WRITE_FAILED_REBUILD_REQUIRED")

    def _ingest_record(self, db: sqlite3.Connection, record: WireRecord) -> None:
        payload = canonical_json(record)
        digest = hashlib.sha256(payload).hexdigest()
        run = record.meta.run
        if type(record) is EventEnvelope:
            existing_event = db.execute(
                "SELECT payload_sha256 FROM record_revisions WHERE event_id = ?",
                (record.event_id,),
            ).fetchone()
            if (existing_event is not None
                    and existing_event["payload_sha256"] != digest):
                _invalid("PROJECTION_EVENT_IDENTITY_CONFLICT")
        current = db.execute(
            "SELECT * FROM record_revisions WHERE record_id = ? AND active = 1",
            (record.meta.record_id,),
        ).fetchone()
        db.execute(
            """INSERT OR IGNORE INTO record_revisions(
                record_id, schema_version, payload_sha256, run_id, generation,
                materialized_at, observed_at, as_of, event_id, payload_json, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                record.meta.record_id, record.schema_version, digest,
                None if run is None else run.run_id,
                None if run is None else run.generation,
                record.meta.materialized_at, record.meta.observed_at,
                record.meta.as_of,
                record.event_id if type(record) is EventEnvelope else None,
                payload.decode("utf-8"),
            ),
        )
        revision = db.execute(
            "SELECT revision_id FROM record_revisions WHERE record_id = ? AND payload_sha256 = ?",
            (record.meta.record_id, digest),
        ).fetchone()[0]
        for relation, refs in (
            ("SOURCE", record.meta.source_refs),
            ("EVIDENCE", record.meta.evidence_refs),
            ("RECEIPT", record.meta.receipt_refs),
        ):
            db.executemany(
                "INSERT OR IGNORE INTO record_refs(revision_id, relation, ref) VALUES (?, ?, ?)",
                ((revision, relation, ref) for ref in refs),
            )
        if current is None or _rank(record, digest) > _row_rank(current):
            db.execute(
                "UPDATE record_revisions SET active = 0 WHERE record_id = ?",
                (record.meta.record_id,),
            )
            db.execute(
                "UPDATE record_revisions SET active = 1 WHERE revision_id = ?",
                (revision,),
            )
    def ingest_event(
        self, event: EventEnvelope, payload: WireRecord,
    ) -> ProjectionStats:
        if type(event) is not EventEnvelope or not isinstance(payload, WireRecord):
            _invalid("PROJECTION_EVENT_PAYLOAD_REQUIRED")
        digest = hashlib.sha256(canonical_json(payload)).hexdigest()
        if (event.payload_schema_version != payload.schema_version
                or event.payload_record_id != payload.meta.record_id
                or event.payload_sha256 != digest):
            _invalid("PROJECTION_EVENT_PAYLOAD_MISMATCH")
        try:
            with self._connect() as db:
                self._ingest_record(db, payload)
                self._ingest_record(db, event)
                self._record_frontier(
                    db, event.position.stream_id, event.position.epoch_id,
                    event.position.ordinal + 1, event.position.cursor_sha256,
                )
                db.commit()
                return self._stats(db)
        except sqlite3.Error:
            _invalid("PROJECTION_WRITE_FAILED_REBUILD_REQUIRED")

    @staticmethod
    def _record_frontier(
        db: sqlite3.Connection, stream_id: str, epoch_id: str,
        next_ordinal: int, latest_cursor_sha256: str | None,
    ) -> None:
        current = db.execute(
            "SELECT * FROM event_frontiers WHERE stream_id = ?", (stream_id,),
        ).fetchone()
        if current is not None and current["epoch_id"] != epoch_id:
            _invalid("PROJECTION_FRONTIER_EPOCH_MISMATCH_REBUILD_REQUIRED")
        if current is not None:
            if next_ordinal < current["next_ordinal"]:
                return
            if (next_ordinal == current["next_ordinal"]
                    and latest_cursor_sha256 != current["latest_cursor_sha256"]):
                _invalid("PROJECTION_FRONTIER_CONFLICT")
        db.execute(
            """INSERT INTO event_frontiers(
                stream_id, epoch_id, next_ordinal, latest_cursor_sha256
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(stream_id) DO UPDATE SET
                epoch_id = excluded.epoch_id,
                next_ordinal = excluded.next_ordinal,
                latest_cursor_sha256 = excluded.latest_cursor_sha256""",
            (stream_id, epoch_id, next_ordinal, latest_cursor_sha256),
        )

    def record_frontier(
        self, stream_id: str, epoch_id: str, next_ordinal: int,
        latest_cursor_sha256: str | None,
    ) -> None:
        if (not is_name(stream_id) or not is_name(epoch_id)
                or not is_wire_integer(next_ordinal) or next_ordinal < 0
                or (latest_cursor_sha256 is not None
                    and not is_sha256(latest_cursor_sha256))
                or (next_ordinal == 0) != (latest_cursor_sha256 is None)):
            _invalid("PROJECTION_FRONTIER_INVALID")
        try:
            with self._connect() as db:
                self._record_frontier(
                    db, stream_id, epoch_id, next_ordinal, latest_cursor_sha256)
                db.commit()
        except sqlite3.Error:
            _invalid("PROJECTION_WRITE_FAILED_REBUILD_REQUIRED")

    def frontier_status(
        self, stream_id: str, epoch_id: str, next_ordinal: int,
        latest_cursor_sha256: str | None,
    ) -> ProjectionFrontierStatus:
        if (not is_name(stream_id) or not is_name(epoch_id)
                or not is_wire_integer(next_ordinal) or next_ordinal < 0
                or (latest_cursor_sha256 is not None
                    and not is_sha256(latest_cursor_sha256))
                or (next_ordinal == 0) != (latest_cursor_sha256 is None)):
            _invalid("PROJECTION_FRONTIER_INVALID")
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM event_frontiers WHERE stream_id = ?", (stream_id,),
            ).fetchone()
        if row is None:
            state = ProjectionFrontierState.EMPTY
            projected_epoch = projected_next = None
        else:
            projected_epoch = row["epoch_id"]
            projected_next = row["next_ordinal"]
            if projected_epoch != epoch_id or projected_next < next_ordinal:
                state = ProjectionFrontierState.STALE
            elif (projected_next > next_ordinal
                  or row["latest_cursor_sha256"] != latest_cursor_sha256):
                state = ProjectionFrontierState.DIVERGED
            else:
                state = ProjectionFrontierState.CURRENT
        return ProjectionFrontierStatus(
            state, stream_id, projected_epoch, projected_next,
            epoch_id, next_ordinal,
        )

    def catalog(self) -> MissionControlQueryCatalog:
        try:
            with self._connect() as db:
                rows = tuple(db.execute(
                    """SELECT payload_json, payload_sha256 FROM record_revisions
                    WHERE active = 1 ORDER BY record_id"""))
            return MissionControlQueryCatalog(self._decode_rows(rows))
        except sqlite3.Error:
            _invalid("PROJECTION_READ_FAILED_REBUILD_REQUIRED")

    def revisions(self, record_id: str) -> tuple[WireRecord, ...]:
        try:
            with self._connect() as db:
                rows = tuple(db.execute(
                    """SELECT payload_json, payload_sha256 FROM record_revisions
                    WHERE record_id = ? ORDER BY revision_id""", (record_id,)))
            return tuple(self._decode_rows(rows))
        except sqlite3.Error:
            _invalid("PROJECTION_READ_FAILED_REBUILD_REQUIRED")

    @staticmethod
    def _decode_rows(rows) -> tuple[WireRecord, ...]:
        decoded = []
        for row in rows:
            payload_json = row["payload_json"]
            if type(payload_json) is not str:
                _invalid("PROJECTION_ROW_CORRUPT_REBUILD_REQUIRED")
            payload = payload_json.encode("utf-8")
            if hashlib.sha256(payload).hexdigest() != row["payload_sha256"]:
                _invalid("PROJECTION_ROW_DIGEST_MISMATCH_REBUILD_REQUIRED")
            try:
                decoded.append(decode_json(payload))
            except MissionControlContractError:
                _invalid("PROJECTION_ROW_CORRUPT_REBUILD_REQUIRED")
        return tuple(decoded)

    @staticmethod
    def _stats(db: sqlite3.Connection) -> ProjectionStats:
        active = db.execute(
            "SELECT COUNT(*) FROM record_revisions WHERE active = 1").fetchone()[0]
        revisions = db.execute("SELECT COUNT(*) FROM record_revisions").fetchone()[0]
        references = db.execute("SELECT COUNT(*) FROM record_refs").fetchone()[0]
        events = db.execute(
            "SELECT COUNT(*) FROM record_revisions WHERE schema_version = ?",
            (EventEnvelope.SCHEMA,),
        ).fetchone()[0]
        return ProjectionStats(active, revisions, references, events)

    def stats(self) -> ProjectionStats:
        try:
            with self._connect() as db:
                return self._stats(db)
        except sqlite3.Error:
            _invalid("PROJECTION_READ_FAILED_REBUILD_REQUIRED")
