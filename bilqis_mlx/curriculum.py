"""Internal, fail-closed developmental-grade contract.

A capability is a bounded semantic skill; a letter grade is a curriculum tranche
comprising 6-9 capabilities of comparable difficulty. Never infer executable
learning evidence from a historical G-number or from an attractive title.

The verified semantic source and generator are required *before* a grade can be
activated for neural training. This module cannot invent a question or gold.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re


BINARY = ("FALSE", "TRUE")
INT_0_3 = ("0", "1", "2", "3")
GRADE_IDS = tuple(chr(i) for i in range(ord("A"), ord("Z") + 1))


@dataclass(frozen=True)
class AnswerFamily:
    kind: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class Capability:
    id: str
    difficulty: str
    source_anchor: str
    taught_roots: tuple[str, ...]
    examined_roots: tuple[str, ...]
    prerequisites: tuple[str, ...]
    composed_of: tuple[str, ...]
    answer_families: tuple[AnswerFamily, ...]
    lesson_generator: str | None = None
    independent_oracle: str | None = None


@dataclass(frozen=True)
class Grade:
    id: str
    capabilities: tuple[Capability, ...]


@dataclass(frozen=True)
class Course:
    grades: tuple[Grade, ...]
    version: str
    source_attestation_sha256: str | None = None
    assessment_manifest_sha256: str | None = None

    @property
    def capability_map(self) -> dict[str, Capability]:
        return {cap.id: cap for grade in self.grades for cap in grade.capabilities}

    def digest(self) -> str:
        from dataclasses import asdict
        value = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @property
    def executable(self) -> bool:
        """Deny execution until every family has an attested lesson and oracle."""
        validate(self)
        hashes = (self.source_attestation_sha256, self.assessment_manifest_sha256)
        certified = all(isinstance(h, str) and len(h) == 64 and
                        all(x in "0123456789abcdef" for x in h) for h in hashes)
        return bool(certified and all(c.lesson_generator and c.independent_oracle and
                   c.source_anchor.startswith(("repo:", "https://"))
                   for grade in self.grades for c in grade.capabilities))


def validate(course: Course) -> None:
    """Validate *structure*, not independently assert that cited sources are true."""
    if not course.version or not course.grades:
        raise ValueError("COURSE_VERSION_OR_GRADES_MISSING")
    all_ids: set[str] = set()
    past_roots: set[str] = set()
    for idx, grade in enumerate(course.grades):
        if idx >= len(GRADE_IDS) or grade.id != GRADE_IDS[idx]:
            raise ValueError("NONSEQUENTIAL_LETTER_GRADE")
        if not 6 <= len(grade.capabilities) <= 9:
            raise ValueError("GRADE_CAPABILITY_COUNT_OUTSIDE_SIX_TO_NINE")
        difficulties = {cap.difficulty for cap in grade.capabilities}
        if len(difficulties) != 1:
            raise ValueError("GRADE_MIXES_DIFFICULTY_LEVELS")
        seen_roots_in_grade: set[str] = set()
        grade_ids: set[str] = set()
        for cap in grade.capabilities:
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]+", cap.id) or cap.id in all_ids or cap.id in grade_ids:
                raise ValueError("INVALID_OR_DUPLICATE_CAPABILITY_ID")
            if not cap.source_anchor or not cap.taught_roots or not cap.examined_roots:
                raise ValueError("CAPABILITY_ROOT_OR_PROVENANCE_MISSING")
            if not set(cap.examined_roots) <= set(cap.taught_roots) | past_roots:
                raise ValueError("UNTAUGHT_ROOT_IN_EXAM")
            if len(set(cap.taught_roots)) != len(cap.taught_roots):
                raise ValueError("DUPLICATE_TAUGHT_ROOT")
            if any(pre not in all_ids for pre in cap.prerequisites):
                raise ValueError("CAPABILITY_PREREQUISITE_NOT_MASTERED_IN_EARLIER_GRADE")
            if cap.composed_of:
                if len(cap.composed_of) < 2 or not set(cap.composed_of) <= set(cap.prerequisites):
                    raise ValueError("COMPOSITION_CONSTITUENTS_NOT_PREVIOUSLY_MASTERED")
            kinds = {family.kind for family in cap.answer_families}
            if "binary" not in kinds or len(kinds) != len(cap.answer_families):
                raise ValueError("MISSING_OR_DUPLICATE_BINARY_ANSWER_FAMILY")
            for family in cap.answer_families:
                if (not family.kind or not 2 <= len(family.values) <= 32 or
                        len(set(family.values)) != len(family.values)):
                    raise ValueError("INVALID_BOUNDED_ANSWER_FAMILY")
                if family.kind == "binary" and family.values != BINARY:
                    raise ValueError("INVALID_BINARY_ANSWER_LABELS")
                if family.kind == "integer_0_3" and family.values != INT_0_3:
                    raise ValueError("INVALID_INTEGER_0_3_ANSWER_LABELS")
            grade_ids.add(cap.id)
            seen_roots_in_grade.update(cap.taught_roots)
        all_ids.update(grade_ids)
        past_roots.update(seen_roots_in_grade)


@dataclass(frozen=True)
class ExamItem:
    capability: str
    answer_kind: str
    gold: str
    roots: tuple[str, ...]
    constituents: tuple[str, ...]
    oracle_ref: str
    item_id: str


def validate_exam_item(course: Course, active_grade: str, item: ExamItem,
                       *, mastered_grade_ids: tuple[str, ...] = ()) -> None:
    """Validate test admission, not the oracle's mathematical calculation.

    An independently verified oracle must still check gold answers at runtime.
    """
    validate(course)
    grades = {g.id: g for g in course.grades}
    if active_grade not in grades:
        raise ValueError("UNKNOWN_EXAM_GRADE")
    cap = next((c for c in grades[active_grade].capabilities
                if c.id == item.capability), None)
    if cap is None:
        raise ValueError("EXAM_CAPABILITY_NOT_IN_ACTIVE_GRADE")
    allowed = {f.kind: f.values for f in cap.answer_families}
    if item.answer_kind not in allowed or item.gold not in allowed[item.answer_kind]:
        raise ValueError("EXAM_ANSWER_OUTSIDE_CAPABILITY_ABI")
    active_idx = GRADE_IDS.index(active_grade)
    earlier = {c.id: g.id for g in course.grades[:active_idx]
               for c in g.capabilities}
    prior_roots = {root for g in course.grades[:active_idx]
                   for c in g.capabilities for root in c.taught_roots}
    if not item.roots or not set(item.roots) <= prior_roots | set(cap.taught_roots):
        raise ValueError("EXAM_USES_UNTAUGHT_SEMANTIC_ROOT")
    if (not item.oracle_ref or not item.item_id or
            item.oracle_ref != cap.independent_oracle):
        raise ValueError("EXAM_HAS_NO_INDEPENDENT_ORACLE_IDENTITY")
    if cap.prerequisites and any(earlier.get(c) not in mastered_grade_ids
                                  for c in cap.prerequisites):
        raise ValueError("EXAM_PREREQUISITE_GRADE_NOT_PASSED")
    if cap.composed_of:
        if not set(cap.composed_of) <= set(item.constituents):
            raise ValueError("EXAM_MISSING_DECOMPOSED_CONSTITUENTS")
    if item.constituents:
        if any(c not in earlier for c in item.constituents):
            raise ValueError("COMPOSED_EXAM_UNMASTERED_EARLIER_CONSTITUENT")
        if any(earlier[c] not in mastered_grade_ids for c in item.constituents):
            raise ValueError("COMPOSED_EXAM_PREREQUISITE_GRADE_NOT_PASSED")
