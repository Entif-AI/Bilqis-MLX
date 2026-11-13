"""Reconstruct courses referenced by immutable historical receipts."""
from __future__ import annotations

from .providers import (
    BOOLEAN_RELEASE, BOOLEAN_COMPOSITE_RELEASE, BOOLEAN_IDENTIFICATION_RELEASE,
    INITIAL_RELEASE, MINIMAL_BOOLEAN_RELEASE, NUMERIC_RELEASE,
    NUMERIC_STAIRCASE_RELEASE, REGISTRY_COUNTING_TARGET,
    boolean_successor, minimal_boolean_successor, boolean_composite_successor,
    boolean_identification_successor, numeric_successor, staircase_successor,
)

def resolve_admitted_courses(historical_course, source_root, saved: dict,
                             *, pending: dict | None = None,
                             include_prospective: bool = True) -> dict[str, object]:
    """Reconstruct every release that may be referenced by saved/pending state."""
    from ...compatibility.historical_live_release import resume_grade_courses

    course_a, course_b = resume_grade_courses(historical_course, source_root, saved)
    courses = {course_a.version: course_a}
    modes = {saved.get("curriculum_mode")}
    if pending is not None:
        modes.add(pending.get("curriculum_mode"))
    if (BOOLEAN_RELEASE in modes or BOOLEAN_COMPOSITE_RELEASE in modes or
            BOOLEAN_IDENTIFICATION_RELEASE in modes or
            NUMERIC_RELEASE in modes or
            NUMERIC_STAIRCASE_RELEASE in modes or
            (include_prospective and
             saved.get("school", {}).get("stage") in (
                 "AWAITING_NEXT_GRADE", "AWAITING_NEXT_GRADE_WITH_DEBT"))):
        course_b = course_b or boolean_successor(course_a, source_root)
        courses[course_b.version] = course_b
    minimal_b = None
    parent_digest = saved.get("grade_c_parent_course_digest")
    if (MINIMAL_BOOLEAN_RELEASE in modes or parent_digest is not None or
            (include_prospective and
             saved.get("school", {}).get("stage") in (
                 "AWAITING_NEXT_GRADE", "AWAITING_NEXT_GRADE_WITH_DEBT") and
             saved.get("curriculum_mode") == INITIAL_RELEASE)):
        minimal_b = minimal_boolean_successor(course_a, source_root)
        courses[minimal_b.version] = minimal_b
    composite_b = None
    if (BOOLEAN_COMPOSITE_RELEASE in modes or BOOLEAN_IDENTIFICATION_RELEASE in modes or
            saved.get("grade_c_parent_course_digest") is not None or
            (include_prospective and saved.get("curriculum_mode") == BOOLEAN_RELEASE)):
        course_b = course_b or boolean_successor(course_a, source_root)
        composite_b = boolean_composite_successor(course_b, source_root)
        courses[composite_b.version] = composite_b
    identified_b = None
    if (BOOLEAN_IDENTIFICATION_RELEASE in modes or
            saved.get("grade_c_parent_course_digest") is not None or
            (include_prospective and
             saved.get("curriculum_mode") == BOOLEAN_COMPOSITE_RELEASE)):
        course_b = course_b or boolean_successor(course_a, source_root)
        composite_b = composite_b or boolean_composite_successor(course_b, source_root)
        courses[composite_b.version] = composite_b
        identified_b = boolean_identification_successor(composite_b, source_root)
        courses[identified_b.version] = identified_b
    if (NUMERIC_RELEASE in modes or NUMERIC_STAIRCASE_RELEASE in modes or
            (include_prospective and saved.get("curriculum_mode") == BOOLEAN_IDENTIFICATION_RELEASE and
             saved.get("school", {}).get("stage") in (
                 "AWAITING_NEXT_GRADE", "AWAITING_NEXT_GRADE_WITH_DEBT"))):
        parent_b = course_b
        if composite_b is None and parent_digest is not None:
            composite_b = boolean_composite_successor(course_b, source_root)
            courses[composite_b.version] = composite_b
        if identified_b is None and parent_digest is not None:
            identified_b = boolean_identification_successor(composite_b, source_root)
            courses[identified_b.version] = identified_b
        if minimal_b is not None and parent_digest == minimal_b.digest():
            parent_b = minimal_b
        elif identified_b is not None and (
                parent_digest == identified_b.digest() or
                saved.get("curriculum_mode") == BOOLEAN_IDENTIFICATION_RELEASE):
            parent_b = identified_b
        elif composite_b is not None and parent_digest == composite_b.digest():
            parent_b = composite_b
        elif saved.get("curriculum_mode") == BOOLEAN_COMPOSITE_RELEASE:
            parent_b = composite_b
        pinned_maximum = (REGISTRY_COUNTING_TARGET
                          if NUMERIC_STAIRCASE_RELEASE in modes
                          else saved.get("numeric_maximum"))
        if (pending or {}).get("curriculum_mode") == NUMERIC_RELEASE and pinned_maximum is None:
            pinned_maximum = pending.get("numeric_maximum")
        course_c, _ = numeric_successor(parent_b, maximum=pinned_maximum)
        courses[course_c.version] = course_c
        if NUMERIC_STAIRCASE_RELEASE in modes:
            active = pending if (pending or {}).get("curriculum_mode") == NUMERIC_STAIRCASE_RELEASE else saved
            staircase = staircase_successor(parent_b, maximum=active["numeric_maximum"])
            courses[staircase.version] = staircase
    return courses


def course_for_mode(courses: dict[str, object], mode: str | None, historical_course):
    if mode is None:
        return historical_course
    try:
        return courses[mode]
    except KeyError as exc:
        raise ValueError("FACTORY_RELEASE_COURSE_NOT_LOADED:" + str(mode)) from exc


def predecessor_course(courses: dict[str, object], current_course):
    """Find the unique admitted release whose grade prefix owns current_course."""
    if len(current_course.grades) < 2:
        raise ValueError("FACTORY_RELEASE_HAS_NO_PREDECESSOR")
    prefix = current_course.grades[:-1]
    matches = [course for course in courses.values()
               if course.grades == prefix]
    unique = {course.digest(): course for course in matches}
    if len(unique) != 1:
        raise ValueError("FACTORY_RELEASE_PREDECESSOR_AMBIGUOUS")
    return next(iter(unique.values()))
