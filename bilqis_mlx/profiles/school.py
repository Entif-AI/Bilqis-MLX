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
