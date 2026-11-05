"""Factory execution profiling owner."""
from __future__ import annotations

from ..adapters import SourceAdapterRegistry
from ..curriculum_definition import CurriculumDefinition, SourceBindingSet
from .profiles import CapabilityProfile, CurriculumProfile, GradeProfile
from .records import CapabilityExecution, GradeExecution
from .. import execution as _api


def _profile_maps(curriculum: CurriculumDefinition, profile: CurriculumProfile):
    grade_ids = {grade.grade_id for grade in curriculum.grades}
    grade_profiles = {item.grade_id: item for item in profile.grades}
    unknown = set(grade_profiles) - grade_ids
    if unknown:
        raise ValueError("FACTORY_PROFILE_UNKNOWN_GRADE:" + ",".join(sorted(unknown)))
    return grade_profiles


def _answer_families(capability, profile: CapabilityProfile | None):
    if profile is None or not profile.answer_family_values:
        return capability.answer_families
    overrides = dict(profile.answer_family_values)
    known = {family.kind: family for family in capability.answer_families}
    if set(overrides) - set(known):
        raise ValueError(
            "FACTORY_PROFILE_UNKNOWN_ANSWER_FAMILY:"
            + capability.capability_id)
    result = []
    for family in capability.answer_families:
        values = overrides.get(family.kind)
        if values is None:
            result.append(family)
            continue
        if (not set(values) <= set(family.values) or
                values != tuple(value for value in family.values if value in values)):
            raise ValueError(
                "FACTORY_PROFILE_ANSWER_VALUES_NOT_CANONICAL_SUBSET:"
                + capability.capability_id)
        result.append(_api.AnswerFamily(family.kind, values))
    return tuple(result)


def _stages(grade, enabled: tuple[str, ...]):
    if grade.teaching_stages:
        enabled_set = set(enabled)
        stages = tuple(
            tuple(cap for cap in stage if cap in enabled_set)
            for stage in grade.teaching_stages)
        stages = tuple(stage for stage in stages if stage)
    else:
        stages = ()
    if stages and tuple(cap for stage in stages for cap in stage) != enabled:
        raise ValueError("FACTORY_PROFILE_STAGES_MUST_PARTITION_ENABLED_CAPABILITIES")
    return stages


def _enabled_for_grade(grade, grade_profile: GradeProfile | None) -> tuple[str, ...]:
    canonical_ids = tuple(cap.capability_id for cap in grade.capabilities)
    requested = (canonical_ids if grade_profile is None or
                 grade_profile.enabled_capabilities is None
                 else grade_profile.enabled_capabilities)
    if not set(requested) <= set(canonical_ids):
        raise ValueError(
            "FACTORY_PROFILE_CAPABILITY_OUTSIDE_GRADE:" + grade.grade_id)
    return tuple(item for item in canonical_ids if item in set(requested))


def _profiled_grade(
        curriculum: CurriculumDefinition, grade, grade_profile: GradeProfile | None,
        bindings: SourceBindingSet, registry: SourceAdapterRegistry,
        cumulative: tuple[str, ...], enabled: tuple[str, ...],
        active_capabilities: set[str]):
    cap_profiles = ({item.capability_id: item for item in grade_profile.capabilities}
                    if grade_profile is not None else {})
    if set(cap_profiles) - set(enabled):
        raise ValueError(
            "FACTORY_PROFILE_OVERRIDE_FOR_DISABLED_CAPABILITY:"
            + grade.grade_id)
    stages = _api._stages(grade, enabled)
    stage_by_cap = {cap: index for index, stage in enumerate(stages) for cap in stage}
    counts = dict(grade.exam_item_counts)
    binding_map = bindings.by_capability
    executions = []
    for cap in grade.capabilities:
        if cap.capability_id not in enabled:
            continue
        if not set(cap.prerequisites) <= active_capabilities:
            raise ValueError(
                "FACTORY_PROFILE_DISABLED_PREREQUISITE:" + cap.capability_id)
        if not set(cap.composed_of) <= active_capabilities:
            raise ValueError(
                "FACTORY_PROFILE_DISABLED_CONSTITUENT:" + cap.capability_id)
        override = cap_profiles.get(cap.capability_id)
        binding = binding_map[cap.capability_id]
        adapter = registry.require(binding.generator_id, binding.oracle_id).descriptor
        provider_parameters = override.provider_parameters if override else ()
        adapter.validate_profile_parameters(provider_parameters)
        executions.append(_api.CapabilityExecution(
            capability_id=cap.capability_id,
            grade_id=grade.grade_id,
            stage=stage_by_cap.get(cap.capability_id, 0),
            prerequisites=cap.prerequisites,
            composed_of=cap.composed_of,
            source_anchor=binding.source_anchor,
            provider_id=adapter.adapter_id,
            provider_implementation_sha256=adapter.implementation_sha256,
            oracle_id=binding.oracle_id,
            construction_program_id=cap.capability_id,
            provider_parameters=provider_parameters,
            variation_axes=adapter.variation_axes,
            teaching_option_ids=("source.direct/" + cap.capability_id,
                                 *adapter.teaching_option_ids),
            answer_families=_api._answer_families(cap, override),
            exam_item_count=counts[cap.capability_id],
        ))
    cumulative = cumulative + enabled
    assessment_payload = {
        "schema": "bilqis.mlx.execution-assessment-blueprint/v1",
        "grade_id": grade.grade_id,
        "capabilities": [
            {
                "id": item.capability_id,
                "count": item.exam_item_count,
                "answer_families": [_api.asdict(family) for family in item.answer_families],
            }
            for item in executions
        ],
        "cumulative_scope": cumulative,
    }
    return (
        _api.GradeExecution(
            grade.grade_id, enabled, stages, cumulative,
            _api._digest(assessment_payload)),
        tuple(executions), cumulative,
    )


def _compile_profiled_grades(
        curriculum: CurriculumDefinition, source_bindings: SourceBindingSet,
        profile: CurriculumProfile, registry: SourceAdapterRegistry,
) -> tuple[tuple[GradeExecution, ...], tuple[CapabilityExecution, ...]]:
    grade_profiles = _api._profile_maps(curriculum, profile)
    enabled_by_grade = {
        grade.grade_id: _api._enabled_for_grade(
            grade, grade_profiles.get(grade.grade_id))
        for grade in curriculum.grades
    }
    active_capabilities = {
        capability for values in enabled_by_grade.values() for capability in values
    }
    if not active_capabilities:
        raise ValueError("FACTORY_PROFILE_EMPTY_EXECUTION")
    grades: list[_api.GradeExecution] = []
    capabilities: list[_api.CapabilityExecution] = []
    cumulative: tuple[str, ...] = ()
    for grade in curriculum.grades:
        enabled = enabled_by_grade[grade.grade_id]
        grade_profile = grade_profiles.get(grade.grade_id)
        if not enabled:
            if grade_profile is not None and grade_profile.capabilities:
                raise ValueError(
                    "FACTORY_PROFILE_OVERRIDE_FOR_DISABLED_GRADE:" + grade.grade_id)
            continue
        compiled, members, cumulative = _api._profiled_grade(
            curriculum, grade, grade_profile, source_bindings, registry,
            cumulative, enabled, active_capabilities)
        grades.append(compiled)
        capabilities.extend(members)
    return tuple(grades), tuple(capabilities)
