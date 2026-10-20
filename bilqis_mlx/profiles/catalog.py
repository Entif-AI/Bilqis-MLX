"""School policy for append-only semantic-catalog admission."""
from __future__ import annotations

from dataclasses import dataclass

from ..factory.executable_release import ExecutableFactoryRelease
from ..factory.execution import (
    CapabilityProfile,
    CurriculumProfile,
    GradeProfile,
)
from ..live_grade_c import expanded_graph
from .school import (
    boolean_entry_profile,
    numeric_foundation_profile,
    with_disabled_future_grades,
)


@dataclass(frozen=True)
class CatalogProfileTransition:
    profile: CurriculumProfile
    graph: dict
    numeric_scope_final_maximum: int | None = None


def numeric_entry_transition(
        release: ExecutableFactoryRelease, graph: dict, *,
        full_boolean: bool, maximum: int = 3) -> CatalogProfileTransition:
    """Build the next canonical grade-prefix profile plus its admitted ABI."""
    if not isinstance(release, ExecutableFactoryRelease):
        raise TypeError("FACTORY_CATALOG_RELEASE_REQUIRED")
    release.verify()
    next_index = len(release.execution_plan.grades)
    if not 0 <= next_index < len(release.curriculum.grades):
        raise ValueError("FACTORY_CATALOG_NO_DISABLED_GRADE")
    next_grade = release.curriculum.grades[next_index]
    boolean = boolean_entry_profile(full=full_boolean)
    profile = numeric_foundation_profile(
        boolean,
        maximum=maximum,
        grade_id=next_grade.grade_id,
        capability_ids=tuple(
            capability.capability_id for capability in next_grade.capabilities),
    )
    future = tuple(
        grade.grade_id
        for grade in release.curriculum.grades[next_index + 1:])
    profile = with_disabled_future_grades(profile, future)
    return CatalogProfileTransition(
        profile=profile,
        graph=expanded_graph(graph),
        numeric_scope_final_maximum=(6 if maximum < 6 else None),
    )


def next_numeric_scope_profile(
        release: ExecutableFactoryRelease, *, final_maximum: int = 6
        ) -> CurriculumProfile | None:
    """Return the next bounded numeric-domain profile, preserving other grades."""
    if (not isinstance(release, ExecutableFactoryRelease) or
            type(final_maximum) is not int or not 1 <= final_maximum <= 10):
        raise ValueError("FACTORY_NUMERIC_SCOPE_ADVANCE_INVALID")
    release.verify()
    if not release.execution_plan.grades:
        return None
    active_grade = release.execution_plan.grades[-1]
    executions = tuple(
        capability for capability in release.execution_plan.capabilities
        if capability.grade_id == active_grade.grade_id)
    domains = {
        family.values
        for capability in executions
        for family in capability.answer_families
        if family.kind == "numeric_active"
    }
    if not domains:
        return None
    if len(domains) != 1:
        raise ValueError("FACTORY_NUMERIC_SCOPE_DOMAIN_INCONSISTENT")
    values = next(iter(domains))
    if values != tuple(str(index) for index in range(len(values))):
        raise ValueError("FACTORY_NUMERIC_SCOPE_DOMAIN_INVALID")
    maximum = len(values) - 1
    if maximum >= final_maximum:
        return None
    target = maximum + 1
    canonical_grade = next(
        grade for grade in release.curriculum.grades
        if grade.grade_id == active_grade.grade_id)
    all_ids = tuple(
        capability.capability_id for capability in canonical_grade.capabilities)
    enabled = all_ids if target >= 6 else all_ids[:5]
    numbers = tuple(str(index) for index in range(target + 1))
    numeric_grade = GradeProfile(
        active_grade.grade_id,
        enabled_capabilities=enabled,
        capabilities=tuple(CapabilityProfile(
            capability_id,
            provider_parameters=(("numbers", numbers),),
            answer_family_values=(("numeric_active", numbers),),
        ) for capability_id in enabled),
    )
    prior = tuple(
        grade for grade in release.profile.grades
        if grade.grade_id != active_grade.grade_id)
    future = tuple(
        GradeProfile(grade.grade_id, enabled_capabilities=())
        for grade in release.curriculum.grades[len(release.execution_plan.grades):]
        if grade.grade_id != active_grade.grade_id)
    return CurriculumProfile(
        f"{release.profile.profile_id.rsplit('/numeric-0-', 1)[0]}"
        f"/numeric-0-{target}",
        grades=(*prior, numeric_grade, *future),
    )
