"""Typed records exposed by the A10.1 evidence-curriculum facade."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from bilqis_mlx.source_adapters.evidence_frames import (
    PRIVATE_REAL, PUBLIC_FIXTURE,
    EvidenceDerivation, EvidenceFrame, EvidenceRights,
    EventTime, SourceSpan,
)


class EvidenceLessonStatus(str, Enum):
    SOURCE_HELD = "SOURCE_HELD"


_DECIMAL_FACTOR_TWO = 2
_DECIMAL_FACTOR_FIVE = 5


def _finite_decimal(value: Fraction) -> str | None:
    numerator = value.numerator
    denominator = value.denominator
    twos = 0
    fives = 0
    while denominator % _DECIMAL_FACTOR_TWO == 0:
        denominator //= _DECIMAL_FACTOR_TWO
        twos += 1
    while denominator % _DECIMAL_FACTOR_FIVE == 0:
        denominator //= _DECIMAL_FACTOR_FIVE
        fives += 1
    if denominator != 1:
        return None
    places = max(twos, fives)
    scaled = (
        numerator
        * (_DECIMAL_FACTOR_TWO ** (places - twos))
        * (_DECIMAL_FACTOR_FIVE ** (places - fives))
    )
    sign = "-" if scaled < 0 else ""
    digits = str(abs(scaled))
    if places == 0:
        return sign + digits
    digits = digits.rjust(places + 1, "0")
    result = sign + digits[:-places] + "." + digits[-places:]
    return result.rstrip("0").rstrip(".") or "0"


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
                or self.rights.regime not in {PUBLIC_FIXTURE, PRIVATE_REAL}
                or not self.rights.allowed_training
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
                value = Fraction(self.frame.reported_decimal)
            except (ValueError, ZeroDivisionError):
                return False
            if value < 0:
                return False
            expected = _finite_decimal(value * 60)
            if expected is None:
                return False
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
