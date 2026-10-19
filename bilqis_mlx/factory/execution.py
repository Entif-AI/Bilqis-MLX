"""Compile declarative curriculum profiles into one executable runtime plan.

This module is deliberately grade- and release-neutral. Canonical semantic meaning
lives in ``Course``. A ``CurriculumProfile`` may expose a subset of that course or
narrow already-authorized construction/answer domains, but it cannot mint new
semantics. Runtime consumers should eventually depend on ``ExecutionPlan`` rather
than reinterpreting ``Course`` independently.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from ..curriculum import AnswerFamily, Course, validate
from .adapters import SourceAdapterRegistry


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
    teaching_stages: tuple[tuple[str, ...], ...] | None = None
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
        if self.teaching_stages is not None and (
                not self.teaching_stages or any(not stage for stage in self.teaching_stages)):
            raise ValueError("FACTORY_PROFILE_TEACHING_STAGES_INVALID")
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
    provider_id: str
    oracle_id: str
    construction_program_id: str
    provider_parameters: tuple[tuple[str, tuple[str, ...]], ...]
    answer_families: tuple[AnswerFamily, ...]
    exam_item_count: int


@dataclass(frozen=True)
class GradeExecution:
    grade_id: str
    capabilities: tuple[str, ...]
    teaching_stages: tuple[tuple[str, ...], ...]
    cumulative_scope: tuple[str, ...]
    assessment_sha256: str


@dataclass(frozen=True)
class ProjectionDigests:
    roster: str
    schedule: str
    assessment: str
    source: str
    answer_schema: str


@dataclass(frozen=True)
class ExecutionPlan:
    profile_id: str
    course_sha256: str
    grades: tuple[GradeExecution, ...]
    capabilities: tuple[CapabilityExecution, ...]
    projection_digests: ProjectionDigests

    @property
    def capability_map(self) -> dict[str, CapabilityExecution]:
        return {item.capability_id: item for item in self.capabilities}

    @property
    def grade_map(self) -> dict[str, GradeExecution]:
        return {item.grade_id: item for item in self.grades}

    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class CurriculumDelta:
    previous_plan_sha256: str
    next_plan_sha256: str
    added_grades: tuple[str, ...]
    removed_grades: tuple[str, ...]
    revised_grades: tuple[str, ...]
    added_capabilities: tuple[str, ...]
    removed_capabilities: tuple[str, ...]
    changed_capabilities: tuple[str, ...]
    projection_changes: tuple[str, ...]


def _profile_maps(course: Course, profile: CurriculumProfile):
    grade_ids = {grade.id for grade in course.grades}
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
        raise ValueError("FACTORY_PROFILE_UNKNOWN_ANSWER_FAMILY:" + capability.id)
    result = []
    for family in capability.answer_families:
        values = overrides.get(family.kind)
        if values is None:
            result.append(family)
            continue
        if (not set(values) <= set(family.values) or
                values != tuple(value for value in family.values if value in values)):
            raise ValueError("FACTORY_PROFILE_ANSWER_VALUES_NOT_CANONICAL_SUBSET:" + capability.id)
        result.append(AnswerFamily(family.kind, values))
    return tuple(result)


def _stages(grade, grade_profile: GradeProfile | None, enabled: tuple[str, ...]):
    if grade_profile is not None and grade_profile.teaching_stages is not None:
        stages = grade_profile.teaching_stages
    elif grade.teaching_stages:
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


def _profiled_grade(course: Course, grade, grade_profile: GradeProfile | None,
                    registry: SourceAdapterRegistry, cumulative: tuple[str, ...]):
    canonical_ids = tuple(cap.id for cap in grade.capabilities)
    enabled = (canonical_ids if grade_profile is None or
               grade_profile.enabled_capabilities is None
               else grade_profile.enabled_capabilities)
    if not set(enabled) <= set(canonical_ids):
        raise ValueError("FACTORY_PROFILE_CAPABILITY_OUTSIDE_GRADE:" + grade.id)
    # Preserve canonical ordering regardless of declaration order in the profile.
    enabled = tuple(item for item in canonical_ids if item in set(enabled))
    cap_profiles = ({item.capability_id: item for item in grade_profile.capabilities}
                    if grade_profile is not None else {})
    if set(cap_profiles) - set(enabled):
        raise ValueError("FACTORY_PROFILE_OVERRIDE_FOR_DISABLED_CAPABILITY:" + grade.id)
    stages = _stages(grade, grade_profile, enabled)
    stage_by_cap = {cap: index for index, stage in enumerate(stages) for cap in stage}
    counts = dict(grade.exam_item_counts)
    all_known = {cap.id for item in course.grades for cap in item.capabilities}
    executions = []
    for cap in grade.capabilities:
        if cap.id not in enabled:
            continue
        if any(pre not in all_known for pre in cap.prerequisites):
            raise ValueError("FACTORY_PROFILE_PREREQUISITE_UNKNOWN:" + cap.id)
        override = cap_profiles.get(cap.id)
        adapter = registry.require(cap.lesson_generator, cap.independent_oracle).descriptor
        executions.append(CapabilityExecution(
            capability_id=cap.id,
            grade_id=grade.id,
            stage=stage_by_cap.get(cap.id, 0),
            prerequisites=cap.prerequisites,
            provider_id=adapter.adapter_id,
            oracle_id=cap.independent_oracle,
            construction_program_id=cap.id,
            provider_parameters=(override.provider_parameters if override else ()),
            answer_families=_answer_families(cap, override),
            exam_item_count=counts[cap.id],
        ))
    cumulative = cumulative + enabled
    # Scheduling order and assessment identity are distinct projections. A
    # stage-only edit must not mint a new assessment seal. Roster, answer
    # domain, provider, or construction-constraint edits do change what the
    # assessment means and therefore derive a new seal.
    modified = enabled != canonical_ids or bool(cap_profiles)
    assessment_payload = {
        "schema": "bilqis.mlx.execution-assessment/v1",
        "canonical_assessment_sha256": grade.assessment_sha256,
        "grade_id": grade.id,
        "capabilities": [
            {
                "id": item.capability_id,
                "count": item.exam_item_count,
                "answer_families": [asdict(family) for family in item.answer_families],
                "provider_id": item.provider_id,
                "provider_parameters": item.provider_parameters,
            }
            for item in executions
        ],
        "cumulative_scope": cumulative,
    }
    assessment_sha256 = (
        _digest(assessment_payload) if modified else grade.assessment_sha256)
    return (
        GradeExecution(grade.id, enabled, stages, cumulative, assessment_sha256),
        tuple(executions),
        cumulative,
    )


def compile_execution_plan(course: Course, profile: CurriculumProfile,
                           registry: SourceAdapterRegistry) -> ExecutionPlan:
    """Compile one executable projection without mutating canonical curriculum."""
    if not isinstance(course, Course) or not isinstance(profile, CurriculumProfile):
        raise TypeError("FACTORY_EXECUTION_PLAN_INVALID_INPUT")
    if not isinstance(registry, SourceAdapterRegistry):
        raise TypeError("FACTORY_EXECUTION_PLAN_REGISTRY_REQUIRED")
    validate(course)
    grade_profiles = _profile_maps(course, profile)
    grades = []
    capabilities = []
    cumulative: tuple[str, ...] = ()
    for grade in course.grades:
        compiled, members, cumulative = _profiled_grade(
            course, grade, grade_profiles.get(grade.id), registry, cumulative)
        grades.append(compiled)
        capabilities.extend(members)

    roster_payload = tuple((grade.grade_id, grade.capabilities) for grade in grades)
    schedule_payload = tuple((
        grade.grade_id, grade.teaching_stages,
        tuple((cap.capability_id, cap.stage, cap.prerequisites)
              for cap in capabilities if cap.grade_id == grade.grade_id),
    ) for grade in grades)
    assessment_payload = tuple((
        grade.grade_id, grade.cumulative_scope, grade.assessment_sha256,
        tuple((cap.capability_id, cap.exam_item_count)
              for cap in capabilities if cap.grade_id == grade.grade_id),
    ) for grade in grades)
    source_payload = tuple((
        cap.capability_id, cap.provider_id, cap.oracle_id,
        cap.construction_program_id, cap.provider_parameters,
    ) for cap in capabilities)
    answer_payload = tuple((
        cap.capability_id,
        tuple((family.kind, family.values) for family in cap.answer_families),
    ) for cap in capabilities)
    digests = ProjectionDigests(
        roster=_digest(roster_payload),
        schedule=_digest(schedule_payload),
        assessment=_digest(assessment_payload),
        source=_digest(source_payload),
        answer_schema=_digest(answer_payload),
    )
    return ExecutionPlan(
        profile_id=profile.profile_id,
        course_sha256=course.digest(),
        grades=tuple(grades),
        capabilities=tuple(capabilities),
        projection_digests=digests,
    )


def diff_execution_plans(previous: ExecutionPlan, current: ExecutionPlan) -> CurriculumDelta:
    if not isinstance(previous, ExecutionPlan) or not isinstance(current, ExecutionPlan):
        raise TypeError("FACTORY_EXECUTION_PLAN_DIFF_INVALID_INPUT")
    previous_grades = previous.grade_map
    current_grades = current.grade_map
    previous_caps = previous.capability_map
    current_caps = current.capability_map
    projection_changes = tuple(
        name for name in ("roster", "schedule", "assessment", "source", "answer_schema")
        if getattr(previous.projection_digests, name) !=
           getattr(current.projection_digests, name))
    return CurriculumDelta(
        previous_plan_sha256=previous.digest(),
        next_plan_sha256=current.digest(),
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
    )
