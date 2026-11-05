"""A10.1 provenance-safe BRAVO evidence records and public-fixture boundary.

This is an application adapter contract, not a Rosetta Core type.  It preserves
source identity, source spans, interpretation revision, rights and explicit
semantic references without minting source labels as semantic authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL


SCHEMA = "BamfEvidenceSnapshot/v1"
PUBLIC_FIXTURE = "PUBLIC_FIXTURE"
PRIVATE_REAL = "PRIVATE_REAL"
UNCLASSIFIED = "UNCLASSIFIED"
PUBLIC_FIXTURE_SOURCE = "actor=actor_01; category=study; status=completed; duration=0.25 h"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_STATUS = frozenset({"PLANNED", "COMPLETED", "UNKNOWN"})
_DURATION_FIELD_PARTS = 2


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(*parts: str) -> str:
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


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


def source_family_id(snapshot: BamfEvidenceSnapshot, record: EvidenceRecord) -> str:
    """One source episode stays one family regardless of derivative adjudication labels."""
    return "evidence-family:" + _digest(
        snapshot.source_manifest_cid,
        snapshot.source_byte_digest,
        str(record.source_span.start),
        str(record.source_span.end),
    )


def verification_state(record: EvidenceRecord) -> str:
    if "EXPECTED_REPORT_MISSING" in record.alternatives:
        return "VERIFICATION_NEEDED"
    if record.alternatives:
        return "ALTERNATIVES_PRESENT"
    return "ADJUDICATED"


def parse_public_fixture_source(
    source_text: str, *, category_ref: str, hour_unit_ref: str, agent_role_ref: str,
) -> EvidenceRecord:
    """Parse the one rights-cleared literal fixture without using free-form inference."""
    expected_parts = (
        ("actor", None), ("category", None), ("status", "completed"),
        ("duration", None),
    )
    try:
        fields = {}
        for part in source_text.split("; "):
            key, value = part.split("=", 1)
            fields[key] = value
        if tuple(fields) != tuple(key for key, _ in expected_parts):
            raise ValueError
        if fields["status"] != "completed":
            raise ValueError
        duration_parts = fields["duration"].split(" ")
        if len(duration_parts) != _DURATION_FIELD_PARTS or duration_parts[1] != "h":
            raise ValueError
        Decimal(duration_parts[0])
    except (ValueError, InvalidOperation):
        _fail("BAMF_EVIDENCE_PUBLIC_FIXTURE_PARSE_INVALID")
    return EvidenceRecord(
        record_id="fixture-001", actor_ref=fields["actor"],
        source_span=SourceSpan(0, len(source_text)), category_ref=category_ref,
        category_label=fields["category"], status="COMPLETED",
        reported_value=ReportedValue(duration_parts[0], hour_unit_ref),
        unit_label=duration_parts[1], event_time=EventTime(None, None, "UTC"),
        observed_at="2026-01-01T00:00:00Z", alternatives=(),
        adjudication_ref="adjudication:fixture-001", agent_role_ref=agent_role_ref,
    )


def build_public_fixture_snapshot(
    *, semantic_release: str, category_ref: str,
    hour_unit_ref: str, agent_role_ref: str,
) -> tuple[BamfEvidenceSnapshot, EvidenceRights]:
    """Create the literal public fixture prescribed by A10 without private data."""
    rights = EvidenceRights(PUBLIC_FIXTURE, "TRAINING", True, True)
    record = parse_public_fixture_source(
        PUBLIC_FIXTURE_SOURCE, category_ref=category_ref,
        hour_unit_ref=hour_unit_ref, agent_role_ref=agent_role_ref)
    digest = sha256(PUBLIC_FIXTURE_SOURCE.encode("utf-8")).hexdigest()
    snapshot = BamfEvidenceSnapshot(
        snapshot_id="bamf-public-fixture-001",
        source_manifest_cid="public-fixture:bravo-a10-1/v1:" + digest,
        source_byte_digest=digest,
        interpretation_revision="bravo-public-fixture/v1",
        semantic_release=semantic_release,
        rights=rights,
        records=(record,),
    )
    return snapshot, rights


def public_export(candidate_set):
    """Fail closed unless the compiled set is wholly public-export qualified."""
    holds = getattr(candidate_set, "holds", ())
    if any(getattr(item, "reason", "") == "RIGHTS_NOT_PUBLIC_TRAINING_QUALIFIED"
           for item in holds):
        _fail("BAMF_EVIDENCE_PUBLIC_EXPORT_HELD")
    rights = getattr(candidate_set, "rights", None)
    if (type(rights) is not EvidenceRights or rights.regime != PUBLIC_FIXTURE
            or not rights.public_export_allowed):
        _fail("BAMF_EVIDENCE_PUBLIC_EXPORT_FORBIDDEN")
    return candidate_set
