"""Release-owned source dispatch for the concrete admitted school curriculum."""
from __future__ import annotations

from .live_grade_a import (GENERATOR as A_GENERATOR, RELEASE as A_RELEASE,
    draw_predicates, generator_source_digest)
from .live_grade_b import (GENERATOR as B_GENERATOR, RELEASE as B_RELEASE,
    draw_connectives, constructor_digest as b_digest)
from .live_grade_c import (GENERATOR as C_GENERATOR, RELEASE as C_RELEASE,
    constructor_digest as c_digest, draw as draw_numbers)


def cohort_contract(course):
    releases = {"A": (A_RELEASE, A_GENERATOR, generator_source_digest),
                "B": (B_RELEASE, B_GENERATOR, b_digest),
                "C": (C_RELEASE, C_GENERATOR, c_digest)}
    grade = course.grades[-1]
    if grade.id not in releases:
        raise ValueError("HUMAN_TRAINER_UNADMITTED_GRADE_COHORT")
    release, generator, fingerprint = releases[grade.id]
    source_sha = fingerprint()
    if grade.id == "A":
        from .historical_live_release import (
            ABI_REFACTORED_A_GENERATOR_SHA256,
            HISTORICAL_A_GENERATOR_SHA256,
            HISTORICAL_A_RUBRIC_SHA256,
        )
        if grade.assessment_sha256 == HISTORICAL_A_RUBRIC_SHA256:
            if source_sha != ABI_REFACTORED_A_GENERATOR_SHA256:
                raise ValueError("HISTORICAL_GRADE_A_SOURCE_COMPATIBILITY_NOT_PROVEN")
            source_sha = HISTORICAL_A_GENERATOR_SHA256
    return grade.assessment_sha256, release, generator, source_sha


def numeric_maximum(course):
    family = next(f for c in course.grades[-1].capabilities
                  for f in c.answer_families if f.kind == "numeric_active")
    return len(family.values)-1


def lesson_contract(course, grade):
    from dataclasses import replace
    prefix = course.grades[:next(i+1 for i, g in enumerate(course.grades) if g.id == grade)]
    return cohort_contract(replace(course, grades=prefix))


def draw_course_rows(source_root, graph, course, *, seed, capability=None, each=None):
    scopes = {g.id for g in course.grades}
    if not scopes <= {"A", "B", "C"}:
        raise ValueError("HUMAN_TRAINER_UNADMITTED_GRADE_SOURCE")
    selected = {capability.split(".", 1)[0]} if capability else scopes
    if not selected <= scopes:
        raise ValueError("HUMAN_TRAINER_CAPABILITY_NOT_IN_COURSE")
    expected = {name: each if each is not None else count for grade in course.grades
                for name, count in grade.exam_item_counts
                if capability is None or name == capability}
    rows = []
    constructors = {"A": draw_predicates, "B": draw_connectives}
    for grade in course.grades:
        if grade.id not in selected:
            continue
        count = each if each is not None else grade.exam_item_counts[0][1]
        if grade.id in constructors:
            rows.extend(constructors[grade.id](source_root, graph, seed=seed,
                                               capability=capability, each=count))
        else:
            rows.extend(draw_numbers(graph, seed=seed, maximum=numeric_maximum(course),
                                     capability=capability, each=count))
    actual = {cap: sum(r["capability"] == cap for r in rows) for cap in expected}
    if not expected or actual != expected or len(rows) != sum(expected.values()):
        raise ValueError("HUMAN_TRAINER_LIVE_GRADE_NOT_COMPREHENSIVE")
    return list(rows)
