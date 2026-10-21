"""Current school profiles.

These functions author data only. Generic runtime consumes CurriculumProfile and
must not dispatch on the capability or historical release identities declared
here.
"""
from __future__ import annotations

from ..factory.execution import (
    CapabilityProfile,
    CurriculumProfile,
    GradeProfile,
)


def boolean_kernel_profile() -> CurriculumProfile:
    """Reduced AND/IFF execution over canonical staged Grade B semantics."""
    return CurriculumProfile(
        "school/boolean-kernel/and-iff",
        grades=(GradeProfile(
            "B",
            enabled_capabilities=(
                "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"),
            capabilities=(
                CapabilityProfile(
                    "B.COMPOSITE",
                    provider_parameters=(("operators", ("AND", "IFF")),)),
                CapabilityProfile(
                    "B.IDBOOLOPS",
                    provider_parameters=(("operators", ("AND", "IFF")),),
                    answer_family_values=(
                        ("boolean_operator", ("AND", "IFF")),)),
            ),
        ),),
    )


def full_boolean_profile() -> CurriculumProfile:
    """Full canonical A+B execution."""
    return CurriculumProfile("school/boolean/full")


def boolean_entry_profile(*, full: bool = False) -> CurriculumProfile:
    """Operator policy selects data; execution remains profile-generic."""
    if type(full) is not bool:
        raise TypeError("FACTORY_BOOLEAN_PROFILE_SELECTION_INVALID")
    return full_boolean_profile() if full else boolean_kernel_profile()


def with_disabled_future_grades(
        profile: CurriculumProfile, grade_ids) -> CurriculumProfile:
    """Keep an execution profile as a canonical active-grade prefix."""
    if not isinstance(profile, CurriculumProfile):
        raise TypeError("FACTORY_PROFILE_REQUIRED")
    existing = {grade.grade_id for grade in profile.grades}
    additions = tuple(
        GradeProfile(grade_id, enabled_capabilities=())
        for grade_id in grade_ids if grade_id not in existing)
    return CurriculumProfile(
        profile.profile_id,
        grades=(*profile.grades, *additions),
    )


def numeric_foundation_profile(
        boolean_profile: CurriculumProfile, *, maximum: int,
        grade_id: str = "C", capability_ids=()) -> CurriculumProfile:
    """Enable the admitted numeric prefix at one bounded source domain."""
    if (not isinstance(boolean_profile, CurriculumProfile) or
            type(maximum) is not int or not 1 <= maximum <= 10):
        raise ValueError("FACTORY_NUMERIC_PROFILE_INVALID")
    capability_ids = tuple(capability_ids)
    if not capability_ids:
        raise ValueError("FACTORY_NUMERIC_PROFILE_CAPABILITIES_REQUIRED")
    active = (
        capability_ids
        if maximum >= 6 else capability_ids[:5])
    numbers = tuple(str(index) for index in range(maximum + 1))
    overrides = tuple(CapabilityProfile(
        capability_id,
        provider_parameters=(("numbers", numbers),),
        answer_family_values=(("numeric_active", numbers),),
    ) for capability_id in active)
    prior = tuple(
        grade for grade in boolean_profile.grades
        if grade.grade_id != grade_id)
    return CurriculumProfile(
        f"{boolean_profile.profile_id}/numeric-0-{maximum}",
        grades=(*prior, GradeProfile(
            grade_id,
            enabled_capabilities=active,
            capabilities=overrides,
        )),
    )
