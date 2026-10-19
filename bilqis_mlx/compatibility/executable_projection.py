"""Project historical Course releases onto the canonical v2 curriculum/profile.

This module is deliberately compatibility-only.  The v2 compiler never learns
legacy release names; it receives canonical semantics plus a declarative profile.
"""
from __future__ import annotations

from dataclasses import replace

from ..boolean_composite import build_course as build_boolean_composite
from ..boolean_identification import build_course as build_boolean_identification
from ..curriculum import BOOLEAN_OPERATORS, Course
from ..factory.curriculum_definition import from_legacy_course
from ..factory.execution import (
    CapabilityProfile, CurriculumProfile, GradeProfile,
)
from ..live_grade_b import live_course as build_boolean_grade


def _canonical_boolean_course(grade_a: Course, source_root) -> Course:
    full = build_boolean_grade(grade_a, source_root)
    full = build_boolean_composite(full, source_root)
    return build_boolean_identification(full, source_root)


def project_legacy_course(
        course: Course, grade_a: Course, source_root, *,
        answer_kinds: tuple[str, ...]):
    """Return canonical curriculum/source bindings + profile for a v1 release."""
    if not isinstance(course, Course) or not isinstance(grade_a, Course):
        raise TypeError("FACTORY_COMPATIBILITY_COURSE_REQUIRED")

    current_b = next((grade for grade in course.grades if grade.id == "B"), None)
    if current_b is None:
        canonical_course = course
        profile = CurriculumProfile.full()
    else:
        canonical_b = _canonical_boolean_course(grade_a, source_root)
        canonical_grade_b = canonical_b.grades[-1]
        current_ids = tuple(cap.id for cap in current_b.capabilities)
        canonical_ids = tuple(cap.id for cap in canonical_grade_b.capabilities)
        if not set(current_ids) <= set(canonical_ids):
            raise ValueError("FACTORY_COMPATIBILITY_BOOLEAN_SCOPE_UNKNOWN")

        grades = (
            canonical_b.grades
            if len(course.grades) == 2
            else (canonical_b.grades[0], canonical_grade_b, *course.grades[2:])
        )
        canonical_course = replace(
            course,
            grades=grades,
            # Preserve the historical higher-grade provenance as compatibility
            # metadata; v2 capability verification independently checks every
            # active source/oracle contract.
            program_complete=course.program_complete,
        )

        overrides = []
        id_capability = next(
            (cap for cap in current_b.capabilities
             if cap.id == "B.IDBOOLOPS"),
            None,
        )
        operator_values = (
            id_capability.answer_families[0].values
            if id_capability is not None else BOOLEAN_OPERATORS
        )
        if tuple(operator_values) != tuple(BOOLEAN_OPERATORS):
            if not set(operator_values) <= set(BOOLEAN_OPERATORS):
                raise ValueError("FACTORY_COMPATIBILITY_BOOLEAN_DOMAIN_UNKNOWN")
            if "B.COMPOSITE" in current_ids:
                overrides.append(CapabilityProfile(
                    "B.COMPOSITE",
                    provider_parameters=(("operators", tuple(operator_values)),),
                ))
            if "B.IDBOOLOPS" in current_ids:
                overrides.append(CapabilityProfile(
                    "B.IDBOOLOPS",
                    provider_parameters=(("operators", tuple(operator_values)),),
                    answer_family_values=(
                        ("boolean_operator", tuple(operator_values)),),
                ))
        profile = CurriculumProfile(
            "compatibility/v1-active-scope",
            grades=(GradeProfile(
                "B",
                enabled_capabilities=current_ids,
                capabilities=tuple(overrides),
            ),),
        )

    curriculum, bindings = from_legacy_course(
        canonical_course, answer_kinds=answer_kinds)
    return curriculum, bindings, profile, canonical_course
