"""Structural extraction from atlas_temporal_revalidation.py; behavior preserved."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from ..errors import ErrorBus, SCHOOL
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef

TEMPORAL_EVENT_SCHEMA = "bilqis.c09.temporal-event/v1"

TEMPORAL_PROJECTION_SCHEMA = "bilqis.c09.temporal-projection/v1"

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")

def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_REVALIDATION.INVALID, reason=reason)

def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)

def _digest(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))

def _time(value: object) -> bool:
    return type(value) is int and value >= 0

def _names(value: object, *, sorted_names: bool = True) -> bool:
    return (isinstance(value, tuple) and bool(value)
            and all(_name(item) for item in value)
            and len(value) == len(set(value))
            and (not sorted_names or value == tuple(sorted(value))))

def _hash(value: object) -> str:
    return hashlib.sha256(
        (json.dumps(value, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ).hexdigest()

class TemporalEventKind(str, Enum):
    PLANNED = "PLANNED"
    OBSERVED = "OBSERVED"
    EXPLICIT_NONOCCURRENCE = "EXPLICIT_NONOCCURRENCE"
    CORRECTION = "CORRECTION"

class TemporalStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    PLANNED = "PLANNED"
    MISSING_EXPECTED_REPORT = "MISSING_EXPECTED_REPORT"
    OBSERVED = "OBSERVED"
    EXPLICIT_NONOCCURRENCE = "EXPLICIT_NONOCCURRENCE"
    CORRECTED = "CORRECTED"
    CONFLICTING_ALTERNATIVES = "CONFLICTING_ALTERNATIVES"

@dataclass(frozen=True)
class TemporalEvent:
    event_id: str
    actor_id: str
    kind: TemporalEventKind
    fact_digest: str
    source_receipt_sha256: str
    source_time: int
    effective_from: int
    effective_until: int | None
    observed_at: int
    recorded_at: int
    expected_report_by: int | None = None
    supersedes_event_id: str | None = None
    schema_version: str = TEMPORAL_EVENT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (self.event_id, self.actor_id))
                or not isinstance(self.kind, TemporalEventKind)
                or not _digest(self.fact_digest)
                or not _digest(self.source_receipt_sha256)
                or not all(_time(item) for item in (
                    self.source_time, self.effective_from,
                    self.observed_at, self.recorded_at))
                or (self.kind is not TemporalEventKind.PLANNED
                    and self.source_time > self.observed_at)
                or self.recorded_at < self.observed_at
                or (self.effective_until is not None
                    and (not _time(self.effective_until)
                         or self.effective_until <= self.effective_from))
                or (self.expected_report_by is not None
                    and (self.kind is not TemporalEventKind.PLANNED
                         or not _time(self.expected_report_by)
                         or self.expected_report_by < self.effective_from))
                or (self.supersedes_event_id is not None
                    and (not _name(self.supersedes_event_id)
                         or self.supersedes_event_id == self.event_id))
                or self.schema_version != TEMPORAL_EVENT_SCHEMA):
            _invalid("BAMF_C09_TEMPORAL_EVENT_INVALID")

@dataclass(frozen=True)
class TemporalProjection:
    actor_id: str
    as_of: int
    status: TemporalStatus
    source_event_ids: tuple[str, ...]
    fact_digest: str | None
    time_dependency: DependencyRef
    schema_version: str = TEMPORAL_PROJECTION_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.actor_id) or not _time(self.as_of)
                or not isinstance(self.status, TemporalStatus)
                or not isinstance(self.source_event_ids, tuple)
                or self.source_event_ids != tuple(
                    sorted(set(self.source_event_ids)))
                or (self.fact_digest is not None
                    and not _digest(self.fact_digest))
                or not isinstance(self.time_dependency, DependencyRef)
                or self.time_dependency.kind is not DependencyKind.TIME
                or self.schema_version != TEMPORAL_PROJECTION_SCHEMA):
            _invalid("BAMF_C09_TEMPORAL_PROJECTION_INVALID")
