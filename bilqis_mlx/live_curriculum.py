"""Factory-owned source and cohort contracts for the admitted school curriculum."""
from __future__ import annotations

from .source_adapters.school import live_source_registry
from .factory.generation import draw_release_rows
from .factory.release import compile_factory_release


def _grade_cohort_contract(course, grade):
    registry = live_source_registry()
    release = compile_factory_release(course, registry)
    definitions = [item for item in release.capabilities if item.grade_id == grade.id]
    if not definitions:
        raise ValueError("FACTORY_COHORT_GRADE_NOT_RELEASED")
    adapter_ids = {item.source_adapter_id for item in definitions}
    if len(adapter_ids) != 1:
        raise ValueError("FACTORY_COHORT_REQUIRES_ONE_SOURCE_ADAPTER_PER_GRADE")
    adapter = release.source_adapter_map[next(iter(adapter_ids))]
    known_releases = {name for name, _ in adapter.cohort_releases}
    schema = course.version if (grade is course.grades[-1] and
                                course.version in known_releases) else (
        adapter.cohort_releases[0][0] if adapter.cohort_releases else course.version)
    source_sha = adapter.cohort_code_sha256(schema)
    # One narrow compatibility rule preserves the already-published Grade-A
    # cohort identity after the semantic-ABI refactor. It does not participate
    # in current/future grade dispatch.
    if grade.assessment_sha256:
        from .compatibility.historical_live_release import (
            ABI_REFACTORED_A_GENERATOR_SHA256,
            HISTORICAL_A_GENERATOR_SHA256,
            HISTORICAL_A_RUBRIC_SHA256,
        )
        if grade.assessment_sha256 == HISTORICAL_A_RUBRIC_SHA256:
            if source_sha != ABI_REFACTORED_A_GENERATOR_SHA256:
                raise ValueError("HISTORICAL_GRADE_A_SOURCE_COMPATIBILITY_NOT_PROVEN")
            source_sha = HISTORICAL_A_GENERATOR_SHA256
    return grade.assessment_sha256, schema, adapter.cohort_generator, source_sha


def cohort_contract(course):
    return _grade_cohort_contract(course, course.grades[-1])


def numeric_maximum(course):
    family = next(f for c in course.grades[-1].capabilities
                  for f in c.answer_families if f.kind == "numeric_active")
    return len(family.values)-1


def lesson_contract(course, grade):
    try:
        selected = next(item for item in course.grades if item.id == grade)
    except StopIteration as exc:
        raise ValueError("FACTORY_LESSON_GRADE_NOT_RELEASED") from exc
    return _grade_cohort_contract(course, selected)


def draw_course_rows(source_root, graph, course, *, seed, capability=None, each=None):
    registry = live_source_registry()
    release = compile_factory_release(course, registry)
    return draw_release_rows(
        source_root, graph, release, registry, seed=seed,
        capability=capability, each=each)
