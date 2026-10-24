"""Program-roster transitions for durable school state."""
from __future__ import annotations

from dataclasses import replace
from enum import Enum

from bilqis_mlx.factory.schedule import ScheduleProgram

from .school_state import SchoolState, _caps, _program


class ProgramAdoptionError(str, Enum):
    SCHEDULE_PROGRAM_REQUIRED = "FACTORY_SCHEDULE_PROGRAM_REQUIRED"
    APPEND_INVALID = "FACTORY_SCHEDULE_APPEND_INVALID"
    APPEND_REQUIRES_GRADUATED_PREFIX = (
        "FACTORY_SCHEDULE_APPEND_REQUIRES_GRADUATED_PREFIX")
    APPEND_FUTURE_CHAMPION_EXISTS = (
        "FACTORY_SCHEDULE_APPEND_FUTURE_CHAMPION_EXISTS")
    DEBT_REQUIRES_PARTIAL_PROGRAM = (
        "DEBT_GRADE_APPEND_REQUIRES_PARTIAL_PROGRAM")
    DEBT_REQUIRES_EXPLICIT_MASTERY = (
        "DEBT_GRADE_APPEND_REQUIRES_EXPLICIT_MASTERY_DEBT")
    DEBT_OUTSIDE_PREVIOUS_PROGRAM = (
        "DEBT_GRADE_APPEND_DEBT_OUTSIDE_PREVIOUS_PROGRAM")
    APPEND_REQUIRES_ONE_NEW_GRADE = (
        "GRADE_APPEND_REQUIRES_EXACTLY_ONE_NEW_GRADE")
    APPEND_WOULD_CHANGE_PREVIOUS = "GRADE_APPEND_WOULD_CHANGE_PREVIOUS_GRADE"
    APPEND_UNSEALED_PREVIOUS = "GRADE_APPEND_UNSEALED_PREVIOUS_GRADE"
    DEBT_DURING_REVALIDATION = (
        "DEBT_GRADE_APPEND_DURING_REVALIDATION_FORBIDDEN")
    DEBT_NONDEBT_GRADE_NOT_MASTERED = (
        "DEBT_GRADE_APPEND_NONDEBT_GRADE_NOT_MASTERED")
    APPEND_FUTURE_CHAMPION_ALREADY_EXISTS = (
        "GRADE_APPEND_FUTURE_CHAMPION_ALREADY_EXISTS")
    PRIOR_EXPANSION_INVALID = "FACTORY_SCHEDULE_PRIOR_GRADE_EXPANSION_INVALID"
    PRIOR_EXPANSION_NOT_ADDITIVE = (
        "FACTORY_SCHEDULE_PRIOR_GRADE_EXPANSION_NOT_ADDITIVE")
    PRIOR_EXPANSION_CHANGED_EXISTING = (
        "FACTORY_SCHEDULE_PRIOR_GRADE_EXPANSION_CHANGED_EXISTING_CAPABILITY")
    REVISION_INVALID = "FACTORY_SCHEDULE_REVISION_INVALID"
    REVISION_REQUIRES_ACTIVE_GRADE = (
        "FACTORY_SCHEDULE_REVISION_REQUIRES_ACTIVE_GRADE")


def _scheduler():
    from . import scheduler
    return scheduler


def adopt_appended_program(previous: ScheduleProgram,
                           successor: ScheduleProgram,
                           state: SchoolState) -> SchoolState:
    """Admit exactly one appended projected grade without knowing its identity."""
    scheduler = _scheduler()
    if (not isinstance(previous, ScheduleProgram) or
            not isinstance(successor, ScheduleProgram)):
        raise TypeError(ProgramAdoptionError.SCHEDULE_PROGRAM_REQUIRED.value)
    scheduler.verify_state(previous, state)
    previous_ids = tuple(grade.id for grade in previous.grades)
    successor_ids = tuple(grade.id for grade in successor.grades)
    if (previous.program_complete or
            state.stage != "AWAITING_NEXT_GRADE" or
            len(successor_ids) != len(previous_ids) + 1 or
            successor_ids[:-1] != previous_ids or
            successor.grades[:-1] != previous.grades):
        raise ValueError(ProgramAdoptionError.APPEND_INVALID.value)
    if state.grade not in state.champions:
        raise ValueError(
            ProgramAdoptionError.APPEND_REQUIRES_GRADUATED_PREFIX.value)
    added = successor_ids[-1]
    if added in state.champions:
        raise ValueError(
            ProgramAdoptionError.APPEND_FUTURE_CHAMPION_EXISTS.value)
    extended = replace(
        state, course_digest=successor.digest(),
        grade_exam_epoch=state.grade_exam_epoch + 1,
        active_grades=successor_ids, stage="MAIN", first_recovery=(),
        main_sweep_visited=(), revalidation_target_grade=None,
        latest_rubric_digest=None, pending_failures=(),
        teacher_soup_digest=None, carried_mastery_debt=())
    return scheduler._enter_grade(
        successor, extended, len(previous.grades))


def append_next_grade_with_debt(
        previous, successor, state: SchoolState,
        mastery_debt: tuple[str, ...]) -> SchoolState:
    """Append one grade while preserving explicitly unresolved prior debt."""
    scheduler = _scheduler()
    previous, successor = _program(previous), _program(successor)
    scheduler.verify_state(previous, state)
    if previous.program_complete:
        raise ValueError(ProgramAdoptionError.DEBT_REQUIRES_PARTIAL_PROGRAM.value)
    if not mastery_debt or len(set(mastery_debt)) != len(mastery_debt):
        raise ValueError(
            ProgramAdoptionError.DEBT_REQUIRES_EXPLICIT_MASTERY.value)
    previous_caps = set(_caps(previous, tuple(g.id for g in previous.grades)))
    if not set(mastery_debt) <= previous_caps:
        raise ValueError(
            ProgramAdoptionError.DEBT_OUTSIDE_PREVIOUS_PROGRAM.value)
    if len(successor.grades) != len(previous.grades) + 1:
        raise ValueError(
            ProgramAdoptionError.APPEND_REQUIRES_ONE_NEW_GRADE.value)
    if tuple(successor.grades[:len(previous.grades)]) != previous.grades:
        raise ValueError(ProgramAdoptionError.APPEND_WOULD_CHANGE_PREVIOUS.value)
    if any(g.assessment_sha256 is None for g in previous.grades):
        raise ValueError(ProgramAdoptionError.APPEND_UNSEALED_PREVIOUS.value)
    if state.revalidation_target_grade is not None:
        raise ValueError(ProgramAdoptionError.DEBT_DURING_REVALIDATION.value)
    grade_by_capability = {
        capability.id: grade.id
        for grade in previous.grades
        for capability in grade.capabilities}
    debt_grades = {
        grade_by_capability[capability] for capability in mastery_debt}
    mastered_required = set(state.active_grades) - debt_grades
    if not mastered_required <= set(state.champions):
        raise ValueError(
            ProgramAdoptionError.DEBT_NONDEBT_GRADE_NOT_MASTERED.value)
    added = successor.grades[-1].id
    if added in state.champions:
        raise ValueError(
            ProgramAdoptionError.APPEND_FUTURE_CHAMPION_ALREADY_EXISTS.value)
    extended = replace(
        state, course_digest=successor.digest(),
        grade_exam_epoch=state.grade_exam_epoch + 1,
        active_grades=tuple(g.id for g in successor.grades),
        stage="MAIN", first_recovery=(), main_sweep_visited=(),
        revalidation_target_grade=None, latest_rubric_digest=None,
        pending_failures=(), teacher_soup_digest=None,
        carried_mastery_debt=tuple(mastery_debt))
    return scheduler._enter_grade(
        successor, extended, len(previous.grades))


def adopt_expanded_prior_grade(previous: ScheduleProgram,
                               successor: ScheduleProgram,
                               state: SchoolState) -> tuple[SchoolState, str]:
    """Add capability debt to an earlier grade without leaving the frontier."""
    scheduler = _scheduler()
    if (not isinstance(previous, ScheduleProgram) or
            not isinstance(successor, ScheduleProgram)):
        raise TypeError(ProgramAdoptionError.SCHEDULE_PROGRAM_REQUIRED.value)
    scheduler.verify_state(previous, state)
    previous_ids = tuple(grade.id for grade in previous.grades)
    successor_ids = tuple(grade.id for grade in successor.grades)
    changed = tuple(
        index
        for index, (old, new) in enumerate(zip(previous.grades, successor.grades))
        if old.capabilities != new.capabilities or
        old.teaching_stages != new.teaching_stages)
    if (previous_ids != successor_ids or len(changed) != 1 or
            changed[0] >= state.grade_index):
        raise ValueError(ProgramAdoptionError.PRIOR_EXPANSION_INVALID.value)
    index = changed[0]
    old_grade, new_grade = previous.grades[index], successor.grades[index]
    old_caps = tuple(cap.id for cap in old_grade.capabilities)
    new_caps = tuple(cap.id for cap in new_grade.capabilities)
    if (not set(old_caps) < set(new_caps) or
            tuple(cap for cap in new_caps if cap in set(old_caps)) != old_caps):
        raise ValueError(ProgramAdoptionError.PRIOR_EXPANSION_NOT_ADDITIVE.value)
    old_by_id = {cap.id: cap for cap in old_grade.capabilities}
    new_by_id = {cap.id: cap for cap in new_grade.capabilities}
    if any(new_by_id[cap] != old for cap, old in old_by_id.items()):
        raise ValueError(
            ProgramAdoptionError.PRIOR_EXPANSION_CHANGED_EXISTING.value)
    added = tuple(cap for cap in new_caps if cap not in old_by_id)
    debt = tuple((
        *state.carried_mastery_debt,
        *(cap for cap in added if cap not in state.carried_mastery_debt)))
    champions = dict(state.champions)
    champions.pop(old_grade.id, None)
    rebound = replace(
        state, course_digest=successor.digest(), champions=champions,
        carried_mastery_debt=debt,
        grade_exam_epoch=state.grade_exam_epoch + 1,
        latest_rubric_digest=None, teacher_soup_digest=None)
    scheduler.verify_state(successor, rebound)
    return rebound, old_grade.id


def adopt_revised_program(previous: ScheduleProgram,
                          successor: ScheduleProgram,
                          state: SchoolState) -> tuple[SchoolState, str]:
    """Rebind one active projected grade after a profile roster revision."""
    scheduler = _scheduler()
    if (not isinstance(previous, ScheduleProgram) or
            not isinstance(successor, ScheduleProgram)):
        raise TypeError(ProgramAdoptionError.SCHEDULE_PROGRAM_REQUIRED.value)
    scheduler.verify_state(previous, state)
    previous_ids = tuple(grade.id for grade in previous.grades)
    successor_ids = tuple(grade.id for grade in successor.grades)
    changed = tuple(
        index
        for index, (old, new) in enumerate(zip(previous.grades, successor.grades))
        if old != new)
    if (previous_ids != successor_ids or len(changed) != 1 or
            changed[0] != len(previous.grades) - 1):
        raise ValueError(ProgramAdoptionError.REVISION_INVALID.value)
    revised_grade = successor_ids[changed[0]]
    if state.grade != revised_grade:
        raise ValueError(
            ProgramAdoptionError.REVISION_REQUIRES_ACTIVE_GRADE.value)
    champions = dict(state.champions)
    champions.pop(revised_grade, None)
    successor_caps = set(_caps(successor, state.active_grades))
    active_debt = tuple(
        capability for capability in state.carried_mastery_debt
        if capability in successor_caps)
    rebound = replace(
        state, course_digest=successor.digest(), stage="MAIN", queue=(),
        first_recovery=(), champions=champions,
        carried_mastery_debt=active_debt,
        grade_exam_epoch=state.grade_exam_epoch + 1,
        introduction_stage=0, main_sweep_visited=(),
        revalidation_target_grade=None, latest_rubric_digest=None,
        pending_failures=(), teacher_soup_digest=None)
    rebound = scheduler._enter_grade(
        successor, rebound, state.grade_index)
    scheduler.verify_state(successor, rebound)
    return rebound, revised_grade


def append_next_grade(previous, successor, state: SchoolState) -> SchoolState:
    from bilqis_mlx.compatibility.scheduler_transitions import (
        append_next_grade as legacy,
    )
    return legacy(previous, successor, state)


def revise_admitted_grade(previous, successor, state: SchoolState):
    from bilqis_mlx.compatibility.scheduler_transitions import (
        revise_admitted_grade as legacy,
    )
    return legacy(previous, successor, state)


def replace_admitted_grade(previous, successor, state: SchoolState):
    from bilqis_mlx.compatibility.scheduler_transitions import (
        replace_admitted_grade as legacy,
    )
    return legacy(previous, successor, state)
