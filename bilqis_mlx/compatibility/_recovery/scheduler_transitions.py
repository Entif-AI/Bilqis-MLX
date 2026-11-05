"""Historical Course mutation transitions retained for old run migration only."""
from __future__ import annotations

from dataclasses import replace

from ..curriculum import Course, validate


def append_next_grade(previous: Course, successor: Course, state):
    from ..curriculum.scheduler import _enter_grade, verify_state

    verify_state(previous, state)
    validate(successor)
    if previous.program_complete or state.stage != "AWAITING_NEXT_GRADE":
        raise ValueError("GRADE_APPEND_NOT_AT_PARTIAL_BOUNDARY")
    if len(successor.grades) != len(previous.grades) + 1:
        raise ValueError("GRADE_APPEND_REQUIRES_EXACTLY_ONE_NEW_GRADE")
    if tuple(successor.grades[:len(previous.grades)]) != previous.grades:
        raise ValueError("GRADE_APPEND_WOULD_CHANGE_PREVIOUS_GRADE")
    if any(g.assessment_sha256 is None for g in previous.grades):
        raise ValueError("GRADE_APPEND_UNSEALED_PREVIOUS_GRADE")
    if (previous.assessment_manifest_sha256 is not None and
            state.latest_rubric_digest != previous.assessment_manifest_sha256):
        raise ValueError("GRADE_APPEND_PRIOR_RUBRIC_NOT_VERIFIED")
    successor_ids = tuple(g.id for g in successor.grades)
    added = successor.grades[-1].id
    if added in state.champions:
        raise ValueError("GRADE_APPEND_FUTURE_CHAMPION_ALREADY_EXISTS")
    extended = replace(
        state,
        course_digest=successor.digest(),
        grade_exam_epoch=state.grade_exam_epoch + 1,
        active_grades=successor_ids,
        stage="MAIN",
        first_recovery=(),
        main_sweep_visited=(),
        revalidation_target_grade=None,
        latest_rubric_digest=None,
        pending_failures=(),
        teacher_soup_digest=None,
    )
    return _enter_grade(successor, extended, len(previous.grades))


def revise_admitted_grade(previous: Course, successor: Course, state):
    from ..curriculum.scheduler import verify_state

    verify_state(previous, state)
    validate(successor)
    if (previous.program_complete or successor.program_complete or
            tuple(grade.id for grade in previous.grades) !=
            tuple(grade.id for grade in successor.grades)):
        raise ValueError("GRADE_REVISION_REQUIRES_SAME_PARTIAL_GRADE_PROGRAM")
    changed = [
        (old, new) for old, new in zip(previous.grades, successor.grades)
        if old != new
    ]
    if len(changed) != 1:
        raise ValueError("GRADE_REVISION_REQUIRES_EXACTLY_ONE_CHANGED_GRADE")
    old_grade, new_grade = changed[0]
    old_by_id = {cap.id: cap for cap in old_grade.capabilities}
    new_by_id = {cap.id: cap for cap in new_grade.capabilities}
    if (not set(old_by_id) < set(new_by_id) or
            tuple(cap.id for cap in new_grade.capabilities[:len(old_grade.capabilities)]) !=
            tuple(old_by_id)):
        raise ValueError("GRADE_REVISION_MUST_APPEND_CAPABILITY_DEBT")
    for cap_id, old_cap in old_by_id.items():
        new_cap = new_by_id[cap_id]
        if replace(new_cap, lesson_generator=old_cap.lesson_generator) != old_cap:
            raise ValueError("GRADE_REVISION_CHANGED_EXISTING_SEMANTICS")

    champions = dict(state.champions)
    champions.pop(old_grade.id, None)
    current_caps = tuple(
        cap.id for grade in successor.grades
        if grade.id == state.grade
        for cap in grade.capabilities
    )
    revised = replace(
        state,
        course_digest=successor.digest(),
        stage="MAIN",
        queue=current_caps,
        first_recovery=(),
        champions=champions,
        grade_exam_epoch=state.grade_exam_epoch + 1,
        introduction_stage=0,
        main_sweep_visited=(),
        revalidation_target_grade=None,
        latest_rubric_digest=None,
        pending_failures=(),
        teacher_soup_digest=None,
    )
    verify_state(successor, revised)
    return revised, old_grade.id


def replace_admitted_grade(previous: Course, successor: Course, state):
    from ..curriculum.scheduler import _enter_grade, verify_state

    verify_state(previous, state)
    validate(successor)
    if (previous.program_complete or successor.program_complete or
            tuple(grade.id for grade in previous.grades) !=
            tuple(grade.id for grade in successor.grades)):
        raise ValueError("GRADE_REPLACEMENT_REQUIRES_SAME_PARTIAL_GRADE_PROGRAM")
    changed = [
        (old, new) for old, new in zip(previous.grades, successor.grades)
        if old != new
    ]
    if len(changed) != 1:
        raise ValueError("GRADE_REPLACEMENT_REQUIRES_EXACTLY_ONE_CHANGED_GRADE")
    old_grade, new_grade = changed[0]
    if old_grade.id != previous.grades[-1].id:
        raise ValueError("GRADE_REPLACEMENT_REQUIRES_LATEST_ADMITTED_GRADE")
    if len(new_grade.capabilities) >= len(old_grade.capabilities):
        raise ValueError("GRADE_REPLACEMENT_MUST_REDUCE_CAPABILITY_INVENTORY")

    champions = dict(state.champions)
    champions.pop(old_grade.id, None)
    rebound = replace(
        state,
        course_digest=successor.digest(),
        stage="MAIN",
        queue=(),
        first_recovery=(),
        champions=champions,
        grade_exam_epoch=state.grade_exam_epoch + 1,
        introduction_stage=0,
        main_sweep_visited=(),
        revalidation_target_grade=None,
        latest_rubric_digest=None,
        pending_failures=(),
        teacher_soup_digest=None,
    )
    rebound = _enter_grade(successor, rebound, state.grade_index)
    verify_state(successor, rebound)
    return rebound, old_grade.id
