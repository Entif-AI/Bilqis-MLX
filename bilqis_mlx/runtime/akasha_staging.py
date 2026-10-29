"""C10.3 private-safe staging census, bounded queries and atomic promotion.

This is a local projection ledger. Actual SKOS graph writes and external
publication remain separate source-authorized integration gates.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from ..errors import ErrorBus, SCHOOL
from .akasha_outbox import AkashaEventKind, OWNER_FIXTURE_KINDS
from .bamf_projection import BamfProjectionEvent, ProjectionDomainContract


PUBLIC_EVENT_SCHEMA = "bilqis.c10.public-event/v1"
STAGING_PROJECTION_SCHEMA = "bilqis.c10.staging-projection/v1"
VERIFIED_STAGE_SCHEMA = "bilqis.c10.verified-stage/v1"
PROMOTION_RECEIPT_SCHEMA = "bilqis.c10.promotion-receipt/v1"
MAX_PUBLIC_QUERY_LIMIT = 100
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_AKASHA.INVALID, reason=reason)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _time(value: object) -> bool:
    return type(value) is int and value >= 0


def _canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PublicEvent:
    event_id: str
    kind: AkashaEventKind
    subject_digest: str
    payload_digest: str
    source_receipt_sha256: str
    release_digest: str
    model_digest: str
    evaluator_digest: str
    rights_digest: str
    source_time: int
    effective_time: int
    observed_at: int
    recorded_at: int
    schema_version: str = PUBLIC_EVENT_SCHEMA

    def __post_init__(self) -> None:
        if self.kind in OWNER_FIXTURE_KINDS:
            _invalid("BAMF_C10_FIXTURE_PUBLIC_SCHEMA_REQUIRED")
        if (not isinstance(self.kind, AkashaEventKind)
                or not all(_sha(value) for value in (
                    self.event_id, self.subject_digest,
                    self.payload_digest, self.source_receipt_sha256,
                    self.release_digest, self.model_digest,
                    self.evaluator_digest, self.rights_digest))
                or not all(_time(value) for value in (
                    self.source_time, self.effective_time,
                    self.observed_at, self.recorded_at))
                or self.observed_at > self.recorded_at
                or self.schema_version != PUBLIC_EVENT_SCHEMA):
            _invalid("BAMF_C10_PUBLIC_EVENT_INVALID")


def _public_event(event: BamfProjectionEvent) -> PublicEvent:
    return PublicEvent(
        event_id=event.event.event_id,
        kind=event.event.kind,
        subject_digest=_digest(event.event.subject_id),
        payload_digest=event.event.payload_digest,
        source_receipt_sha256=event.event.source_receipt_sha256,
        release_digest=event.release_digest,
        model_digest=event.model_digest,
        evaluator_digest=event.evaluator_digest,
        rights_digest=event.rights_digest,
        source_time=event.event.source_time,
        effective_time=event.event.effective_time,
        observed_at=event.event.observed_at,
        recorded_at=event.event.recorded_at,
    )


def _public_payload(event: PublicEvent) -> dict:
    return {**asdict(event), "kind": event.kind.value}


@dataclass(frozen=True)
class StagingProjection:
    public_events: tuple[PublicEvent, ...]
    census: tuple[tuple[str, int], ...]
    domain_digest: str
    stage_digest: str
    schema_version: str = STAGING_PROJECTION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.public_events, tuple)
                or any(not isinstance(item, PublicEvent)
                       for item in self.public_events)
                or self.public_events != tuple(sorted(
                    self.public_events, key=lambda item: item.event_id))
                or len({item.event_id for item in self.public_events})
                != len(self.public_events)
                or not isinstance(self.census, tuple)
                or not _sha(self.domain_digest)
                or not _sha(self.stage_digest)
                or self.schema_version != STAGING_PROJECTION_SCHEMA):
            _invalid("BAMF_C10_STAGING_PROJECTION_INVALID")
        counts = {}
        for event in self.public_events:
            counts[event.kind.value] = counts.get(event.kind.value, 0) + 1
        if self.census != tuple(sorted(counts.items())):
            _invalid("BAMF_C10_STAGING_CENSUS_DRIFT")
        if self.stage_digest != _digest(self._identity_payload()):
            _invalid("BAMF_C10_STAGING_DIGEST_DRIFT")

    def _identity_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "domain_digest": self.domain_digest,
            "census": self.census,
            "public_events": tuple(
                _public_payload(item) for item in self.public_events),
        }

    @property
    def canonical_json(self) -> str:
        return _canonical({
            **self._identity_payload(),
            "stage_digest": self.stage_digest,
        })

    @classmethod
    def from_canonical_json(cls, value: str) -> "StagingProjection":
        try:
            raw = json.loads(value)
            events = tuple(PublicEvent(
                **{**item, "kind": AkashaEventKind(item["kind"])})
                for item in raw["public_events"])
            return cls(
                public_events=events,
                census=tuple(tuple(item) for item in raw["census"]),
                domain_digest=raw["domain_digest"],
                stage_digest=raw["stage_digest"],
                schema_version=raw["schema_version"])
        except (TypeError, ValueError, KeyError):
            _invalid("BAMF_C10_STAGING_STORED_INVALID")


def build_staging_projection(
    events: tuple[BamfProjectionEvent, ...],
    domain: ProjectionDomainContract,
) -> StagingProjection:
    if (not isinstance(events, tuple)
            or any(not isinstance(item, BamfProjectionEvent)
                   for item in events)
            or not isinstance(domain, ProjectionDomainContract)):
        _invalid("BAMF_C10_STAGING_ARGUMENT_INVALID")
    # Durable queued events cannot be rebound by a caller-created wrapper.
    from .bamf_projection import read_projection_outbox
    if domain.outbox_path.exists():
        stored = {item.event.event_id: item for item in read_projection_outbox(domain.outbox_path)}
        for event in events:
            if event.event.event_id in stored and stored[event.event.event_id] != event:
                _invalid("BAMF_C10_STAGING_DURABLE_BINDING_DRIFT")
    for event in events:
        if (event.source_id != domain.source_id
                or event.release_digest != domain.release_digest
                or event.model_digest != domain.model_digest
                or event.evaluator_digest != domain.evaluator_digest
                or event.rights_digest != domain.rights_digest
                or event.as_of != domain.as_of):
            _invalid("BAMF_C10_STAGING_DOMAIN_DRIFT")
    public = tuple(sorted(
        (_public_event(item) for item in events),
        key=lambda item: item.event_id))
    if len({item.event_id for item in public}) != len(public):
        _invalid("BAMF_C10_STAGING_EVENT_DUPLICATE")
    counts = {}
    for event in public:
        counts[event.kind.value] = counts.get(event.kind.value, 0) + 1
    census = tuple(sorted(counts.items()))
    identity = {
        "schema_version": STAGING_PROJECTION_SCHEMA,
        "domain_digest": domain.digest,
        "census": census,
        "public_events": tuple(_public_payload(item) for item in public),
    }
    return StagingProjection(
        public, census, domain.digest, _digest(identity))


def query_public_projection(
    stage: StagingProjection, *, limit: int,
    kind: AkashaEventKind | None = None, as_of: int | None = None,
) -> tuple[PublicEvent, ...]:
    if (not isinstance(stage, StagingProjection)
            or type(limit) is not int
            or not 1 <= limit <= MAX_PUBLIC_QUERY_LIMIT
            or (kind is not None and not isinstance(kind, AkashaEventKind))
            or (as_of is not None and not _time(as_of))):
        _invalid("BAMF_C10_PUBLIC_QUERY_INVALID")
    return tuple(
        event for event in stage.public_events
        if (kind is None or event.kind is kind)
        and (as_of is None or event.recorded_at <= as_of)
        and (as_of is None or event.effective_time <= as_of)
    )[:limit]


@dataclass(frozen=True)
class VerifiedStage:
    stage: StagingProjection
    census_digest: str
    bounded_query_digest: str
    proof_digest: str
    schema_version: str = VERIFIED_STAGE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.stage, StagingProjection)
                or not all(_sha(item) for item in (
                    self.census_digest, self.bounded_query_digest,
                    self.proof_digest))
                or self.census_digest != _digest(self.stage.census)
                or self.bounded_query_digest != _query_digest(self.stage)
                or self.proof_digest != _digest({
                    "stage_digest": self.stage.stage_digest,
                    "census_digest": self.census_digest,
                    "bounded_query_digest": self.bounded_query_digest,
                })
                or self.schema_version != VERIFIED_STAGE_SCHEMA):
            _invalid("BAMF_C10_STAGING_PROOF_INVALID")


def _query_digest(stage: StagingProjection) -> str:
    queries = tuple(
        (kind.value, tuple(item.event_id for item in
            query_public_projection(
                stage, limit=MAX_PUBLIC_QUERY_LIMIT, kind=kind)))
        for kind in AkashaEventKind
    )
    return _digest(queries)


def verify_staging_projection(stage: StagingProjection) -> VerifiedStage:
    if not isinstance(stage, StagingProjection):
        _invalid("BAMF_C10_STAGING_ARGUMENT_INVALID")
    census_digest = _digest(stage.census)
    query_digest = _query_digest(stage)
    return VerifiedStage(
        stage, census_digest, query_digest,
        _digest({
            "stage_digest": stage.stage_digest,
            "census_digest": census_digest,
            "bounded_query_digest": query_digest,
        }))


@dataclass(frozen=True)
class PromotionReceipt:
    previous_digest: str | None
    active_digest: str
    census_digest: str
    schema_version: str = PROMOTION_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if ((self.previous_digest is not None
             and not _sha(self.previous_digest))
                or not _sha(self.active_digest)
                or not _sha(self.census_digest)
                or self.schema_version != PROMOTION_RECEIPT_SCHEMA):
            _invalid("BAMF_C10_PROMOTION_RECEIPT_INVALID")


_STAGE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS akasha_stages (
    stage_digest TEXT PRIMARY KEY,
    canonical_json TEXT NOT NULL,
    census_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS akasha_active_pointer (
    id INTEGER PRIMARY KEY CHECK (id=1),
    stage_digest TEXT NOT NULL REFERENCES akasha_stages(stage_digest)
);
CREATE TRIGGER IF NOT EXISTS akasha_stages_no_update
BEFORE UPDATE ON akasha_stages
BEGIN SELECT RAISE(ABORT, 'AKASHA_STAGE_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_stages_no_delete
BEFORE DELETE ON akasha_stages
BEGIN SELECT RAISE(ABORT, 'AKASHA_STAGE_APPEND_ONLY'); END;
"""


@contextmanager
def _stage_connection(path: Path):
    if not isinstance(path, Path) or not path.parent.is_dir():
        _invalid("BAMF_C10_STAGING_PATH_INVALID")
    connection = sqlite3.connect(path, timeout=10)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(_STAGE_SCHEMA_SQL)
        with connection:
            yield connection
    finally:
        connection.close()


def promote_staging_projection(
    path: Path, verified: VerifiedStage,
    *, expected_active_digest: str | None,
) -> PromotionReceipt:
    if (not isinstance(verified, VerifiedStage)
            or (expected_active_digest is not None
                and not _sha(expected_active_digest))):
        _invalid("BAMF_C10_STAGING_PROMOTION_ARGUMENT_INVALID")
    stage = verified.stage
    # Recompute the proof immediately before the active-pointer transaction.
    if verified != verify_staging_projection(stage):
        _invalid("BAMF_C10_STAGING_PROOF_INVALID")
    with _stage_connection(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT stage_digest FROM akasha_active_pointer WHERE id=1"
        ).fetchone()
        previous = row[0] if row is not None else None
        if previous != expected_active_digest:
            _invalid("BAMF_C10_STAGING_POINTER_CONFLICT")
        prior = connection.execute(
            "SELECT canonical_json, census_digest FROM akasha_stages "
            "WHERE stage_digest=?", (stage.stage_digest,)).fetchone()
        if prior is None:
            connection.execute(
                "INSERT INTO akasha_stages "
                "(stage_digest, canonical_json, census_digest) "
                "VALUES (?, ?, ?)",
                (stage.stage_digest, stage.canonical_json,
                 verified.census_digest))
        elif prior != (stage.canonical_json, verified.census_digest):
            _invalid("BAMF_C10_STAGING_HISTORY_CONFLICT")
        connection.execute(
            "INSERT INTO akasha_active_pointer (id, stage_digest) "
            "VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET "
            "stage_digest=excluded.stage_digest", (stage.stage_digest,))
    return PromotionReceipt(
        previous, stage.stage_digest, verified.census_digest)


def read_staging_projection(
    path: Path, stage_digest: str,
) -> StagingProjection | None:
    if not isinstance(path, Path) or not _sha(stage_digest):
        _invalid("BAMF_C10_STAGING_DIGEST_INVALID")
    if not path.exists():
        return None
    with _stage_connection(path) as connection:
        row = connection.execute(
            "SELECT canonical_json FROM akasha_stages "
            "WHERE stage_digest=?", (stage_digest,)).fetchone()
    return (StagingProjection.from_canonical_json(row[0])
            if row is not None else None)


def read_active_projection(path: Path) -> StagingProjection | None:
    if not isinstance(path, Path):
        _invalid("BAMF_C10_STAGING_PATH_INVALID")
    if not path.exists():
        return None
    with _stage_connection(path) as connection:
        row = connection.execute(
            "SELECT stage_digest FROM akasha_active_pointer WHERE id=1"
        ).fetchone()
    return (read_staging_projection(path, row[0])
            if row is not None else None)
