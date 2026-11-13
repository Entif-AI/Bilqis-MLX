"""Typed A10.1 evidence adapter records and validation contracts."""
from __future__ import annotations

from dataclasses import dataclass
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL


SCHEMA = "BamfEvidenceSnapshot/v1"
PUBLIC_FIXTURE = "PUBLIC_FIXTURE"
PRIVATE_REAL = "PRIVATE_REAL"
UNCLASSIFIED = "UNCLASSIFIED"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_STATUS = frozenset({"PLANNED", "COMPLETED", "UNKNOWN"})


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _text(value: object) -> bool:
    return type(value) is str and bool(value)


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        if type(self.start) is not int or type(self.end) is not int or not 0 <= self.start < self.end:
            _fail("BAMF_EVIDENCE_SOURCE_SPAN_INVALID")


@dataclass(frozen=True)
class EvidenceRights:
    regime: str
    purpose: str
    allowed_training: bool
    public_export_allowed: bool

    def __post_init__(self) -> None:
        if (self.regime not in {PUBLIC_FIXTURE, PRIVATE_REAL, UNCLASSIFIED}
                or not _text(self.purpose)
                or type(self.allowed_training) is not bool
                or type(self.public_export_allowed) is not bool):
            _fail("BAMF_EVIDENCE_RIGHTS_INVALID")
        if self.regime != PUBLIC_FIXTURE and self.public_export_allowed:
            _fail("BAMF_EVIDENCE_PRIVATE_EXPORT_INVALID")


@dataclass(frozen=True)
class ReportedValue:
    decimal: str | None
    unit_ref: str

    def __post_init__(self) -> None:
        if ((self.decimal is not None and not _text(self.decimal))
                or not _text(self.unit_ref)):
            _fail("BAMF_EVIDENCE_REPORTED_VALUE_INVALID")


@dataclass(frozen=True)
class EventTime:
    start_iso: str | None
    end_iso: str | None
    time_zone: str

    def __post_init__(self) -> None:
        if (self.start_iso is not None and not _text(self.start_iso)) or (
                self.end_iso is not None and not _text(self.end_iso)) or not _text(self.time_zone):
            _fail("BAMF_EVIDENCE_EVENT_TIME_INVALID")


@dataclass(frozen=True)
class EvidenceRecord:
    record_id: str
    actor_ref: str
    source_span: SourceSpan
    category_ref: str
    category_label: str
    status: str
    reported_value: ReportedValue
    unit_label: str
    event_time: EventTime
    observed_at: str
    alternatives: tuple[str, ...]
    adjudication_ref: str | None
    agent_role_ref: str
    negated: bool = False

    def __post_init__(self) -> None:
        if (not all(_text(value) for value in (
                    self.record_id, self.actor_ref, self.category_ref,
                    self.category_label, self.unit_label, self.observed_at,
                    self.agent_role_ref))
                or (self.adjudication_ref is not None and not _text(self.adjudication_ref))
                or type(self.source_span) is not SourceSpan
                or self.status not in _STATUS
                or type(self.reported_value) is not ReportedValue
                or type(self.event_time) is not EventTime
                or type(self.alternatives) is not tuple
                or type(self.negated) is not bool
                or any(not _text(item) for item in self.alternatives)
                or len(set(self.alternatives)) != len(self.alternatives)):
            _fail("BAMF_EVIDENCE_RECORD_INVALID")


@dataclass(frozen=True)
class BamfEvidenceSnapshot:
    snapshot_id: str
    source_manifest_cid: str
    source_byte_digest: str
    interpretation_revision: str
    semantic_release: str
    rights: EvidenceRights
    records: tuple[EvidenceRecord, ...]
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if (not all(_text(value) for value in (
                    self.snapshot_id, self.source_manifest_cid,
                    self.interpretation_revision, self.semantic_release))
                or not _SHA.fullmatch(self.semantic_release)
                or not _SHA.fullmatch(self.source_byte_digest)
                or type(self.rights) is not EvidenceRights
                or type(self.records) is not tuple
                or any(type(item) is not EvidenceRecord for item in self.records)
                or len({item.record_id for item in self.records}) != len(self.records)
                or self.schema != SCHEMA):
            _fail("BAMF_EVIDENCE_SNAPSHOT_INVALID")


@dataclass(frozen=True)
class EvidenceFrame:
    record_id: str
    actor_ref: str
    actor_role_ref: str
    category_ref: str
    status: str
    reported_decimal: str | None
    reported_unit_ref: str
    event_time: EventTime
    alternatives: tuple[str, ...]
    negated: bool
    verification_state: str
    source_digest: str
    interpretation_revision: str
    semantic_release: str
    source_family_id: str

    @property
    def occurrence_truth(self) -> str:
        if self.status == "COMPLETED" and self.verification_state == "ADJUDICATED":
            return "FALSE" if self.negated else "TRUE"
        return "UNKNOWN"


@dataclass(frozen=True)
class EvidenceDerivation:
    operator_id: str
    input_value: str
    input_unit_ref: str
    output_value: str
    output_unit: str


@dataclass(frozen=True)
class EvidenceSemanticAuthority:
    semantic_release: str
    category_ref: str
    hour_unit_ref: str
    agent_role_ref: str
    unit_operator_id: str
    unit_operator_grant_sha256: str

    def __post_init__(self) -> None:
        if (not _SHA.fullmatch(self.semantic_release)
                or not _SHA.fullmatch(self.unit_operator_grant_sha256)
                or not all(_text(value) for value in (
                    self.category_ref, self.hour_unit_ref,
                    self.agent_role_ref, self.unit_operator_id))
                or self.hour_unit_ref != "h"
                or self.agent_role_ref != "agent"
                or self.unit_operator_id != "UNIT_CONVERT"):
            _fail("BAMF_EVIDENCE_SEMANTIC_AUTHORITY_INVALID")
