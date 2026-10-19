"""Compile semantic curriculum plus source bindings into one execution plan.

Canonical curriculum meaning is independent from source/provider implementation.
Legacy ``Course`` remains an input only through a compatibility projection while
callers migrate to ``CurriculumDefinition`` and ``SourceBindingSet``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json

from ..curriculum import AnswerFamily, Course
from .adapters import SourceAdapterRegistry
from .curriculum_definition import (
    CurriculumDefinition, SourceBindingSet, from_legacy_course,
    validate_curriculum_definition, validate_source_bindings,
)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def _pairs(value) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if value is None:
        return ()
    result = tuple((str(key), tuple(items)) for key, items in value)
    if (len({key for key, _ in result}) != len(result) or
            any(not key or not items or len(set(items)) != len(items) or
                any(not isinstance(item, str) or not item for item in items)
                for key, items in result)):
        raise ValueError("FACTORY_PROFILE_DIMENSION_INVALID")
    return result


@dataclass(frozen=True)
class CapabilityProfile:
    capability_id: str
    provider_parameters: tuple[tuple[str, tuple[str, ...]], ...] = ()
    answer_family_values: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not self.capability_id:
            raise ValueError("FACTORY_PROFILE_CAPABILITY_ID_REQUIRED")
        object.__setattr__(self, "provider_parameters", _pairs(self.provider_parameters))
        object.__setattr__(self, "answer_family_values", _pairs(self.answer_family_values))


@dataclass(frozen=True)
class GradeProfile:
    grade_id: str
    enabled_capabilities: tuple[str, ...] | None = None
    capabilities: tuple[CapabilityProfile, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.grade_id, str) or not self.grade_id:
            raise ValueError("FACTORY_PROFILE_GRADE_ID_REQUIRED")
        if self.enabled_capabilities is not None and (
                not self.enabled_capabilities or
                len(set(self.enabled_capabilities)) != len(self.enabled_capabilities) or
                any(not isinstance(item, str) or not item
                    for item in self.enabled_capabilities)):
            raise ValueError("FACTORY_PROFILE_ENABLED_CAPABILITIES_INVALID")
        ids = tuple(item.capability_id for item in self.capabilities)
        if len(set(ids)) != len(ids):
            raise ValueError("FACTORY_PROFILE_DUPLICATE_CAPABILITY_OVERRIDE")


@dataclass(frozen=True)
class CurriculumProfile:
    profile_id: str
    grades: tuple[GradeProfile, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise ValueError("FACTORY_PROFILE_ID_REQUIRED")
        ids = tuple(item.grade_id for item in self.grades)
        if len(set(ids)) != len(ids):
            raise ValueError("FACTORY_PROFILE_DUPLICATE_GRADE_OVERRIDE")

    @classmethod
    def full(cls) -> "CurriculumProfile":
        return cls("full")


@dataclass(frozen=True)
class CapabilityExecution:
    capability_id: str
    grade_id: str
    stage: int
    prerequisites: tuple[str, ...]
    composed_of: tuple[str, ...]
    source_anchor: str
    provider_id: str
    provider_implementation_sha256: str
    oracle_id: str
    construction_program_id: str
    provider_parameters: tuple[tuple[str, tuple[str, ...]], ...]
    variation_axes: tuple[str, ...]
    teaching_option_ids: tuple[str, ...]
    answer_families: tuple[AnswerFamily, ...]
    exam_item_count: int


@dataclass(frozen=True)
class GradeExecution:
    grade_id: str
    capabilities: tuple[str, ...]
    teaching_stages: tuple[tuple[str, ...], ...]
    cumulative_scope: tuple[str, ...]
    assessment_blueprint_sha256: str


@dataclass(frozen=True)
class ProjectionDigests:
    roster: str
    schedule: str
    assessment: str
    source: str
    answer_schema: str
    coverage: str
    teaching: str


@dataclass(frozen=True)
class CapabilityProjectionDigests:
    capability_id: str
    schedule: str
    assessment: str
    source: str
    answer_schema: str
    coverage: str
    teaching: str


@dataclass(frozen=True)
class ExecutionPlan:
    profile_id: str
    curriculum_sha256: str
    source_binding_sha256: str
    grades: tuple[GradeExecution, ...]
    capabilities: tuple[CapabilityExecution, ...]
    projection_digests: ProjectionDigests
    capability_projection_digests: tuple[CapabilityProjectionDigests, ...]

    @property
    def capability_map(self) -> dict[str, CapabilityExecution]:
        return {item.capability_id: item for item in self.capabilities}

    @property
    def grade_map(self) -> dict[str, GradeExecution]:
        return {item.grade_id: item for item in self.grades}

    @property
    def course_sha256(self) -> str:
        """Compatibility alias for pre-split callers only."""
        return self.curriculum_sha256

    def digest(self) -> str:
        return _digest(asdict(self))


class SemanticGeometryChange(str, Enum):
    UNCHANGED = "UNCHANGED"
    APPEND_ONLY_EXPANSION = "APPEND_ONLY_EXPANSION"
    INCOMPATIBLE = "INCOMPATIBLE"


@dataclass(frozen=True)
class PlanLineage:
    previous_curriculum_sha256: str
    next_curriculum_sha256: str
    semantic_geometry: SemanticGeometryChange

    def __post_init__(self) -> None:
        for value in (
                self.previous_curriculum_sha256,
                self.next_curriculum_sha256):
            if (not isinstance(value, str) or len(value) != 64 or
                    any(c not in "0123456789abcdef" for c in value)):
                raise ValueError("FACTORY_PLAN_LINEAGE_CURRICULUM_DIGEST_INVALID")

    @classmethod
    def from_semantic_catalogs(
            cls, previous: ExecutionPlan, current: ExecutionPlan,
            previous_tokens: tuple[str, ...], current_tokens: tuple[str, ...]):
        if (not previous_tokens or not current_tokens or
                len(set(previous_tokens)) != len(previous_tokens) or
                len(set(current_tokens)) != len(current_tokens)):
            raise ValueError("FACTORY_PLAN_LINEAGE_SEMANTIC_CATALOG_INVALID")
        if current_tokens == previous_tokens:
            geometry = SemanticGeometryChange.UNCHANGED
        elif current_tokens[:len(previous_tokens)] == previous_tokens:
            geometry = SemanticGeometryChange.APPEND_ONLY_EXPANSION
        else:
            geometry = SemanticGeometryChange.INCOMPATIBLE
        return cls(
            previous.curriculum_sha256, current.curriculum_sha256, geometry)


@dataclass(frozen=True)
class CurriculumDelta:
    previous_plan_sha256: str
    next_plan_sha256: str
    previous_curriculum_sha256: str
    next_curriculum_sha256: str
    previous_source_binding_sha256: str
    next_source_binding_sha256: str
    added_grades: tuple[str, ...]
    removed_grades: tuple[str, ...]
    revised_grades: tuple[str, ...]
    added_capabilities: tuple[str, ...]
    removed_capabilities: tuple[str, ...]
    changed_capabilities: tuple[str, ...]
    projection_changes: tuple[str, ...]
    semantic_geometry: str


def _normalize_inputs(
        curriculum: CurriculumDefinition | Course,
        source_bindings: SourceBindingSet | None,
        answer_registry):
    if isinstance(curriculum, Course):
        if source_bindings is not None:
            raise ValueError("FACTORY_EXECUTION_PLAN_LEGACY_BINDINGS_AMBIGUOUS")
        legacy = curriculum
        curriculum, source_bindings = from_legacy_course(
            legacy,
            answer_kinds=(answer_registry.kinds
                          if answer_registry is not None else None))
        answer_kinds = (
            answer_registry.kinds if answer_registry is not None else
            tuple(dict.fromkeys(
                family.kind for grade in legacy.grades
                for capability in grade.capabilities
                for family in capability.answer_families)))
    elif isinstance(curriculum, CurriculumDefinition):
        if source_bindings is None:
            raise ValueError("FACTORY_EXECUTION_PLAN_SOURCE_BINDINGS_REQUIRED")
        if answer_registry is None:
            raise ValueError("FACTORY_EXECUTION_PLAN_ANSWER_REGISTRY_REQUIRED")
        answer_kinds = answer_registry.kinds
    else:
        raise TypeError("FACTORY_EXECUTION_PLAN_INVALID_INPUT")
    validate_curriculum_definition(curriculum, answer_kinds=answer_kinds)
    validate_source_bindings(curriculum, source_bindings)
    return curriculum, source_bindings


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
        result.append(AnswerFamily(family.kind, values))
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
    stages = _stages(grade, enabled)
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
        executions.append(CapabilityExecution(
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
            teaching_option_ids=adapter.teaching_option_ids,
            answer_families=_answer_families(cap, override),
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
                "answer_families": [asdict(family) for family in item.answer_families],
            }
            for item in executions
        ],
        "cumulative_scope": cumulative,
    }
    return (
        GradeExecution(
            grade.grade_id, enabled, stages, cumulative,
            _digest(assessment_payload)),
        tuple(executions), cumulative,
    )


def compile_execution_plan(
        curriculum: CurriculumDefinition | Course, profile: CurriculumProfile,
        registry: SourceAdapterRegistry, *,
        source_bindings: SourceBindingSet | None = None,
        answer_registry=None) -> ExecutionPlan:
    """Compile one executable projection without mutating canonical curriculum."""
    if not isinstance(profile, CurriculumProfile):
        raise TypeError("FACTORY_EXECUTION_PLAN_INVALID_INPUT")
    if not isinstance(registry, SourceAdapterRegistry):
        raise TypeError("FACTORY_EXECUTION_PLAN_REGISTRY_REQUIRED")
    curriculum, source_bindings = _normalize_inputs(
        curriculum, source_bindings, answer_registry)
    grade_profiles = _profile_maps(curriculum, profile)
    enabled_by_grade = {
        grade.grade_id: _enabled_for_grade(
            grade, grade_profiles.get(grade.grade_id))
        for grade in curriculum.grades
    }
    active_capabilities = {
        capability for values in enabled_by_grade.values() for capability in values
    }
    grades = []
    capabilities = []
    cumulative: tuple[str, ...] = ()
    for grade in curriculum.grades:
        compiled, members, cumulative = _profiled_grade(
            curriculum, grade, grade_profiles.get(grade.grade_id),
            source_bindings, registry, cumulative,
            enabled_by_grade[grade.grade_id], active_capabilities)
        grades.append(compiled)
        capabilities.extend(members)

    roster_payload = tuple((grade.grade_id, grade.capabilities) for grade in grades)
    schedule_payload = tuple((
        grade.grade_id, grade.teaching_stages,
        tuple((cap.capability_id, cap.stage, cap.prerequisites, cap.composed_of)
              for cap in capabilities if cap.grade_id == grade.grade_id),
    ) for grade in grades)
    assessment_payload = tuple((
        grade.grade_id, grade.cumulative_scope, grade.assessment_blueprint_sha256,
        tuple((cap.capability_id, cap.exam_item_count)
              for cap in capabilities if cap.grade_id == grade.grade_id),
    ) for grade in grades)
    source_payload = (
        ("source_attestation", source_bindings.source_attestation_sha256),
        *tuple((
            cap.capability_id, cap.source_anchor, cap.provider_id,
            cap.provider_implementation_sha256, cap.oracle_id,
            cap.construction_program_id, cap.provider_parameters,
        ) for cap in capabilities),
    )
    answer_payload = tuple((
        cap.capability_id,
        tuple((family.kind, family.values) for family in cap.answer_families),
    ) for cap in capabilities)
    coverage_payload = tuple((
        cap.capability_id, cap.exam_item_count, cap.variation_axes,
    ) for cap in capabilities)
    teaching_payload = tuple((
        cap.capability_id, cap.teaching_option_ids,
    ) for cap in capabilities)
    digests = ProjectionDigests(
        roster=_digest(roster_payload),
        schedule=_digest(schedule_payload),
        assessment=_digest(assessment_payload),
        source=_digest(source_payload),
        answer_schema=_digest(answer_payload),
        coverage=_digest(coverage_payload),
        teaching=_digest(teaching_payload),
    )
    capability_digests = tuple(CapabilityProjectionDigests(
        capability_id=cap.capability_id,
        schedule=_digest((
            cap.capability_id, cap.grade_id, cap.stage,
            cap.prerequisites, cap.composed_of)),
        assessment=_digest((
            cap.capability_id, cap.exam_item_count,
            tuple((family.kind, family.values) for family in cap.answer_families))),
        source=_digest((
            cap.capability_id, cap.source_anchor, cap.provider_id,
            cap.provider_implementation_sha256, cap.oracle_id,
            cap.construction_program_id, cap.provider_parameters,
            source_bindings.source_attestation_sha256)),
        answer_schema=_digest((
            cap.capability_id,
            tuple((family.kind, family.values)
                  for family in cap.answer_families))),
        coverage=_digest((
            cap.capability_id, cap.exam_item_count, cap.variation_axes)),
        teaching=_digest((cap.capability_id, cap.teaching_option_ids)),
    ) for cap in capabilities)
    plan = ExecutionPlan(
        profile_id=profile.profile_id,
        curriculum_sha256=curriculum.digest(),
        source_binding_sha256=source_bindings.digest(),
        grades=tuple(grades),
        capabilities=tuple(capabilities),
        projection_digests=digests,
        capability_projection_digests=capability_digests,
    )
    if answer_registry is not None:
        answer_registry.validate_plan(plan)
    return plan


def diff_execution_plans(
        previous: ExecutionPlan, current: ExecutionPlan, *,
        lineage: PlanLineage | None = None) -> CurriculumDelta:
    if not isinstance(previous, ExecutionPlan) or not isinstance(current, ExecutionPlan):
        raise TypeError("FACTORY_EXECUTION_PLAN_DIFF_INVALID_INPUT")
    if previous.curriculum_sha256 == current.curriculum_sha256:
        if lineage is not None and (
                lineage.previous_curriculum_sha256 != previous.curriculum_sha256 or
                lineage.next_curriculum_sha256 != current.curriculum_sha256 or
                lineage.semantic_geometry is not SemanticGeometryChange.UNCHANGED):
            raise ValueError("FACTORY_PLAN_LINEAGE_PROFILE_REVISION_DRIFT")
        geometry = SemanticGeometryChange.UNCHANGED
    else:
        if lineage is None:
            raise ValueError("FACTORY_EXECUTION_PLAN_LINEAGE_REQUIRED")
        if (lineage.previous_curriculum_sha256 != previous.curriculum_sha256 or
                lineage.next_curriculum_sha256 != current.curriculum_sha256):
            raise ValueError("FACTORY_PLAN_LINEAGE_CURRICULUM_DRIFT")
        geometry = lineage.semantic_geometry

    previous_grades = previous.grade_map
    current_grades = current.grade_map
    previous_caps = previous.capability_map
    current_caps = current.capability_map
    projection_changes = tuple(
        name for name in (
            "roster", "schedule", "assessment", "source", "answer_schema",
            "coverage", "teaching")
        if getattr(previous.projection_digests, name) !=
           getattr(current.projection_digests, name))
    return CurriculumDelta(
        previous_plan_sha256=previous.digest(),
        next_plan_sha256=current.digest(),
        previous_curriculum_sha256=previous.curriculum_sha256,
        next_curriculum_sha256=current.curriculum_sha256,
        previous_source_binding_sha256=previous.source_binding_sha256,
        next_source_binding_sha256=current.source_binding_sha256,
        added_grades=tuple(sorted(set(current_grades) - set(previous_grades))),
        removed_grades=tuple(sorted(set(previous_grades) - set(current_grades))),
        revised_grades=tuple(sorted(
            grade for grade in set(previous_grades) & set(current_grades)
            if previous_grades[grade] != current_grades[grade])),
        added_capabilities=tuple(sorted(set(current_caps) - set(previous_caps))),
        removed_capabilities=tuple(sorted(set(previous_caps) - set(current_caps))),
        changed_capabilities=tuple(sorted(
            cap for cap in set(previous_caps) & set(current_caps)
            if previous_caps[cap] != current_caps[cap])),
        projection_changes=projection_changes,
        semantic_geometry=geometry.value,
    )
