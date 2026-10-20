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
from ..factory.executable_release import compile_executable_factory_release
from ..factory.live_answers import live_answer_registry
from ..factory.schedule import schedule_program_from_executable_release
from ..live_grade_b import live_course as build_boolean_grade
from ..minimal_grade_b import build_course as build_minimal_boolean
from ..source_adapters.school import live_source_registry


LIVE_V2_VERIFICATION_SEED = 2026101905


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

    canonical_b = _canonical_boolean_course(grade_a, source_root)
    current_b = next((grade for grade in course.grades if grade.id == "B"), None)
    if current_b is None:
        canonical_course = canonical_b
        profile = CurriculumProfile(
            "compatibility/v1-a-only",
            grades=(GradeProfile("B", enabled_capabilities=()),),
        )
    else:
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
        canonical_course = (
            canonical_b
            if len(course.grades) == 2
            else replace(
                course,
                grades=grades,
                # Preserve higher-grade provenance only when higher grades are
                # actually present. A/B semantic and source authority comes
                # from the single canonical full-B declaration.
                program_complete=course.program_complete,
            )
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


def compile_projected_executable_release(
        course: Course, grade_a: Course, source_root, graph: dict, *,
        predecessor=None):
    """Compile one v2 artifact from the historical live-course boundary."""
    answers = live_answer_registry()
    curriculum, bindings, profile, canonical_course = project_legacy_course(
        course, grade_a, source_root, answer_kinds=answers.kinds)
    release = compile_executable_factory_release(
        curriculum, bindings, profile,
        live_source_registry(), answers,
        source_root=source_root,
        graph=graph,
        verification_seed=LIVE_V2_VERIFICATION_SEED,
        legacy_course=canonical_course,
        predecessor=predecessor,
    )
    return release, schedule_program_from_executable_release(release), canonical_course


def legacy_course_for_profile(
        grade_a: Course, source_root, profile: CurriculumProfile) -> Course:
    """Temporary historical Course view for consumers not yet on v2 projections."""
    canonical = _canonical_boolean_course(grade_a, source_root)
    grade_profile = next(
        (item for item in profile.grades if item.grade_id == "B"), None)
    if grade_profile is None:
        return canonical
    enabled = grade_profile.enabled_capabilities
    if enabled == ():
        return grade_a
    canonical_ids = tuple(cap.id for cap in canonical.grades[-1].capabilities)
    if enabled is None or enabled == canonical_ids:
        return canonical
    if enabled == ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"):
        return build_minimal_boolean(grade_a, source_root)
    raise ValueError("FACTORY_COMPATIBILITY_PROFILE_VIEW_UNSUPPORTED")
