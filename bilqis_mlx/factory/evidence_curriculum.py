"""A10.1 BRAVO evidence-to-lesson compiler over provenance-safe records."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_FIXTURE, BamfEvidenceSnapshot, EvidenceDerivation, EvidenceFrame,
    EvidenceRecord, EvidenceRights, SourceSpan, source_family_id, verification_state,
)


class EvidenceLessonStatus(str, Enum):
    SOURCE_HELD = "SOURCE_HELD"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


@dataclass(frozen=True)
class EvidenceHold:
    status: EvidenceLessonStatus
    reason: str
    record_id: str


@dataclass(frozen=True)
class EvidenceLesson:
    lesson_id: str
    record_id: str
    source_family_id: str
    source_span: SourceSpan
    frame: EvidenceFrame
    question: str
    gold: str
    rendered: str
    task_modality: str
    positive_family: str
    negative_family: str
    checker_id: str
    prerequisite_capabilities: tuple[str, ...]
    rights: EvidenceRights
    derivation: EvidenceDerivation | None = None

    def check(self) -> bool:
        if self.frame.record_id != self.record_id or self.rights.regime != PUBLIC_FIXTURE:
            return False
        if self.question == "What category?":
            return self.gold == self.frame.category_ref
        if self.question == "Planned or completed?":
            return self.gold == self.frame.status
        if self.question == "What reported duration?":
            expected = "UNKNOWN" if self.frame.reported_decimal is None else self.frame.reported_decimal
            return self.gold == expected
        if self.question == "Convert the reported duration to minutes.":
            if self.frame.reported_decimal is None:
                return self.gold == "UNKNOWN" and self.derivation is None
            return (self.derivation is not None
                    and self.derivation.output_value == self.gold
                    and self.derivation.operator_id == "duration.hour-to-minute/v1")
        return False


@dataclass(frozen=True)
class LessonCandidateSet:
    snapshot_id: str
    source_byte_digest: str
    interpretation_revision: str
    semantic_release: str
    rights: EvidenceRights
    lessons: tuple[EvidenceLesson, ...]
    holds: tuple[EvidenceHold, ...]


@dataclass(frozen=True)
class EvidenceSplitReceipt:
    train_record_ids: tuple[str, ...]
    heldout_record_ids: tuple[str, ...]
    train_family_ids: tuple[str, ...]
    heldout_family_ids: tuple[str, ...]
    receipt_sha256: str


def _minutes(decimal: str) -> tuple[str, EvidenceDerivation]:
    try:
        value = Decimal(decimal)
    except InvalidOperation:
        _fail("BAMF_EVIDENCE_DURATION_INVALID")
    minutes = value * Decimal(60)
    normalized = format(minutes.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    normalized = normalized or "0"
    return normalized, EvidenceDerivation(
        "duration.hour-to-minute/v1", decimal, "reported-unit", normalized, "minute")


def _render(record: EvidenceRecord) -> str:
    decimal = record.reported_value.decimal
    if decimal is None:
        return f"{record.actor_ref} reported {record.category_label}; duration is unknown."
    if record.status == "COMPLETED":
        return f"{record.actor_ref} completed {record.category_label} for {decimal} {record.unit_label}."
    if record.status == "PLANNED":
        return f"{record.actor_ref} plans {record.category_label} for {decimal} {record.unit_label}."
    return f"{record.actor_ref} reported {record.category_label} for {decimal} {record.unit_label}."


def _frame(snapshot: BamfEvidenceSnapshot, record: EvidenceRecord) -> EvidenceFrame:
    return EvidenceFrame(
        record_id=record.record_id,
        actor_ref=record.actor_ref,
        actor_role_ref=record.agent_role_ref,
        category_ref=record.category_ref,
        status=record.status,
        reported_decimal=record.reported_value.decimal,
        reported_unit_ref=record.reported_value.unit_ref,
        event_time=record.event_time,
        alternatives=record.alternatives,
        verification_state=verification_state(record),
        source_digest=snapshot.source_byte_digest,
        interpretation_revision=snapshot.interpretation_revision,
        semantic_release=snapshot.semantic_release,
        source_family_id=source_family_id(snapshot, record),
    )


def _lessons(snapshot: BamfEvidenceSnapshot, record: EvidenceRecord) -> tuple[EvidenceLesson, ...]:
    frame = _frame(snapshot, record)
    rendered = _render(record)
    family = frame.source_family_id
    common = dict(
        record_id=record.record_id,
        source_family_id=family,
        source_span=record.source_span,
        frame=frame,
        rendered=rendered,
        task_modality="typed-evidence-reconstruction/v1",
        positive_family="source-adjudicated-positive/v1",
        negative_family="source-authorized-contrast/v1",
        checker_id="bilqis.evidence-exact-checker/v1",
        prerequisite_capabilities=("semantic.role.AGENT", "semantic.status", "semantic.duration"),
        rights=snapshot.rights,
    )
    rows = [
        ("category", "What category?", record.category_ref, None),
        ("status", "Planned or completed?", record.status, None),
        ("reported-duration", "What reported duration?",
         "UNKNOWN" if record.reported_value.decimal is None else record.reported_value.decimal, None),
    ]
    if record.reported_value.decimal is None:
        rows.append(("minutes", "Convert the reported duration to minutes.", "UNKNOWN", None))
    else:
        value, derivation = _minutes(record.reported_value.decimal)
        derivation = EvidenceDerivation(
            derivation.operator_id, derivation.input_value,
            record.reported_value.unit_ref, derivation.output_value, derivation.output_unit)
        rows.append(("minutes", "Convert the reported duration to minutes.", value, derivation))
    return tuple(EvidenceLesson(
        lesson_id=f"{record.record_id}:{snapshot.interpretation_revision}:{suffix}", question=question, gold=gold,
        derivation=derivation, **common) for suffix, question, gold, derivation in rows)


def compile_evidence_lessons(
    adjudicated_snapshot: BamfEvidenceSnapshot,
    source_rights: EvidenceRights,
    semantic_release: str,
) -> LessonCandidateSet:
    """Compile only currently qualified source evidence into deterministic lessons."""
    if (type(adjudicated_snapshot) is not BamfEvidenceSnapshot
            or type(source_rights) is not EvidenceRights
            or source_rights != adjudicated_snapshot.rights
            or semantic_release != adjudicated_snapshot.semantic_release):
        _fail("BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH")
    if (source_rights.regime != PUBLIC_FIXTURE or not source_rights.allowed_training
            or not source_rights.public_export_allowed):
        holds = tuple(EvidenceHold(
            EvidenceLessonStatus.SOURCE_HELD,
            "RIGHTS_NOT_PUBLIC_TRAINING_QUALIFIED", record.record_id)
            for record in adjudicated_snapshot.records)
        return LessonCandidateSet(
            adjudicated_snapshot.snapshot_id,
            adjudicated_snapshot.source_byte_digest,
            adjudicated_snapshot.interpretation_revision,
            semantic_release, source_rights, (), holds)
    qualified = tuple(record for record in adjudicated_snapshot.records
                      if record.adjudication_ref is not None)
    record_holds = tuple(EvidenceHold(
        EvidenceLessonStatus.SOURCE_HELD, "SOURCE_UNADJUDICATED", record.record_id)
        for record in adjudicated_snapshot.records if record.adjudication_ref is None)
    lessons = tuple(
        lesson for record in qualified
        for lesson in _lessons(adjudicated_snapshot, record))
    return LessonCandidateSet(
        adjudicated_snapshot.snapshot_id,
        adjudicated_snapshot.source_byte_digest,
        adjudicated_snapshot.interpretation_revision,
        semantic_release, source_rights, lessons, record_holds)


def split_evidence_families(
    candidates: LessonCandidateSet, *,
    train_record_ids: tuple[str, ...],
    heldout_record_ids: tuple[str, ...],
) -> EvidenceSplitReceipt:
    """Prove that one underlying source episode cannot straddle an independent split."""
    if set(train_record_ids) & set(heldout_record_ids):
        _fail("BAMF_EVIDENCE_SPLIT_RECORD_OVERLAP")
    by_record: dict[str, str] = {}
    for lesson in candidates.lessons:
        prior = by_record.setdefault(lesson.record_id, lesson.source_family_id)
        if prior != lesson.source_family_id:
            _fail("BAMF_EVIDENCE_SPLIT_FAMILY_DRIFT")
    if any(item not in by_record for item in (*train_record_ids, *heldout_record_ids)):
        _fail("BAMF_EVIDENCE_SPLIT_RECORD_UNKNOWN")
    train = tuple(sorted({by_record[item] for item in train_record_ids}))
    held = tuple(sorted({by_record[item] for item in heldout_record_ids}))
    if set(train) & set(held):
        _fail("BAMF_EVIDENCE_SPLIT_WITNESS_NOT_INDEPENDENT")
    payload = repr((train_record_ids, heldout_record_ids, train, held)).encode("utf-8")
    return EvidenceSplitReceipt(
        tuple(train_record_ids), tuple(heldout_record_ids), train, held,
        sha256(payload).hexdigest())
