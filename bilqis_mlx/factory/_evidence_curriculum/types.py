"""Typed records exposed by the A10.1 evidence-curriculum facade."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_FIXTURE, EvidenceDerivation, EvidenceFrame, EvidenceRights,
    EventTime, SourceSpan,
)


class EvidenceLessonStatus(str, Enum):
    SOURCE_HELD = "SOURCE_HELD"


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
    template_lineage: str
    checker_id: str
    prerequisite_capabilities: tuple[str, ...]
    rights: EvidenceRights
    derivation: EvidenceDerivation | None = None

    def check(self) -> bool:
        if (self.frame.record_id != self.record_id
                or self.rights.regime != PUBLIC_FIXTURE
                or self.frame.actor_role_ref != "agent"):
            return False
        if self.question == "What category?":
            return bool(self.frame.category_ref) and self.gold == self.frame.category_ref
        if self.question == "Planned or completed?":
            return (
                self.frame.status in {"PLANNED", "COMPLETED", "UNKNOWN"}
                and self.gold == self.frame.status
            )
        if self.question == "What reported duration?":
            expected = (
                "UNKNOWN" if self.frame.reported_decimal is None
                else self.frame.reported_decimal
            )
            return self.gold == expected
        if self.question == "Convert the reported duration to minutes.":
            if self.frame.reported_decimal is None:
                return self.gold == "UNKNOWN" and self.derivation is None
            try:
                value = Decimal(self.frame.reported_decimal)
            except InvalidOperation:
                return False
            if not value.is_finite() or value < 0:
                return False
            expected = format((value * Decimal(60)).normalize(), "f")
            if "." in expected:
                expected = expected.rstrip("0").rstrip(".")
            expected = expected or "0"
            return (
                self.derivation is not None
                and self.derivation.operator_id == "UNIT_CONVERT"
                and self.derivation.input_value == self.frame.reported_decimal
                and self.derivation.input_unit_ref == "h"
                and self.frame.reported_unit_ref == "h"
                and self.derivation.output_unit == "min"
                and self.gold == expected
                and self.derivation.output_value == expected
            )
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


@dataclass(frozen=True)
class TypedEvidenceReconstruction:
    record_id: str
    source_family_id: str
    template_lineage: str
    actor_ref: str
    category_ref: str
    status: str
    reported_value: str | None
    reported_unit_ref: str
    computed_values: tuple[EvidenceDerivation, ...]
    negated: bool
    event_time: EventTime
    alternatives: tuple[str, ...]
    verification_state: str


@dataclass(frozen=True)
class EvidenceChallengePlan:
    split: EvidenceSplitReceipt
    train_template_groups: tuple[tuple[str, str, tuple[str, ...]], ...]
    heldout_template_groups: tuple[tuple[str, str, tuple[str, ...]], ...]
    post_exam_teachable_lesson_ids: tuple[str, ...]
