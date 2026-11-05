"""Factory execution compilation owner."""
from __future__ import annotations

from ...curriculum import Course
from ..adapters import SourceAdapterRegistry
from ..curriculum_definition import CurriculumDefinition, SourceBindingSet
from ..execution import CurriculumProfile
from ..execution import ExecutionPlan
from .. import execution as _api


def _normalize_inputs(
        curriculum: CurriculumDefinition | Course,
        source_bindings: SourceBindingSet | None,
        answer_registry):
    if isinstance(curriculum, _api.Course):
        if source_bindings is not None:
            raise ValueError("FACTORY_EXECUTION_PLAN_LEGACY_BINDINGS_AMBIGUOUS")
        legacy = curriculum
        curriculum, source_bindings = _api.from_legacy_course(
            legacy,
            answer_kinds=(answer_registry.kinds
                          if answer_registry is not None else None))
        answer_kinds = (
            answer_registry.kinds if answer_registry is not None else
            tuple(dict.fromkeys(
                family.kind for grade in legacy.grades
                for capability in grade.capabilities
                for family in capability.answer_families)))
    elif isinstance(curriculum, _api.CurriculumDefinition):
        if source_bindings is None:
            raise ValueError("FACTORY_EXECUTION_PLAN_SOURCE_BINDINGS_REQUIRED")
        if answer_registry is None:
            raise ValueError("FACTORY_EXECUTION_PLAN_ANSWER_REGISTRY_REQUIRED")
        answer_kinds = answer_registry.kinds
    else:
        raise TypeError("FACTORY_EXECUTION_PLAN_INVALID_INPUT")
    _api.validate_curriculum_definition(curriculum, answer_kinds=answer_kinds)
    _api.validate_source_bindings(curriculum, source_bindings)
    return curriculum, source_bindings


def compile_execution_plan(
        curriculum: CurriculumDefinition | Course, profile: CurriculumProfile,
        registry: SourceAdapterRegistry, *,
        source_bindings: SourceBindingSet | None = None,
        answer_registry=None) -> ExecutionPlan:
    """Compile one executable projection without mutating canonical curriculum."""
    if not isinstance(profile, _api.CurriculumProfile):
        raise TypeError("FACTORY_EXECUTION_PLAN_INVALID_INPUT")
    if not isinstance(registry, _api.SourceAdapterRegistry):
        raise TypeError("FACTORY_EXECUTION_PLAN_REGISTRY_REQUIRED")
    curriculum, source_bindings = _api._normalize_inputs(
        curriculum, source_bindings, answer_registry)
    grades, capabilities = _api._compile_profiled_grades(
        curriculum, source_bindings, profile, registry)
    digests = _api._projection_digests(grades, capabilities, source_bindings)
    capability_digests = _api._capability_projection_digests(
        capabilities, source_bindings)
    plan = _api.ExecutionPlan(
        profile_id=profile.profile_id,
        curriculum_sha256=curriculum.digest(),
        source_binding_sha256=source_bindings.digest(),
        grades=grades,
        capabilities=capabilities,
        projection_digests=digests,
        capability_projection_digests=capability_digests,
    )
    if answer_registry is not None:
        answer_registry.validate_plan(plan)
    return plan
