"""Typed, neural-inert contracts for the mandatory curriculum factory.

These values bind existing semantic/source authority into one executable release.
They never own model parameters, AdamW state, scheduler mutation, or teacher policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json

from ..curriculum import AnswerFamily, Capability, Course, Grade


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def _sha256(value: str, code: str) -> str:
    if (not isinstance(value, str) or len(value) != 64 or
            any(char not in "0123456789abcdef" for char in value)):
        raise ValueError(code)
    return value


class AssessmentClass(str, Enum):
    ROUTINE = "ROUTINE"
    PROMOTION = "PROMOTION"
    GENERALIZATION = "GENERALIZATION"


@dataclass(frozen=True)
class SemanticRelease:
    version: str
    course_sha256: str
    ast_sha256: str
    source_attestation_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("FACTORY_SEMANTIC_RELEASE_VERSION_REQUIRED")
        _sha256(self.course_sha256, "FACTORY_SEMANTIC_RELEASE_COURSE_DIGEST_INVALID")
        _sha256(self.ast_sha256, "FACTORY_SEMANTIC_RELEASE_AST_DIGEST_INVALID")
        _sha256(self.source_attestation_sha256,
                "FACTORY_SEMANTIC_RELEASE_SOURCE_DIGEST_INVALID")


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    grade_id: str
    prerequisites: tuple[str, ...]
    source_adapter_id: str
    oracle_id: str
    answer_kinds: tuple[str, ...]


@dataclass(frozen=True)
class GradeDefinition:
    grade_id: str
    capabilities: tuple[str, ...]
    teaching_stages: tuple[tuple[str, ...], ...]
    assessment_sha256: str


@dataclass(frozen=True)
class ConstructionProgram:
    capability_id: str
    source_adapter_id: str
    generator_id: str
    oracle_id: str
    prerequisites: tuple[str, ...]


@dataclass(frozen=True)
class CoveragePlan:
    capability_id: str
    variation_axes: tuple[str, ...]
    minimum_specimens: int
    require_counterbalanced_gold: bool = True
    require_fresh_seed: bool = True


@dataclass(frozen=True)
class TeachingOption:
    option_id: str
    capability_id: str
    construction_program_id: str
    source_grounded: bool
    supervised_gold_allowed: bool


@dataclass(frozen=True)
class SourceAdapter:
    """Release-time identity of one genuine source construction boundary."""

    adapter_id: str
    generator_id: str
    accepted_oracle_ids: tuple[str, ...]
    implementation_sha256: str
    cohort_generator_id: str | None = None
    cohort_releases: tuple[tuple[str, str], ...] = ()
    variation_axes: tuple[str, ...] = ("source-valid", "balanced-gold", "fresh-seed")
    teaching_option_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (not self.adapter_id or not self.generator_id or
                not self.accepted_oracle_ids or
                any(not isinstance(item, str) or not item
                    for item in self.accepted_oracle_ids)):
            raise ValueError("FACTORY_SOURCE_ADAPTER_IDENTITY_INVALID")
        _sha256(self.implementation_sha256,
                "FACTORY_SOURCE_ADAPTER_IMPLEMENTATION_DIGEST_INVALID")
        if self.cohort_generator_id is not None and not self.cohort_generator_id:
            raise ValueError("FACTORY_SOURCE_ADAPTER_COHORT_GENERATOR_INVALID")
        if (not self.variation_axes or
                any(not isinstance(axis, str) or not axis for axis in self.variation_axes) or
                len(set(self.variation_axes)) != len(self.variation_axes)):
            raise ValueError("FACTORY_SOURCE_ADAPTER_VARIATION_AXES_INVALID")
        seen = set()
        for release, digest in self.cohort_releases:
            if (not release or release in seen):
                raise ValueError("FACTORY_SOURCE_ADAPTER_COHORT_RELEASE_INVALID")
            seen.add(release)
            _sha256(digest, "FACTORY_SOURCE_ADAPTER_COHORT_RELEASE_DIGEST_INVALID")
        if (len(set(self.teaching_option_ids)) != len(self.teaching_option_ids) or
                any(not isinstance(item, str) or not item
                    for item in self.teaching_option_ids)):
            raise ValueError("FACTORY_SOURCE_ADAPTER_TEACHING_OPTIONS_INVALID")

    @property
    def cohort_generator(self) -> str:
        return self.cohort_generator_id or self.generator_id

    def cohort_code_sha256(self, release: str) -> str:
        mapping = dict(self.cohort_releases)
        return mapping.get(release, self.implementation_sha256)


@dataclass(frozen=True)
class AssessmentPlan:
    grade_id: str
    assessment_class: AssessmentClass
    lifecycle: str
    fresh_on_decision: bool
    reusable_after_failure: bool
    burn_after_failure: bool


def assessment_plans(grade_ids) -> tuple[AssessmentPlan, ...]:
    from ..generated_assessment import (
        GENERALIZATION_LIFECYCLE, PROMOTION_ATTEMPT_LIFECYCLE, ROUTINE_EVAL_LIFECYCLE,
    )
    return tuple(
        AssessmentPlan(grade, kind, lifecycle, fresh, reusable, burn)
        for grade in grade_ids
        for kind, lifecycle, fresh, reusable, burn in (
            (AssessmentClass.ROUTINE, ROUTINE_EVAL_LIFECYCLE, True, False, False),
            (AssessmentClass.PROMOTION, PROMOTION_ATTEMPT_LIFECYCLE, False, True, False),
            (AssessmentClass.GENERALIZATION, GENERALIZATION_LIFECYCLE, True, False, True)))


@dataclass(frozen=True)
class FactoryRelease:
    """Only release artifact from which a production grade may be executed."""

    semantic_release: SemanticRelease
    course: Course
    capabilities: tuple[CapabilityDefinition, ...]
    grades: tuple[GradeDefinition, ...]
    source_adapters: tuple[SourceAdapter, ...]
    construction_programs: tuple[ConstructionProgram, ...]
    coverage_plans: tuple[CoveragePlan, ...]
    teaching_options: tuple[TeachingOption, ...]
    assessments: tuple[AssessmentPlan, ...]
    release_sha256: str

    def __post_init__(self) -> None:
        _sha256(self.release_sha256, "FACTORY_RELEASE_DIGEST_INVALID")

    @property
    def source_adapter_map(self) -> dict[str, SourceAdapter]:
        return {adapter.adapter_id: adapter for adapter in self.source_adapters}

    def expected_digest(self) -> str:
        return _digest(self.manifest())

    def manifest(self) -> dict:
        return {
            "semantic_release": asdict(self.semantic_release),
            "course": asdict(self.course),
            "course_sha256": self.course.digest(),
            "capabilities": [asdict(item) for item in self.capabilities],
            "grades": [asdict(item) for item in self.grades],
            "source_adapters": [asdict(item) for item in self.source_adapters],
            "construction_programs": [asdict(item) for item in self.construction_programs],
            "coverage_plans": [asdict(item) for item in self.coverage_plans],
            "teaching_options": [asdict(item) for item in self.teaching_options],
            "assessments": [
                {**asdict(item), "assessment_class": item.assessment_class.value}
                for item in self.assessments],
        }

    @classmethod
    def from_manifest(cls, payload: dict, release_sha256: str) -> FactoryRelease:
        """Decode typed release data; never import executable provider names from it."""
        def tuples(value):
            return tuple(tuples(item) for item in value) if isinstance(value, list) else value

        def record(record_type, value):
            return record_type(**{key: tuples(item) for key, item in value.items()})

        try:
            declared = payload["course"]
            grades = []
            for grade in declared["grades"]:
                caps = tuple(record(Capability, {
                    **cap, "answer_families": tuple(record(AnswerFamily, family)
                                                   for family in cap["answer_families"]),
                }) for cap in grade["capabilities"])
                grades.append(record(Grade, {**grade, "capabilities": caps}))
            course = Course(**{**declared, "grades": tuple(grades)})
            release = cls(
                semantic_release=record(SemanticRelease, payload["semantic_release"]),
                course=course,
                **{key: tuple(record(kind, value) for value in payload[key])
                   for key, kind in (
                       ("capabilities", CapabilityDefinition), ("grades", GradeDefinition),
                       ("source_adapters", SourceAdapter),
                       ("construction_programs", ConstructionProgram),
                       ("coverage_plans", CoveragePlan), ("teaching_options", TeachingOption))},
                assessments=tuple(record(AssessmentPlan, {
                    **value, "assessment_class": AssessmentClass(value["assessment_class"]),
                }) for value in payload["assessments"]),
                release_sha256=release_sha256,
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("FACTORY_RELEASE_MANIFEST_INVALID") from exc
        if _digest(payload) != release_sha256 or payload["course_sha256"] != course.digest():
            raise ValueError("FACTORY_RELEASE_MANIFEST_CONTENT_DRIFT")
        release.verify()
        return release

    def verify(self) -> None:
        from ..curriculum_compiler import compile_ast

        if not self.course.executable:
            raise ValueError("FACTORY_RELEASE_COURSE_NOT_EXECUTABLE")
        if self.semantic_release.course_sha256 != self.course.digest():
            raise ValueError("FACTORY_RELEASE_COURSE_BINDING_DRIFT")
        if self.release_sha256 != self.expected_digest():
            raise ValueError("FACTORY_RELEASE_CONTENT_DRIFT")
        if (self.semantic_release.version != self.course.version or
                self.semantic_release.ast_sha256 != compile_ast(self.course).digest() or
                self.semantic_release.source_attestation_sha256 !=
                self.course.source_attestation_sha256):
            raise ValueError("FACTORY_RELEASE_SEMANTIC_BINDING_DRIFT")
        grade_ids = tuple(grade.id for grade in self.course.grades)
        if tuple(item.grade_id for item in self.grades) != grade_ids:
            raise ValueError("FACTORY_RELEASE_GRADE_BINDING_DRIFT")
        for definition, grade in zip(self.grades, self.course.grades):
            if definition != GradeDefinition(
                    grade.id, tuple(cap.id for cap in grade.capabilities),
                    grade.teaching_stages, grade.assessment_sha256):
                raise ValueError("FACTORY_RELEASE_GRADE_CONTRACT_DRIFT")
        expected_caps = tuple(cap.id for grade in self.course.grades
                              for cap in grade.capabilities)
        if tuple(item.capability_id for item in self.capabilities) != expected_caps:
            raise ValueError("FACTORY_RELEASE_CAPABILITY_BINDING_DRIFT")
        for field, values in (
                ("construction", self.construction_programs),
                ("coverage", self.coverage_plans)):
            if tuple(item.capability_id for item in values) != expected_caps:
                raise ValueError("FACTORY_RELEASE_" + field.upper() + "_BINDING_DRIFT")
        self._verify_source_contracts(expected_caps)
        if self.assessments != assessment_plans(grade_ids):
            raise ValueError("FACTORY_RELEASE_ASSESSMENT_CONTRACT_DRIFT")


    def _verify_source_contracts(self, expected_caps):
        teaching_by_capability = {
            capability: tuple(item for item in self.teaching_options
                              if item.capability_id == capability)
            for capability in expected_caps
        }
        if (any(not teaching_by_capability[capability] for capability in expected_caps) or
                {item.capability_id for item in self.teaching_options} != set(expected_caps) or
                any(not any(item.option_id == "source.direct/" + capability
                            for item in teaching_by_capability[capability])
                    for capability in expected_caps)):
            raise ValueError("FACTORY_RELEASE_TEACHING_BINDING_DRIFT")
        adapters = self.source_adapter_map
        if len(adapters) != len(self.source_adapters):
            raise ValueError("FACTORY_RELEASE_DUPLICATE_SOURCE_ADAPTER")
        for cap in self.capabilities:
            adapter = adapters.get(cap.source_adapter_id)
            if adapter is None or cap.oracle_id not in adapter.accepted_oracle_ids:
                raise ValueError("FACTORY_RELEASE_SOURCE_ORACLE_BINDING_INVALID")
            declared = self.course.capability_map[cap.capability_id]
            if (cap.grade_id != next(grade.id for grade in self.course.grades
                                    if declared in grade.capabilities) or
                    cap.prerequisites != declared.prerequisites or
                    cap.oracle_id != declared.independent_oracle or
                    cap.answer_kinds != tuple(f.kind for f in declared.answer_families) or
                    adapter.generator_id != declared.lesson_generator):
                raise ValueError("FACTORY_RELEASE_CAPABILITY_CONTRACT_DRIFT")
        for cap, program, coverage in zip(
                self.capabilities, self.construction_programs, self.coverage_plans):
            adapter = adapters[cap.source_adapter_id]
            if program != ConstructionProgram(
                    cap.capability_id, cap.source_adapter_id, adapter.generator_id,
                    cap.oracle_id, cap.prerequisites):
                raise ValueError("FACTORY_RELEASE_CONSTRUCTION_CONTRACT_DRIFT")
            counts = dict(next(grade.exam_item_counts for grade in self.course.grades
                               if grade.id == cap.grade_id))
            if (coverage.variation_axes != adapter.variation_axes or
                    coverage.minimum_specimens != counts[cap.capability_id] or
                    coverage.require_counterbalanced_gold !=
                    ("balanced-gold" in adapter.variation_axes) or
                    coverage.require_fresh_seed is not True):
                raise ValueError("FACTORY_RELEASE_COVERAGE_CONTRACT_DRIFT")
            expected_options = tuple(
                TeachingOption(option, cap.capability_id, cap.capability_id, True, True)
                for option in ("source.direct/" + cap.capability_id,
                               *adapter.teaching_option_ids))
            if teaching_by_capability[cap.capability_id] != expected_options:
                raise ValueError("FACTORY_RELEASE_TEACHING_CONTRACT_DRIFT")


@dataclass(frozen=True)
class LearningEvidence:
    assessment_class: AssessmentClass
    cohort_sha256: str
    checkpoint_sha256: str
    optimizer_step: int
    passed: bool
    contaminated_for_qualification: bool = False

    def __post_init__(self):
        if not isinstance(self.assessment_class, AssessmentClass):
            raise ValueError("FACTORY_LEARNING_EVIDENCE_CLASS_INVALID")
        _sha256(self.cohort_sha256, "FACTORY_LEARNING_EVIDENCE_COHORT_INVALID")
        _sha256(self.checkpoint_sha256, "FACTORY_LEARNING_EVIDENCE_STUDENT_INVALID")
        if (type(self.optimizer_step) is not int or self.optimizer_step < 0 or
                type(self.passed) is not bool or
                type(self.contaminated_for_qualification) is not bool):
            raise ValueError("FACTORY_LEARNING_EVIDENCE_VALUE_INVALID")


@dataclass(frozen=True)
class AdmissionReceipt:
    factory_release_sha256: str
    course_sha256: str
    student_sha256: str
    optimizer_step: int
    semantic_graph_sha256: str

    def verify(self, release: FactoryRelease) -> None:
        release.verify()
        if (self.factory_release_sha256 != release.release_sha256 or
                self.course_sha256 != release.course.digest()):
            raise ValueError("FACTORY_ADMISSION_RELEASE_MISMATCH")
        _sha256(self.student_sha256, "FACTORY_ADMISSION_STUDENT_DIGEST_INVALID")
        _sha256(self.semantic_graph_sha256, "FACTORY_ADMISSION_GRAPH_DIGEST_INVALID")
        if type(self.optimizer_step) is not int or self.optimizer_step < 0:
            raise ValueError("FACTORY_ADMISSION_OPTIMIZER_STEP_INVALID")
