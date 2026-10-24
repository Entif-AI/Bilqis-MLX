"""Execution-neutral curriculum definition and separately sealed source bindings.

The legacy ``Course`` type mixes semantic/pedagogical declarations with live
release bindings such as generator IDs, oracle IDs and assessment seals. This
module is the target split: curriculum meaning is stable while source/provider
implementations can evolve through FactoryRelease without rewriting the AST.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from ..curriculum import AnswerFamily, Course, GRADE_IDS, validate as validate_course


V2_GRADE_CAPABILITY_MAX = 12


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    difficulty: str
    taught_roots: tuple[str, ...]
    examined_roots: tuple[str, ...]
    prerequisites: tuple[str, ...]
    composed_of: tuple[str, ...]
    answer_families: tuple[AnswerFamily, ...]


@dataclass(frozen=True)
class GradeSpec:
    grade_id: str
    capabilities: tuple[CapabilitySpec, ...]
    exam_item_counts: tuple[tuple[str, int], ...]
    teaching_stages: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class CurriculumDefinition:
    curriculum_id: str
    grades: tuple[GradeSpec, ...]
    program_complete: bool = False

    @property
    def capability_map(self) -> dict[str, CapabilitySpec]:
        return {
            capability.capability_id: capability
            for grade in self.grades for capability in grade.capabilities
        }

    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class CapabilitySourceBinding:
    capability_id: str
    source_anchor: str
    generator_id: str
    oracle_id: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (
                self.capability_id, self.source_anchor,
                self.generator_id, self.oracle_id)):
            raise ValueError("FACTORY_SOURCE_BINDING_IDENTITY_INVALID")


@dataclass(frozen=True)
class SourceBindingSet:
    bindings: tuple[CapabilitySourceBinding, ...]
    source_attestation_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.source_attestation_sha256 is not None and (
                not isinstance(self.source_attestation_sha256, str) or
                len(self.source_attestation_sha256) != 64 or
                any(c not in "0123456789abcdef"
                    for c in self.source_attestation_sha256)):
            raise ValueError("FACTORY_SOURCE_ATTESTATION_DIGEST_INVALID")

    @property
    def by_capability(self) -> dict[str, CapabilitySourceBinding]:
        return {item.capability_id: item for item in self.bindings}

    def digest(self) -> str:
        return _digest(asdict(self))


def validate_curriculum_definition(
        curriculum: CurriculumDefinition, *, answer_kinds: tuple[str, ...]) -> None:
    if (not isinstance(curriculum, CurriculumDefinition) or
            not curriculum.curriculum_id or not curriculum.grades or
            type(curriculum.program_complete) is not bool):
        raise ValueError("FACTORY_CURRICULUM_DEFINITION_INVALID")
    allowed_answers = set(answer_kinds)
    if not allowed_answers:
        raise ValueError("FACTORY_CURRICULUM_ANSWER_AUTHORITY_EMPTY")
    all_ids = set()
    previous_roots = set()
    seen_grades = set()
    for grade in curriculum.grades:
        if (grade.grade_id not in GRADE_IDS or grade.grade_id in seen_grades or
                not 1 <= len(grade.capabilities) <= V2_GRADE_CAPABILITY_MAX):
            raise ValueError("FACTORY_CURRICULUM_GRADE_INVALID")
        seen_grades.add(grade.grade_id)
        ids = tuple(cap.capability_id for cap in grade.capabilities)
        if (len(set(ids)) != len(ids) or
                tuple(name for name, _ in grade.exam_item_counts) != ids or
                any(type(count) is not int or count < 1
                    for _, count in grade.exam_item_counts)):
            raise ValueError("FACTORY_CURRICULUM_GRADE_INVENTORY_INVALID")
        if grade.teaching_stages and (
                any(not stage for stage in grade.teaching_stages) or
                tuple(cap for stage in grade.teaching_stages for cap in stage) != ids):
            raise ValueError("FACTORY_CURRICULUM_STAGES_INVALID")
        stage_by_capability = {
            cap: index for index, stage in enumerate(grade.teaching_stages)
            for cap in stage
        }
        grade_ids = set()
        grade_roots = set()
        difficulties = {cap.difficulty for cap in grade.capabilities}
        if len(difficulties) != 1:
            raise ValueError("FACTORY_CURRICULUM_GRADE_DIFFICULTY_DRIFT")
        for capability in grade.capabilities:
            if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]+", capability.capability_id) or
                    capability.capability_id in all_ids or
                    not capability.taught_roots or
                    not capability.examined_roots):
                raise ValueError("FACTORY_CURRICULUM_CAPABILITY_INVALID")
            if not set(capability.examined_roots) <= (
                    set(capability.taught_roots) | previous_roots):
                raise ValueError("FACTORY_CURRICULUM_UNTAUGHT_EXAM_ROOT")
            if len(set(capability.taught_roots)) != len(capability.taught_roots):
                raise ValueError("FACTORY_CURRICULUM_DUPLICATE_ROOT")
            for prerequisite in capability.prerequisites:
                earlier_stage = (
                    prerequisite in grade_ids and grade.teaching_stages and
                    stage_by_capability.get(prerequisite, -1) <
                    stage_by_capability.get(capability.capability_id, -1))
                if prerequisite not in all_ids and not earlier_stage:
                    raise ValueError("FACTORY_CURRICULUM_PREREQUISITE_NOT_EARLIER")
            if capability.composed_of and (
                    len(capability.composed_of) < 2 or
                    not set(capability.composed_of) <= set(capability.prerequisites)):
                raise ValueError("FACTORY_CURRICULUM_COMPOSITION_INVALID")
            kinds = tuple(family.kind for family in capability.answer_families)
            if (not kinds or len(set(kinds)) != len(kinds) or
                    not set(kinds) <= allowed_answers):
                raise ValueError("FACTORY_CURRICULUM_ANSWER_MODALITY_INVALID")
            for family in capability.answer_families:
                if (not family.kind or not 2 <= len(family.values) <= 32 or
                        len(set(family.values)) != len(family.values) or
                        any(not isinstance(value, str) or not value
                            for value in family.values)):
                    raise ValueError("FACTORY_CURRICULUM_ANSWER_FAMILY_INVALID")
            grade_ids.add(capability.capability_id)
            grade_roots.update(capability.taught_roots)
        all_ids.update(grade_ids)
        previous_roots.update(grade_roots)


def validate_source_bindings(
        curriculum: CurriculumDefinition, bindings: SourceBindingSet) -> None:
    if not isinstance(bindings, SourceBindingSet):
        raise TypeError("FACTORY_SOURCE_BINDINGS_REQUIRED")
    expected = tuple(curriculum.capability_map)
    observed = tuple(item.capability_id for item in bindings.bindings)
    if expected != observed or len(set(observed)) != len(observed):
        raise ValueError("FACTORY_SOURCE_BINDINGS_SCOPE_DRIFT")


def from_legacy_course(
        course: Course, *, answer_kinds: tuple[str, ...] | None = None
        ) -> tuple[CurriculumDefinition, SourceBindingSet]:
    """Compatibility projection. New declarations should not originate here."""
    if not isinstance(course, Course):
        raise TypeError("FACTORY_LEGACY_COURSE_REQUIRED")
    validate_course(course, answer_kinds=answer_kinds)
    grades = []
    bindings = []
    for grade in course.grades:
        capabilities = []
        for capability in grade.capabilities:
            capabilities.append(CapabilitySpec(
                capability.id,
                capability.difficulty,
                capability.taught_roots,
                capability.examined_roots,
                capability.prerequisites,
                capability.composed_of,
                capability.answer_families,
            ))
            if not capability.lesson_generator or not capability.independent_oracle:
                raise ValueError("FACTORY_LEGACY_COURSE_SOURCE_BINDING_MISSING")
            bindings.append(CapabilitySourceBinding(
                capability.id, capability.source_anchor,
                capability.lesson_generator,
                capability.independent_oracle))
        grades.append(GradeSpec(
            grade.id, tuple(capabilities), grade.exam_item_counts,
            grade.teaching_stages))
    return (
        CurriculumDefinition(
            "bilqis.curriculum.semantic/v1", tuple(grades),
            course.program_complete),
        SourceBindingSet(
            tuple(bindings), course.source_attestation_sha256),
    )
