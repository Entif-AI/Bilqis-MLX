"""Typed, neural-inert contracts for the mandatory curriculum factory.

These values bind existing semantic/source authority into one executable release.
They never own model parameters, AdamW state, scheduler mutation, or teacher policy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json

from ..curriculum import Course


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
        seen = set()
        for release, digest in self.cohort_releases:
            if (not release or release in seen):
                raise ValueError("FACTORY_SOURCE_ADAPTER_COHORT_RELEASE_INVALID")
            seen.add(release)
            _sha256(digest, "FACTORY_SOURCE_ADAPTER_COHORT_RELEASE_DIGEST_INVALID")

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

    def verify(self) -> None:
        if not self.course.executable:
            raise ValueError("FACTORY_RELEASE_COURSE_NOT_EXECUTABLE")
        if self.semantic_release.course_sha256 != self.course.digest():
            raise ValueError("FACTORY_RELEASE_COURSE_BINDING_DRIFT")
        if self.release_sha256 != self.expected_digest():
            raise ValueError("FACTORY_RELEASE_CONTENT_DRIFT")
        grade_ids = tuple(grade.id for grade in self.course.grades)
        if tuple(item.grade_id for item in self.grades) != grade_ids:
            raise ValueError("FACTORY_RELEASE_GRADE_BINDING_DRIFT")
        expected_caps = tuple(cap.id for grade in self.course.grades
                              for cap in grade.capabilities)
        if tuple(item.capability_id for item in self.capabilities) != expected_caps:
            raise ValueError("FACTORY_RELEASE_CAPABILITY_BINDING_DRIFT")
        for field, values in (
                ("construction", self.construction_programs),
                ("coverage", self.coverage_plans)):
            if tuple(item.capability_id for item in values) != expected_caps:
                raise ValueError("FACTORY_RELEASE_" + field.upper() + "_BINDING_DRIFT")
        if tuple(item.capability_id for item in self.teaching_options) != expected_caps:
            raise ValueError("FACTORY_RELEASE_TEACHING_BINDING_DRIFT")
        adapters = self.source_adapter_map
        if len(adapters) != len(self.source_adapters):
            raise ValueError("FACTORY_RELEASE_DUPLICATE_SOURCE_ADAPTER")
        for cap in self.capabilities:
            adapter = adapters.get(cap.source_adapter_id)
            if adapter is None or cap.oracle_id not in adapter.accepted_oracle_ids:
                raise ValueError("FACTORY_RELEASE_SOURCE_ORACLE_BINDING_INVALID")


@dataclass(frozen=True)
class LearningEvidence:
    assessment_class: AssessmentClass
    cohort_sha256: str
    checkpoint_sha256: str
    optimizer_step: int
    passed: bool
    contaminated_for_qualification: bool = False


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
