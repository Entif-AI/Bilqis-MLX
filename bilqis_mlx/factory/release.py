"""Compile and verify one immutable FactoryRelease from admitted course authority."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

from ..curriculum import Course, validate
from ..curriculum_compiler import compile_ast
from ..generated_assessment import (
    GENERALIZATION_LIFECYCLE,
    PROMOTION_ATTEMPT_LIFECYCLE,
    ROUTINE_EVAL_LIFECYCLE,
)
from .adapters import SourceAdapterRegistry
from .model import (
    AdmissionReceipt, AssessmentClass, AssessmentPlan, CapabilityDefinition,
    ConstructionProgram, CoveragePlan, FactoryRelease, GradeDefinition,
    SemanticRelease, TeachingOption,
    assessment_plans,
)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def compile_factory_release(course: Course, registry: SourceAdapterRegistry) -> FactoryRelease:
    """Fail closed unless every executable capability has one registered adapter."""
    if not isinstance(course, Course) or not isinstance(registry, SourceAdapterRegistry):
        raise TypeError("FACTORY_RELEASE_INVALID_INPUT")
    validate(course)
    if not course.executable:
        raise ValueError("FACTORY_RELEASE_REQUIRES_EXECUTABLE_COURSE")
    ast = compile_ast(course)
    semantic = SemanticRelease(
        version=course.version,
        course_sha256=course.digest(),
        ast_sha256=ast.digest(),
        source_attestation_sha256=course.source_attestation_sha256,
    )
    capabilities = tuple(
        CapabilityDefinition(
            capability_id=cap.id,
            grade_id=grade.id,
            prerequisites=cap.prerequisites,
            source_adapter_id=registry.require(
                cap.lesson_generator, cap.independent_oracle).descriptor.adapter_id,
            oracle_id=cap.independent_oracle,
            answer_kinds=tuple(family.kind for family in cap.answer_families),
        )
        for grade in course.grades for cap in grade.capabilities
    )
    grades = tuple(GradeDefinition(
        grade_id=grade.id,
        capabilities=tuple(cap.id for cap in grade.capabilities),
        teaching_stages=grade.teaching_stages,
        assessment_sha256=grade.assessment_sha256,
    ) for grade in course.grades)
    construction_programs = tuple(ConstructionProgram(
        capability_id=cap.capability_id,
        source_adapter_id=cap.source_adapter_id,
        generator_id=next(item.generator_id for item in registry.descriptors_for(course)
                          if item.adapter_id == cap.source_adapter_id),
        oracle_id=cap.oracle_id,
        prerequisites=cap.prerequisites,
    ) for cap in capabilities)
    adapters_by_id = {item.adapter_id: item for item in registry.descriptors_for(course)}
    count_by_capability = {name: count for grade in course.grades
                           for name, count in grade.exam_item_counts}
    coverage_plans = tuple(CoveragePlan(
        capability_id=cap.capability_id,
        variation_axes=adapters_by_id[cap.source_adapter_id].variation_axes,
        minimum_specimens=count_by_capability[cap.capability_id],
        require_counterbalanced_gold="balanced-gold" in
            adapters_by_id[cap.source_adapter_id].variation_axes,
    ) for cap in capabilities)
    teaching_options = _teaching_options(capabilities, adapters_by_id)
    assessments = assessment_plans(grade.id for grade in course.grades)
    release = FactoryRelease(
        semantic_release=semantic,
        course=course,
        capabilities=capabilities,
        grades=grades,
        source_adapters=registry.descriptors_for(course),
        construction_programs=construction_programs,
        coverage_plans=coverage_plans,
        teaching_options=teaching_options,
        assessments=assessments,
        release_sha256="0" * 64,
    )
    release = replace(release, release_sha256=release.expected_digest())
    release.verify()
    return release


def _teaching_options(capabilities, adapters_by_id):
    return tuple(
        option
        for cap in capabilities
        for option in (
            TeachingOption(
                option_id="source.direct/" + cap.capability_id,
                capability_id=cap.capability_id,
                construction_program_id=cap.capability_id,
                source_grounded=True,
                supervised_gold_allowed=True,
            ),
            *(TeachingOption(
                option_id=option_id,
                capability_id=cap.capability_id,
                construction_program_id=cap.capability_id,
                source_grounded=True,
                supervised_gold_allowed=True,
            ) for option_id in adapters_by_id[
                cap.source_adapter_id].teaching_option_ids),
        )
    )


def admit_factory_release(release: FactoryRelease, *, student_sha256: str,
                          optimizer_step: int, semantic_graph_sha256: str) -> AdmissionReceipt:
    """Bind one immutable student/catalog baseline to an already verified release."""
    release.verify()
    receipt = AdmissionReceipt(
        factory_release_sha256=release.release_sha256,
        course_sha256=release.course.digest(),
        student_sha256=student_sha256,
        optimizer_step=optimizer_step,
        semantic_graph_sha256=semantic_graph_sha256,
    )
    receipt.verify(release)
    return receipt
