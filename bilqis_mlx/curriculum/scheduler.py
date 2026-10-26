"""Deterministic, neural-inert school-grade scheduler and promotion contract.

No optimizer, teacher/model or exam generator is invoked here. This state
machine accepts only explicit same-checkpoint scores from a separate evaluator.
It prevents an old mixed-step score board from certifying new grade mastery.
"""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus, SCHOOL

from dataclasses import asdict, replace
from fractions import Fraction
from .promotion import (
    PROMOTION_MEAN_FLOOR, PromotionError, _promotion_debt, _boundary_mastery_debt, _introduced_grade_capabilities, _mean_accuracy, _promotion_sweep_fields_cleared, _verify_promotion_sweep_state, _promotion_sweep_due, _start_promotion_sweep,
)
from .program_adoption import (
    adopt_appended_program, adopt_expanded_prior_grade, adopt_revised_program,
    append_next_grade, append_next_grade_with_debt, replace_admitted_grade,
    revise_admitted_grade,
)
from .foundational_rehearsal import (
    FOUNDATIONAL_DEBT_RUN_INTERVAL,
    rehearsal_plan as _foundational_rehearsal_plan,
)
from .debt_priority import (
    NONGATING_DEBT_RUN_INTERVAL,
    debt_run_due as _b_debt_run_due,
    debt_run_queue as _b_debt_run_queue,
    frontier_recovery_queue as _frontier_recovery_queue,
    imperfect_ranked as _imperfect_ranked,
    roles as _nongating_debt_priority_roles,
)
from .school_state import Assessment, SchoolState, Score, _caps, _program
import hashlib
import json
from pathlib import Path

from bilqis_mlx.learning.champions import Checkpoint, repoint_earlier, vote_counts, soup_weights
from bilqis_mlx.factory.schedule import ScheduleProgram
from bilqis_mlx.runtime.disk import atomic_text


SCHOOL_STATE_SCHEMA = "bilqis.mlx.letter-grade/v1"
STAGES = frozenset(("MAIN", "ASSESS_MAIN", "RECOVERY_1", "ASSESS_RECOVERY_1",
                    "RECOVERY_2", "ASSESS_RECOVERY_2", "PROMOTION_SWEEP",
                    "ASSESS_PROMOTION_SWEEP", "AWAITING_TEACHER_SOUP",
                    "AWAITING_NEXT_GRADE", "AWAITING_NEXT_GRADE_WITH_DEBT",
                    "WHOLE_SCHOOL_MASTERED", "DEFERRED_STAGNATION"))
def _enter_due_b_debt_run(program, state: SchoolState,
                          snapshot: Assessment, *,
                          allowed_capabilities: tuple[str, ...] | None = None,
                          reset_sweep: bool = True) -> SchoolState | None:
    if not _b_debt_run_due(program, state):
        return None
    queue = _b_debt_run_queue(
        program, state, snapshot.scores,
        allowed_capabilities=allowed_capabilities)
    if not queue:
        return None
    debt_grade, _ = _nongating_debt_priority_roles(program, state)
    entered = _enter_grade(
        program, state, state.active_grades.index(debt_grade),
        stage="MAIN", first_recovery=(),
        main_sweep_visited=() if reset_sweep else state.main_sweep_visited,
        latest_rubric_digest=snapshot.rubric_digest)
    return replace(entered, queue=queue)


def _enter_due_foundational_rehearsal(
        program, state: SchoolState, snapshot: Assessment, *,
        allowed_capabilities: tuple[str, ...] | None = None,
        reset_sweep: bool = True) -> SchoolState | None:
    plan = _foundational_rehearsal_plan(
        program, state, snapshot.scores,
        allowed_capabilities=allowed_capabilities,
        priority_active=_nongating_debt_priority_roles(program, state) is not None)
    if plan is None:
        return None
    grade, queue = plan
    entered = _enter_grade(
        program, state, state.active_grades.index(grade),
        stage="MAIN", first_recovery=(),
        main_sweep_visited=() if reset_sweep else state.main_sweep_visited,
        latest_rubric_digest=snapshot.rubric_digest)
    return replace(entered, queue=queue)


def migrate_b_full_run_epoch(program, state: SchoolState) -> SchoolState:
    """Adopt ADR-094 without inventing learning or preserving single-B crumbs."""
    program = _program(program)
    roles = _nongating_debt_priority_roles(program, state)
    if roles is None:
        return replace(state, non_b_training_turns_since_b_run=0)
    debt_grade, frontier_grade = roles
    migrated = replace(
        state, non_b_training_turns_since_b_run=NONGATING_DEBT_RUN_INTERVAL)
    if migrated.stage not in ("MAIN", "RECOVERY_1", "RECOVERY_2"):
        return migrated
    debt_caps = set(_caps(program, (debt_grade,)))
    if (migrated.grade != debt_grade and
            any(cap in debt_caps for cap in migrated.queue)):
        return _enter_grade(
            program, migrated, migrated.active_grades.index(frontier_grade),
            stage="MAIN", first_recovery=(), main_sweep_visited=(),
            latest_rubric_digest=migrated.latest_rubric_digest)
    return migrated


def migrate_foundational_rehearsal_epoch(program, state: SchoolState) -> SchoolState:
    """Let legacy long-lived runs immediately reconsider decayed foundations."""
    program = _program(program)
    if _nongating_debt_priority_roles(program, state) is None:
        return replace(
            state, non_foundational_training_turns_since_foundational_run=0)
    return replace(
        state,
        non_foundational_training_turns_since_foundational_run=
        FOUNDATIONAL_DEBT_RUN_INTERVAL)


def migrate_promotion_sweep_attempt_epoch(program, state: SchoolState) -> SchoolState:
    """Disarm legacy score-flux retries until the student or scope changes.

    Historical receipts did not remember which unchanged student had already
    attempted the current promotion scope. Treat the current checkpoint/scope as
    already attempted rather than inventing fresh qualification authority on resume.
    """
    program = _program(program)
    return replace(
        state,
        promotion_sweep_attempt_student_sha256=state.current_student.sha256,
        promotion_sweep_attempt_scope=_introduced_grade_capabilities(program, state),
    )


def migrate_c_frontier_priority_epoch(program, state: SchoolState) -> SchoolState:
    """Re-anchor pre-policy queued work without inventing neural progress.

    Older receipts can resume in a full B MAIN/recovery queue.  The new budget
    begins at zero, so that inherited burst would violate the policy before its
    counters had any chance to govern.  Only teaching stages are re-anchored;
    an owed ASSESS_* boundary remains untouched and is consumed normally.
    """
    program = _program(program)
    roles = _nongating_debt_priority_roles(program, state)
    if (roles is None or
            state.stage not in ("MAIN", "RECOVERY_1", "RECOVERY_2")):
        return state
    debt_grade, frontier_grade = roles
    debt_caps = set(_caps(program, (debt_grade,)))
    if not state.queue or state.queue[0] not in debt_caps:
        return state
    return _enter_grade(
        program, state, state.active_grades.index(frontier_grade),
        stage="MAIN", first_recovery=(), main_sweep_visited=(),
        latest_rubric_digest=state.latest_rubric_digest)








def _score_pool(program, state: SchoolState) -> tuple[str, ...]:
    program = _program(program)
    represented = set(state.champions) | {state.grade}
    if state.carried_mastery_debt:
        # Debt admission opens new learning territory without letting an
        # unresolved earlier grade disappear from cumulative assessment.
        represented.update(state.active_grades)
    if state.latest_rubric_digest is not None:
        sealed = [index for index, grade in enumerate(program.grades)
                  if grade.id in state.active_grades and
                  grade.assessment_sha256 == state.latest_rubric_digest]
        if sealed:
            cutoff = max(sealed)
            represented.update(
                grade.id for grade in program.grades[:cutoff + 1]
                if grade.id in state.active_grades)
    seen = tuple(g.id for g in program.grades if g.id in represented)
    frontiers = dict(state.introduction_frontiers)
    introduced = set()
    for grade in program.grades:
        if grade.id not in represented:
            continue
        if not grade.teaching_stages or grade.id in state.champions:
            introduced.update(capability.id for capability in grade.capabilities)
            continue
        stage_index = (
            state.introduction_stage if grade.id == state.grade
            else frontiers.get(grade.id, 0)
        )
        introduced.update(
            capability
            for stage in grade.teaching_stages[:stage_index + 1]
            for capability in stage
        )
    return tuple(cap for cap in _caps(program, seen) if cap in introduced)


def assessment_capabilities(program, state: SchoolState) -> tuple[str, ...]:
    """Expose only already introduced concepts plus earlier mastered grades."""
    program = _program(program)
    verify_state(program, state)
    return _score_pool(program, state)


def _main_queue(program, state: SchoolState) -> tuple[str, ...]:
    program = _program(program)
    return tuple(c for c in _score_pool(program, state)
                 if c in _caps(program, (state.grade,)))


def _frontiers_with(state: SchoolState, grade: str, stage: int) -> tuple[tuple[str, int], ...]:
    frontiers = dict(state.introduction_frontiers)
    frontiers[grade] = stage
    return tuple((grade_id, frontiers[grade_id])
                 for grade_id in state.active_grades if grade_id in frontiers)


def _at_introduction_stage(state: SchoolState, introduction_stage: int,
                           **changes) -> SchoolState:
    return replace(
        state,
        introduction_stage=introduction_stage,
        introduction_frontiers=_frontiers_with(
            state, state.grade, introduction_stage),
        **changes,
    )


def _enter_grade(program, state: SchoolState, grade_index: int, **changes) -> SchoolState:
    program = _program(program)
    grade_id = state.active_grades[grade_index]
    grade = next(g for g in program.grades if g.id == grade_id)
    frontiers = dict(state.introduction_frontiers)
    if 0 <= state.grade_index < len(state.active_grades):
        frontiers[state.grade] = state.introduction_stage
    index = (len(grade.teaching_stages)-1
             if grade_id in state.champions and grade.teaching_stages
             else frontiers.get(grade_id, 0))
    frontiers[grade_id] = index
    entered = replace(
        state, grade_index=grade_index, introduction_stage=index,
        introduction_frontiers=tuple(
            (active_grade, frontiers[active_grade])
            for active_grade in state.active_grades if active_grade in frontiers),
        **changes)
    queue = _main_queue(program, entered)
    if grade.teaching_stages and grade_id not in entered.champions:
        queue = grade.teaching_stages[index]
    return replace(entered, queue=queue)


def start_new(program, initial_student: Checkpoint) -> SchoolState:
    program = _program(program)
    state = SchoolState(schema="bilqis.mlx.letter-grade/v1",
                       course_digest=program.digest(),
                       active_grades=tuple(g.id for g in program.grades),
                       grade_index=0, stage="MAIN",
                       queue=_caps(program, (program.grades[0].id,)),
                       first_recovery=(), current_student=initial_student,
                       champions={})
    return replace(state, queue=_main_queue(program, state))




def _school_state_boundary_issue(program, state: SchoolState):
    """Return the first boundary violation without discarding its evidence."""
    program = _program(program)
    runtime_digest = program.digest()
    if state.schema != SCHOOL_STATE_SCHEMA:
        return SCHOOL.STATE.SCHEMA_MISMATCH, {
            "actual_schema": state.schema,
            "expected_schema": SCHOOL_STATE_SCHEMA,
        }
    if state.course_digest != runtime_digest:
        return SCHOOL.STATE.COURSE_DIGEST_MISMATCH, {
            "saved_course_digest": state.course_digest,
            "runtime_course_digest": runtime_digest,
        }
    if state.stage not in STAGES:
        return SCHOOL.STATE.STAGE_INVALID, {
            "actual_stage": state.stage,
        }
    if not state.active_grades:
        return SCHOOL.STATE.ACTIVE_GRADES_EMPTY, {}
    if not 0 <= state.grade_index < len(state.active_grades):
        return SCHOOL.STATE.GRADE_INDEX_OUT_OF_RANGE, {
            "grade_index": state.grade_index,
            "active_grade_count": len(state.active_grades),
        }
    return None


def verify_state(program, state: SchoolState):
    program = _program(program)
    boundary_issue = _school_state_boundary_issue(program, state)
    if boundary_issue is not None:
        spec, context = boundary_issue
        ErrorBus.raise_(spec, **context)
    known = {g.id for g in program.grades}
    if (not set(state.active_grades) <= known or
            tuple(g.id for g in program.grades if g.id in state.active_grades) != state.active_grades or
            not set(state.champions) <= known):
        raise ValueError("INVALID_GRADE_PROGRAM_OR_CHAMPIONS")
    if any(cap not in _score_pool(program, state) for cap in state.queue + state.first_recovery):
        raise ValueError("QUEUE_CAPABILITY_OUTSIDE_ACTIVE_AND_PASSED_GRADES")
    if (state.visits < 0 or state.school_cycles < 1 or
            type(state.grade_exam_epoch) is not int or state.grade_exam_epoch < 0 or
            type(state.introduction_stage) is not int or state.introduction_stage < 0 or
            type(state.frontier_priority_visits) is not int or
            state.frontier_priority_visits < 0 or
            type(state.nongating_b_visits) is not int or
            state.nongating_b_visits < 0 or
            type(state.non_b_training_turns_since_b_run) is not int or
            state.non_b_training_turns_since_b_run < 0 or
            type(state.non_foundational_training_turns_since_foundational_run) is not int or
            state.non_foundational_training_turns_since_foundational_run < 0):
        raise ValueError("INVALID_SCHOOL_COUNTER")
    frontiers = state.introduction_frontiers
    grade_lookup = {grade.id: grade for grade in program.grades}
    if (len({grade for grade, _ in frontiers}) != len(frontiers) or
            any(grade not in state.active_grades or type(stage) is not int or stage < 0
                for grade, stage in frontiers) or
            any(stage >= max(1, len(grade_lookup[grade].teaching_stages))
                for grade, stage in frontiers)):
        raise ValueError("INVALID_INTRODUCTION_FRONTIER_HISTORY")
    if (len(set(state.main_sweep_visited)) != len(state.main_sweep_visited) or
            not set(state.main_sweep_visited) <= set(state.active_grades)):
        raise ValueError("INVALID_MAIN_SWEEP_HISTORY")
    all_active_caps = set(_caps(program, state.active_grades))
    if (len(set(state.carried_mastery_debt)) != len(state.carried_mastery_debt) or
            not set(state.carried_mastery_debt) <= all_active_caps):
        raise ValueError("INVALID_CARRIED_MASTERY_DEBT")
    if state.carried_mastery_debt and state.stage in (
            "AWAITING_NEXT_GRADE", "WHOLE_SCHOOL_MASTERED"):
        raise ValueError("CARRIED_MASTERY_DEBT_AT_COMPLETION_BOUNDARY")
    current = next(g for g in program.grades if g.id == state.grade)
    if state.introduction_stage >= max(1, len(current.teaching_stages)):
        raise ValueError("INVALID_INTRODUCTION_STAGE")
    _verify_promotion_sweep_state(program, state)
    program = _program(program)
    if state.revalidation_target_grade is not None:
        if (state.revalidation_target_grade not in state.active_grades[1:] or
                state.grade_index > state.active_grades.index(state.revalidation_target_grade) or
                state.stage not in ("MAIN", "ASSESS_MAIN", "RECOVERY_1",
                                    "ASSESS_RECOVERY_1", "RECOVERY_2", "ASSESS_RECOVERY_2",
                                    "PROMOTION_SWEEP", "ASSESS_PROMOTION_SWEEP",
                                    "DEFERRED_STAGNATION") or
                not set(state.active_grades[:state.active_grades.index(
                    state.revalidation_target_grade) + 1]) <= set(state.champions)):
            raise ValueError("INVALID_GRADE_REVALIDATION_STATE")
    if state.stage == "AWAITING_NEXT_GRADE" and (
            program.program_complete or state.grade != program.grades[-1].id or
            state.queue or state.pending_failures or
            state.grade not in state.champions):
        raise ValueError("INVALID_PARTIAL_SCHOOL_COMPLETION")
    if state.stage == "AWAITING_NEXT_GRADE_WITH_DEBT" and (
            program.program_complete or state.grade != state.active_grades[-1] or
            state.queue or not state.carried_mastery_debt):
        raise ValueError(PromotionError.INVALID_DEBT_BEARING_GRADE_BOUNDARY.value)
    if state.stage == "WHOLE_SCHOOL_MASTERED" and not program.program_complete:
        raise ValueError("WHOLE_SCHOOL_CANNOT_COMPLETE_PARTIAL_COURSE")


def next_capability(state: SchoolState) -> str | None:
    return (state.queue[0]
            if state.stage in ("MAIN", "RECOVERY_1", "RECOVERY_2",
                               "PROMOTION_SWEEP") and state.queue
            else None)


def visit(program, state: SchoolState, capability: str,
          student_after_visit: Checkpoint) -> SchoolState:
    """Record a completed human-run visit. Caller supplies the admitted full student.

    A rejected candidate leaves the complete student checkpoint unchanged.
    """
    program = _program(program)
    verify_state(program, state)
    if next_capability(state) != capability:
        raise ValueError("VISIT_NOT_NEXT_SCHEDULED_CAPABILITY")
    rest = state.queue[1:]
    frontier_priority_visits = state.frontier_priority_visits
    nongating_b_visits = state.nongating_b_visits
    non_b_training_turns_since_b_run = state.non_b_training_turns_since_b_run
    foundational_turns = state.non_foundational_training_turns_since_foundational_run
    foundational_grades = set(state.active_grades[:-2])
    roles = _nongating_debt_priority_roles(program, state)
    if roles is not None:
        debt_grade, frontier_grade = roles
        if capability in set(_caps(program, (frontier_grade,))):
            frontier_priority_visits += 1
        elif capability in set(_caps(program, (debt_grade,))):
            nongating_b_visits += 1
        if not rest:
            if state.grade == debt_grade:
                non_b_training_turns_since_b_run = 0
            else:
                non_b_training_turns_since_b_run += 1
            if state.grade in foundational_grades:
                foundational_turns = 0
            else:
                foundational_turns += 1
    elif not rest and state.grade in foundational_grades:
        foundational_turns = 0
    if state.stage == "PROMOTION_SWEEP":
        after = "ASSESS_PROMOTION_SWEEP"
    else:
        after = (state.stage if rest else
                 "ASSESS_" + ("MAIN" if state.stage == "MAIN" else state.stage))
    return replace(state, queue=rest, stage=after, visits=state.visits+1,
                   current_student=student_after_visit,
                   frontier_priority_visits=frontier_priority_visits,
                   nongating_b_visits=nongating_b_visits,
                   non_b_training_turns_since_b_run=(
                       non_b_training_turns_since_b_run),
                   non_foundational_training_turns_since_foundational_run=(
                       foundational_turns))


def require_assessment_after_flash(program, state: SchoolState) -> SchoolState:
    """End flash mode owing a real assessment before normal scheduling resumes."""
    program = _program(program)
    verify_state(program, state)
    if state.stage in ("ASSESS_MAIN", "ASSESS_RECOVERY_1",
                       "ASSESS_RECOVERY_2", "ASSESS_PROMOTION_SWEEP"):
        return state
    if state.stage not in ("MAIN", "RECOVERY_1", "RECOVERY_2",
                           "PROMOTION_SWEEP"):
        raise ValueError("FLASH_MODE_CANNOT_REQUIRE_ASSESSMENT_FROM_STAGE")
    if state.stage == "PROMOTION_SWEEP":
        return replace(state, stage="ASSESS_PROMOTION_SWEEP")
    return replace(state, stage="ASSESS_" + state.stage, queue=())


def weakest_three(scores: dict[str, Score], pool: tuple[str, ...]) -> tuple[str, ...]:
    """Select up to three failures from the complete cumulative introduced pool."""
    if len(set(pool)) != len(pool) or not set(pool) <= set(scores):
        raise ValueError("WEAKEST_THREE_INCOMPLETE_POOL")
    ranking = sorted((c for c in pool if not scores[c].perfect),
                     key=lambda c: (scores[c].accuracy, c))
    return tuple(ranking[:3])


def _perfect_in_grade(program, grade: str, scores: dict[str, Score]) -> bool:
    return all(c in scores and scores[c].perfect for c in _caps(program, (grade,)))


def _next_imperfect_grade_index(program, state: SchoolState,
                                scores: dict[str, Score], *,
                                allowed_capabilities: tuple[str, ...] | None = None,
                                excluded_grades: tuple[str, ...] = ()) -> int | None:
    """Find the next imperfect eligible grade in canonical wrapped order.

    Start immediately after the current grade, wrap once through canonical
    admitted order, skip grades already perfect on the latest cumulative
    assessment, and optionally skip grades already visited in the current
    ordinary MAIN sweep.
    """
    allowed = set(scores) if allowed_capabilities is None else set(allowed_capabilities)
    if not allowed <= set(scores):
        raise ValueError("SPIRAL_ALLOWED_CAPABILITY_OUTSIDE_ASSESSMENT")
    excluded = set(excluded_grades)
    if not excluded <= set(state.active_grades):
        raise ValueError("SPIRAL_EXCLUDED_GRADE_OUTSIDE_ACTIVE_PROGRAM")
    count = len(state.active_grades)
    for offset in range(1, count + 1):
        index = (state.grade_index + offset) % count
        if state.active_grades[index] in excluded:
            continue
        grade_caps = _caps(program, (state.active_grades[index],))
        eligible = tuple(cap for cap in grade_caps if cap in allowed)
        if not eligible:
            continue
        # An ordinary pass is due when any currently eligible capability in the
        # grade is imperfect. Missing/withheld capabilities are handled by the
        # caller's explicit containment authority, never synthesized as perfect.
        if any(not scores[cap].perfect for cap in eligible):
            return index
    return None


def _resume_ordinary_spiral(program, state: SchoolState,
                            snapshot: Assessment, *,
                            allowed_capabilities: tuple[str, ...] | None = None,
                            reset_sweep: bool = True) -> SchoolState | None:
    roles = _nongating_debt_priority_roles(program, state)
    if roles is not None:
        _, frontier_grade = roles
        foundational = _enter_due_foundational_rehearsal(
            program, state, snapshot,
            allowed_capabilities=allowed_capabilities,
            reset_sweep=reset_sweep)
        if foundational is not None:
            return foundational
        due_b = _enter_due_b_debt_run(
            program, state, snapshot,
            allowed_capabilities=allowed_capabilities,
            reset_sweep=reset_sweep)
        if due_b is not None:
            return due_b
        allowed = (set(snapshot.scores) if allowed_capabilities is None
                   else set(allowed_capabilities))
        frontier_caps = tuple(
            cap for cap in _caps(program, (frontier_grade,)) if cap in allowed)
        if _imperfect_ranked(snapshot.scores, frontier_caps):
            return _enter_grade(
                program, state, state.active_grades.index(frontier_grade),
                stage="MAIN", first_recovery=(),
                main_sweep_visited=() if reset_sweep else state.main_sweep_visited,
                latest_rubric_digest=snapshot.rubric_digest)
        return None
    excluded: tuple[str, ...] = ()
    while len(excluded) < len(state.active_grades):
        index = _next_imperfect_grade_index(
            program, state, snapshot.scores,
            allowed_capabilities=allowed_capabilities,
            excluded_grades=excluded)
        if index is None:
            return None
        entered = _enter_grade(
            program, state, index, stage="MAIN", first_recovery=(),
            main_sweep_visited=() if reset_sweep else state.main_sweep_visited,
            latest_rubric_digest=snapshot.rubric_digest)
        if allowed_capabilities is None:
            return entered
        allowed = set(allowed_capabilities)
        queue = tuple(cap for cap in entered.queue if cap in allowed)
        if queue:
            return replace(entered, queue=queue)
        excluded = (*excluded, entered.grade)
    return None


def _continue_main_sweep(program, state: SchoolState,
                         snapshot: Assessment, *,
                         allowed_capabilities: tuple[str, ...] | None = None) -> SchoolState | None:
    """Continue ordinary grade passes before scheduling global recovery.

    A grade enters `main_sweep_visited` only after its complete currently
    introduced MAIN queue has been assessed. Recovery therefore happens at
    most twice *between* full multi-grade sweeps, not twice after every grade.
    """
    program = _program(program)
    visited = state.main_sweep_visited
    if state.grade not in visited:
        visited = visited + (state.grade,)
    roles = _nongating_debt_priority_roles(program, state)
    if roles is not None:
        _, frontier_grade = roles
        foundational = _enter_due_foundational_rehearsal(
            program, state, snapshot,
            allowed_capabilities=allowed_capabilities,
            reset_sweep=False)
        if foundational is not None:
            return foundational
        due_b = _enter_due_b_debt_run(
            program, state, snapshot,
            allowed_capabilities=allowed_capabilities,
            reset_sweep=False)
        if due_b is not None:
            return due_b
        if state.grade == frontier_grade:
            return None
        allowed = (set(snapshot.scores) if allowed_capabilities is None
                   else set(allowed_capabilities))
        frontier_caps = tuple(
            cap for cap in _caps(program, (frontier_grade,)) if cap in allowed)
        if _imperfect_ranked(snapshot.scores, frontier_caps):
            return _enter_grade(
                program, state, state.active_grades.index(frontier_grade),
                stage="MAIN", first_recovery=(),
                main_sweep_visited=visited,
                latest_rubric_digest=snapshot.rubric_digest)
        return None
    excluded = visited
    while len(excluded) < len(state.active_grades):
        index = _next_imperfect_grade_index(
            program, state, snapshot.scores,
            allowed_capabilities=allowed_capabilities,
            excluded_grades=excluded)
        if index is None:
            return None
        entered = _enter_grade(
            program, state, index, stage="MAIN", first_recovery=(),
            main_sweep_visited=visited,
            latest_rubric_digest=snapshot.rubric_digest)
        if allowed_capabilities is None:
            return entered
        allowed = set(allowed_capabilities)
        queue = tuple(cap for cap in entered.queue if cap in allowed)
        if queue:
            return replace(entered, queue=queue)
        excluded = (*excluded, entered.grade)
    return None


def _finish_grade_series(program, state: SchoolState, assessment: Assessment,
                         pointers: dict[str, Checkpoint]) -> SchoolState:
    """Advance to the next grade or stop at a verified program boundary."""
    program = _program(program)
    next_index = state.grade_index + 1
    if next_index < len(state.active_grades):
        next_grade = state.active_grades[next_index]
        return _enter_grade(program, state, next_index,
                       stage="MAIN", first_recovery=(), champions=pointers,
                       main_sweep_visited=(),
                       revalidation_target_grade=None,
                       # The newly admitted grade owns the next cumulative seal.
                       latest_rubric_digest=None)
    if not program.program_complete:
        # Passing the last *published* grade cannot silently certify the
        # still-unpublished rest of New Ithkuil. Retain the intact champion
        # and wait for an explicitly versioned next-grade admission.
        return replace(state, queue=(), first_recovery=(), champions=pointers,
                       stage="AWAITING_NEXT_GRADE", pending_failures=(),
                       main_sweep_visited=(),
                       revalidation_target_grade=None,
                       latest_rubric_digest=assessment.rubric_digest)
    # Whole-school result is *one* model's all-grade result. A collection of
    # per-grade champions does not substitute for a perfect all-grade student.
    all_caps = _caps(program, tuple(g.id for g in program.grades))
    if set(assessment.scores) != set(all_caps):
        raise ValueError("FINAL_WHOLE_SCHOOL_SNAPSHOT_INCOMPLETE")
    failed = tuple(g.id for g in program.grades
                   if not _perfect_in_grade(program, g.id, assessment.scores))
    return replace(state, queue=(), first_recovery=(), champions=pointers,
                   stage="AWAITING_TEACHER_SOUP" if failed else "WHOLE_SCHOOL_MASTERED",
                   main_sweep_visited=(),
                   revalidation_target_grade=None,
                   latest_rubric_digest=assessment.rubric_digest,
                   pending_failures=failed)


def _promote(program, state: SchoolState, assessment: Assessment) -> SchoolState:
    program = _program(program)
    candidate = state.current_student
    previous = tuple(g.id for g in program.grades if g.id in state.champions)
    full_at_candidate = tuple(g for g in previous if _perfect_in_grade(program, g, assessment.scores))
    pointers = repoint_earlier(state.champions, candidate,
                               previously_passed=previous,
                               fully_mastered_at_this_candidate=full_at_candidate)
    pointers[state.grade] = candidate

    if state.carried_mastery_debt:
        all_caps = _caps(program, state.active_grades)
        if not set(all_caps) <= set(assessment.scores):
            # A staged grade deliberately withholds unintroduced capabilities
            # from routine assessment. A perfect earlier grade may still be
            # recorded, but partial evidence cannot close the debt epoch.
            debt = tuple(cap for cap in all_caps if (
                cap in state.carried_mastery_debt or
                (cap in assessment.scores and not assessment.scores[cap].perfect)))
            next_index = _next_imperfect_grade_index(
                program, state, assessment.scores)
            if next_index is None:
                # The remaining work may be the next unintroduced stage, not
                # an imperfect score in the currently measurable subset.
                for offset in range(1, len(state.active_grades) + 1):
                    index = (state.grade_index + offset) % len(state.active_grades)
                    grade = state.active_grades[index]
                    if not set(_caps(program, (grade,))) <= set(assessment.scores):
                        next_index = index
                        break
            if next_index is None:
                raise ValueError("DEBT_PROMOTION_REQUIRES_COMPLETE_ACTIVE_ASSESSMENT")
            return _enter_grade(
                program, replace(state, carried_mastery_debt=debt),
                next_index, stage="MAIN", first_recovery=(),
                champions=pointers, main_sweep_visited=(),
                revalidation_target_grade=None,
                latest_rubric_digest=assessment.rubric_digest)
        debt = tuple(capability for capability in all_caps
                     if not assessment.scores[capability].perfect)
        if not debt:
            # One intact checkpoint has finally cleared every admitted grade.
            # Repoint every grade to that same complete student, then use the
            # ordinary partial/full program boundary machinery.
            complete_pointers = {
                grade: candidate for grade in state.active_grades
            }
            last = len(state.active_grades) - 1
            boundary = _enter_grade(
                program, replace(state, carried_mastery_debt=()), last,
                stage="MAIN", first_recovery=(), champions=complete_pointers,
                main_sweep_visited=(), revalidation_target_grade=None,
                latest_rubric_digest=assessment.rubric_digest)
            return _finish_grade_series(
                program, boundary, assessment, complete_pointers)
        next_index = _next_imperfect_grade_index(
            program, state, assessment.scores)
        if next_index is None:
            raise ValueError("DEBT_SPIRAL_HAS_NO_IMPERFECT_GRADE")
        return _enter_grade(
            program, replace(state, carried_mastery_debt=debt), next_index,
            stage="MAIN", first_recovery=(), champions=pointers,
            main_sweep_visited=(), revalidation_target_grade=None,
            latest_rubric_digest=assessment.rubric_digest)

    target = state.revalidation_target_grade
    if target is not None:
        target_index = state.active_grades.index(target)
        if state.grade_index < target_index:
            # A/B/C are revisited in order, with their normal full-grade,
            # weakest-three and same-checkpoint assessment schedule.
            next_index = state.grade_index + 1
            return _enter_grade(program, state, next_index,
                           stage="MAIN", first_recovery=(), champions=pointers,
                           main_sweep_visited=())
        failed = tuple(g for g in state.active_grades[:target_index + 1]
                       if not _perfect_in_grade(program, g, assessment.scores))
        if failed:
            if program.program_complete and target == program.grades[-1].id:
                # Preserve the original final-program teacher-soup recovery:
                # only failed grades are revisited in that next school cycle.
                return replace(state, queue=(), first_recovery=(), champions=pointers,
                               stage="AWAITING_TEACHER_SOUP", pending_failures=failed,
                               main_sweep_visited=(),
                               revalidation_target_grade=None,
                               latest_rubric_digest=assessment.rubric_digest)
            # At a partial-program boundary, do not start C if the final B
            # checkpoint lost A. Repeat the ordered prefix until it sticks.
            return _enter_grade(program, state, 0, stage="MAIN",
                           first_recovery=(), champions=pointers,
                           main_sweep_visited=())
        return _finish_grade_series(program, state, assessment, pointers)

    if state.grade_index > 0 and state.grade not in state.champions:
        # Newly mastered B triggers A->B; C triggers A->B->C, etc.
        # Even a perfect initial cumulative B examination is followed by a
        # fresh ordered revalidation pass before the next grade is entered.
        return _enter_grade(program, state, 0, stage="MAIN",
                       first_recovery=(), champions=pointers,
                       main_sweep_visited=(),
                       revalidation_target_grade=state.grade,
                       latest_rubric_digest=assessment.rubric_digest)
    return _finish_grade_series(program, state, assessment, pointers)


def _verify_assessment_boundary(program, state: SchoolState,
                                snapshot: Assessment,
                                pool: tuple[str, ...], *,
                                rubric_pool: tuple[str, ...] | None = None) -> None:
    program = _program(program)
    verify_state(program, state)
    if state.stage not in ("ASSESS_MAIN", "ASSESS_RECOVERY_1",
                           "ASSESS_RECOVERY_2", "ASSESS_PROMOTION_SWEEP"):
        raise ValueError("ASSESSMENT_NOT_SCHEDULED_AT_DURABLE_BOUNDARY")
    snapshot.verify(
        state.current_student, program, pool,
        rubric_capabilities=rubric_pool,
    )
    if (not program.assessment_projections and
            state.latest_rubric_digest is not None and
            state.latest_rubric_digest != snapshot.rubric_digest):
        raise ValueError("ASSESSMENT_RUBRIC_CHANGED_MID_COURSE")










def _refresh_mastery_debt(program, state: SchoolState,
                          snapshot: Assessment) -> SchoolState:
    if not state.carried_mastery_debt:
        return state
    all_caps = _caps(program, state.active_grades)
    if not set(all_caps) <= set(snapshot.scores):
        return state
    debt = tuple(capability for capability in all_caps
                 if not snapshot.scores[capability].perfect)
    # Keep the nonempty marker until _promote observes one complete
    # all-perfect checkpoint and closes the debt-admission epoch.
    return replace(state, carried_mastery_debt=debt) if debt else state


def _assess_ordinary(program, state: SchoolState,
                     snapshot: Assessment) -> SchoolState:
    pool = _score_pool(program, state)
    grade = next(g for g in program.grades if g.id == state.grade)
    if grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1:
        own = set(_main_queue(program, state))
        if all(snapshot.scores[c].perfect for c in own):
            next_stage = state.introduction_stage + 1
            return _at_introduction_stage(
                state, next_stage, stage="MAIN",
                queue=grade.teaching_stages[next_stage], first_recovery=(),
                latest_rubric_digest=snapshot.rubric_digest)
    if _perfect_in_grade(program, state.grade, snapshot.scores):
        return replace(_promote(program, state, snapshot),
                       grade_exam_epoch=state.grade_exam_epoch + 1)
    if state.stage == "ASSESS_MAIN":
        continued = _continue_main_sweep(program, state, snapshot)
        if continued is not None:
            return continued
        trio = _frontier_recovery_queue(
            program, state, snapshot.scores, pool)
        return replace(state, stage="RECOVERY_1", queue=trio,
                       first_recovery=trio,
                       main_sweep_visited=(
                           state.main_sweep_visited + (state.grade,)
                           if state.grade not in state.main_sweep_visited
                           else state.main_sweep_visited),
                       latest_rubric_digest=snapshot.rubric_digest)
    if state.stage == "ASSESS_RECOVERY_1":
        due_b = _enter_due_b_debt_run(program, state, snapshot)
        if due_b is not None:
            return due_b
        trio = _frontier_recovery_queue(
            program, state, snapshot.scores, pool)
        return replace(state, stage="RECOVERY_2", queue=trio,
                       latest_rubric_digest=snapshot.rubric_digest)
    resumed = _resume_ordinary_spiral(
        program, state, snapshot, reset_sweep=True)
    if resumed is None:
        raise ValueError("SPIRAL_RECOVERY_ENDED_WITHOUT_IMPERFECT_GRADE")
    return resumed


def _advance_after_promotion_sweep(program, state: SchoolState,
                                   snapshot: Assessment) -> SchoolState:
    debt = _promotion_debt(program, state, snapshot)
    return_stage = state.promotion_sweep_return_stage
    cleared = _promotion_sweep_fields_cleared(
        state, carried_mastery_debt=debt,
        latest_rubric_digest=snapshot.rubric_digest)
    grade = next(g for g in program.grades if g.id == state.grade)
    if grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1:
        next_stage = state.introduction_stage + 1
        advanced = _at_introduction_stage(
            cleared, next_stage, stage="MAIN",
            queue=grade.teaching_stages[next_stage], first_recovery=())
        due_b = _enter_due_b_debt_run(program, advanced, snapshot)
        return due_b if due_b is not None else advanced
    if _perfect_in_grade(program, state.grade, snapshot.scores):
        return replace(_promote(program, cleared, snapshot),
                       grade_exam_epoch=state.grade_exam_epoch + 1)
    boundary_debt = _boundary_mastery_debt(
        program, state, snapshot, debt)
    cleared = replace(cleared, carried_mastery_debt=boundary_debt)
    next_index = state.grade_index + 1
    if next_index < len(state.active_grades):
        return _enter_grade(
            program, cleared, next_index, stage="MAIN", first_recovery=(),
            main_sweep_visited=(), latest_rubric_digest=None)
    if not program.program_complete:
        return replace(
            cleared, stage="AWAITING_NEXT_GRADE_WITH_DEBT", queue=(),
            first_recovery=(), main_sweep_visited=())
    ordinary = replace(cleared, stage=return_stage, queue=())
    return _assess_ordinary(program, ordinary, snapshot)


def _assess_promotion_sweep(program, state: SchoolState,
                            snapshot: Assessment) -> SchoolState:
    scope = state.promotion_sweep_scope
    completed = len(scope) - len(state.queue)
    if completed < 1:
        raise ValueError(PromotionError.PROMOTION_SWEEP_ASSESSMENT_WITHOUT_VISIT.value)
    visited = scope[completed - 1]
    running = {
        capability: Score(correct, total)
        for capability, correct, total in state.promotion_sweep_scores
    }
    running[visited] = snapshot.scores[visited]
    effective_scores = dict(snapshot.scores)
    effective_scores.update(running)
    effective_snapshot = replace(snapshot, scores=effective_scores)
    running_state = replace(
        state,
        promotion_sweep_scores=tuple(
            (capability, running[capability].correct, running[capability].total)
            for capability in scope),
    )
    if _mean_accuracy(running, scope) < PROMOTION_MEAN_FLOOR:
        return_stage = state.promotion_sweep_return_stage
        ordinary = _promotion_sweep_fields_cleared(
            running_state, stage=return_stage, queue=(),
            latest_rubric_digest=effective_snapshot.rubric_digest)
        ordinary = _refresh_mastery_debt(program, ordinary, effective_snapshot)
        return _assess_ordinary(program, ordinary, effective_snapshot)
    if state.queue:
        return replace(
            running_state, stage="PROMOTION_SWEEP",
            latest_rubric_digest=effective_snapshot.rubric_digest)
    return _advance_after_promotion_sweep(
        program, running_state, effective_snapshot)


def assess(program, state: SchoolState, snapshot: Assessment) -> SchoolState:
    program = _program(program)
    pool = _score_pool(program, state)
    _verify_assessment_boundary(program, state, snapshot, pool)
    if state.stage == "ASSESS_PROMOTION_SWEEP":
        return _assess_promotion_sweep(program, state, snapshot)
    state = _refresh_mastery_debt(program, state, snapshot)
    if _promotion_sweep_due(program, state, snapshot):
        return _start_promotion_sweep(program, state, snapshot)
    return _assess_ordinary(program, state, snapshot)


def assess_flash(program, state: SchoolState, snapshot: Assessment) -> SchoolState:
    """Use fresh routine evidence for scheduling without minting qualification authority.

    Flash mode may decide what should be taught next, including crossing grade
    boundaries, but it must not promote a grade, move champion pointers, or
    increment the authoritative grade-exam epoch. If every currently eligible
    grade is perfect, leave the assessment debt in place so a later full exam
    can establish qualification on the authoritative path.
    """
    program = _program(program)
    pool = _score_pool(program, state)
    _verify_assessment_boundary(program, state, snapshot, pool)
    if state.stage == "ASSESS_PROMOTION_SWEEP":
        # Stability promotion is qualification authority. Flash may collect the
        # fresh evidence but cannot consume it to advance the sweep.
        return replace(state, latest_rubric_digest=snapshot.rubric_digest)
    grade = next(g for g in program.grades if g.id == state.grade)
    if grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1:
        own = set(_main_queue(program, state))
        if all(snapshot.scores[c].perfect for c in own):
            next_stage = state.introduction_stage + 1
            return _at_introduction_stage(
                state, next_stage, stage="MAIN",
                queue=grade.teaching_stages[next_stage], first_recovery=(),
                latest_rubric_digest=snapshot.rubric_digest)

    if _perfect_in_grade(program, state.grade, snapshot.scores):
        if state.stage == "ASSESS_MAIN":
            continued = _continue_main_sweep(program, state, snapshot)
            if continued is not None:
                return continued
            # If another grade visited earlier in this sweep is still imperfect,
            # the ordinary sweep is complete and the two global recovery rounds
            # are due before regular progression resumes.
            trio = _frontier_recovery_queue(
                program, state, snapshot.scores, pool)
            if trio:
                visited = state.main_sweep_visited
                if state.grade not in visited:
                    visited = visited + (state.grade,)
                return replace(state, stage="RECOVERY_1", queue=trio,
                               first_recovery=trio, main_sweep_visited=visited,
                               latest_rubric_digest=snapshot.rubric_digest)
        resumed = _resume_ordinary_spiral(program, state, snapshot, reset_sweep=True)
        if resumed is not None and resumed.grade != state.grade:
            return resumed
        # No remaining imperfect grade exists. Hold the exact assessment debt
        # for a non-flash qualification exam instead of manufacturing a pass.
        return replace(state, latest_rubric_digest=snapshot.rubric_digest)

    if state.stage == "ASSESS_MAIN":
        continued = _continue_main_sweep(program, state, snapshot)
        if continued is not None:
            return continued
        trio = _frontier_recovery_queue(
            program, state, snapshot.scores, pool)
        return replace(state, stage="RECOVERY_1", queue=trio,
                       first_recovery=trio,
                       main_sweep_visited=(state.main_sweep_visited + (state.grade,)
                                           if state.grade not in state.main_sweep_visited
                                           else state.main_sweep_visited),
                       latest_rubric_digest=snapshot.rubric_digest)
    if state.stage == "ASSESS_RECOVERY_1":
        trio = _frontier_recovery_queue(
            program, state, snapshot.scores, pool)
        return replace(state, stage="RECOVERY_2", queue=trio,
                       latest_rubric_digest=snapshot.rubric_digest)
    resumed = _resume_ordinary_spiral(program, state, snapshot, reset_sweep=True)
    if resumed is None:
        return replace(state, latest_rubric_digest=snapshot.rubric_digest)
    return resumed


def _advance_withheld_intro_stage(
        program, state: SchoolState, snapshot: Assessment,
        active_pool: tuple[str, ...], blocked: tuple[str, ...]) -> SchoolState | None:
    grade = next(g for g in program.grades if g.id == state.grade)
    current_caps = set(_caps(program, (state.grade,)))
    blocked_current = current_caps & set(blocked)
    if (not grade.teaching_stages or
            state.introduction_stage >= len(grade.teaching_stages)-1 or
            blocked_current):
        return None
    own = tuple(c for c in _main_queue(program, state) if c in active_pool)
    if not own or not all(snapshot.scores[c].perfect for c in own):
        return None
    next_stage = state.introduction_stage + 1
    entered = _at_introduction_stage(
        state, next_stage, stage="MAIN", first_recovery=(),
        latest_rubric_digest=snapshot.rubric_digest)
    queue = tuple(
        c for c in grade.teaching_stages[next_stage] if c not in set(blocked))
    return replace(entered, queue=queue) if queue else None


def assess_withheld(program, state: SchoolState, snapshot: Assessment,
                    withheld: tuple[str, ...], *,
                    rubric_capabilities: tuple[str, ...] | None = None) -> SchoolState:
    """Advance ordinary school work while retaining quarantined mastery debt.

    The snapshot contains only capabilities still eligible for this human
    command's ordinary evaluation.  Withheld capabilities are never assigned a
    synthetic/stale score and can never permit promotion.  When the remaining
    eligible work is exhausted the command stops at `DEFERRED_STAGNATION` for
    end-of-run review; a later command may explicitly re-enter that debt.
    """
    program = _program(program)
    if not withheld:
        return assess(program, state, snapshot)
    if state.stage == "ASSESS_PROMOTION_SWEEP":
        return_stage = state.promotion_sweep_return_stage
        ordinary = _promotion_sweep_fields_cleared(
            state, stage=return_stage, queue=(),
            latest_rubric_digest=snapshot.rubric_digest)
        return assess_withheld(
            program, ordinary, snapshot, withheld,
            rubric_capabilities=rubric_capabilities)
    pool = _score_pool(program, state)
    blocked = tuple(dict.fromkeys(withheld))
    if (len(blocked) != len(withheld) or not set(blocked) <= set(pool)):
        raise ValueError("STAGNATION_WITHHELD_CAPABILITY_OUTSIDE_ACTIVE_POOL")
    active_pool = tuple(cap for cap in pool if cap not in set(blocked))
    if not active_pool:
        return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                       first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)
    _verify_assessment_boundary(
        program, state, snapshot, active_pool,
        rubric_pool=(rubric_capabilities if rubric_capabilities is not None else
                     active_pool if program.assessment_projections else pool),
    )

    advanced = _advance_withheld_intro_stage(
        program, state, snapshot, active_pool, blocked)
    if advanced is not None:
        return advanced

    # Any withheld capability remains explicit graduation debt; never promote
    # a grade or cumulative prefix from a partial ordinary assessment.
    if state.stage == "ASSESS_MAIN":
        continued = _continue_main_sweep(
            program, state, snapshot, allowed_capabilities=active_pool)
        if continued is not None:
            return continued
        trio = _frontier_recovery_queue(
            program, state, snapshot.scores, active_pool)
        if trio:
            visited = state.main_sweep_visited
            if state.grade not in visited:
                visited = visited + (state.grade,)
            return replace(state, stage="RECOVERY_1", queue=trio,
                           first_recovery=trio,
                           main_sweep_visited=visited,
                           latest_rubric_digest=snapshot.rubric_digest)
        return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                       first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)
    if state.stage == "ASSESS_RECOVERY_1":
        due_b = _enter_due_b_debt_run(
            program, state, snapshot, allowed_capabilities=active_pool)
        if due_b is not None:
            return due_b
        trio = _frontier_recovery_queue(
            program, state, snapshot.scores, active_pool)
        if trio:
            return replace(state, stage="RECOVERY_2", queue=trio,
                           latest_rubric_digest=snapshot.rubric_digest)
        return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                       first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)

    resumed = _resume_ordinary_spiral(
        program, state, snapshot, allowed_capabilities=active_pool,
        reset_sweep=True)
    if resumed is not None:
        return resumed
    return replace(state, stage="DEFERRED_STAGNATION", queue=(),
                   first_recovery=(), latest_rubric_digest=snapshot.rubric_digest)


def reactivate_stagnation_debt(program, state: SchoolState,
                               debt: tuple[str, ...]) -> SchoolState:
    """Start a later human command by explicitly re-entering deferred debt."""
    program = _program(program)
    verify_state(program, state)
    if state.stage != "DEFERRED_STAGNATION" or not debt or len(set(debt)) != len(debt):
        raise ValueError("STAGNATION_REENTRY_INVALID")
    pool = _score_pool(program, state)
    if not set(debt) <= set(pool):
        raise ValueError("STAGNATION_REENTRY_OUTSIDE_ACTIVE_POOL")
    return replace(state, stage="RECOVERY_1", queue=tuple(debt),
                   first_recovery=tuple(debt[:3]))


def continue_after_soup(program, state: SchoolState,
                        *, frozen_teacher_receipt: str) -> SchoolState:
    """Start a new *grade cycle*. The causal student and AdamW are untouched."""
    program = _program(program)
    verify_state(program, state)
    if state.stage != "AWAITING_TEACHER_SOUP" or not state.pending_failures:
        raise ValueError("TEACHER_SOUP_NOT_DUE")
    if (len(frozen_teacher_receipt) != 64 or
            any(c not in "0123456789abcdef" for c in frozen_teacher_receipt)):
        raise ValueError("TEACHER_SOUP_RECEIPT_MISSING")
    restarted = replace(state, active_grades=state.pending_failures,
                   grade_exam_epoch=state.grade_exam_epoch + 1,
                   first_recovery=(), stage="MAIN",
                   main_sweep_visited=(),
                   pending_failures=(), school_cycles=state.school_cycles+1,
                   revalidation_target_grade=None,
                   teacher_soup_digest=frozen_teacher_receipt)
    return _enter_grade(program, restarted, 0)


def teacher_vote_weights(program, state: SchoolState) -> dict[str, int]:
    program = _program(program)
    if state.revalidation_target_grade is not None:
        # Every already-graduated grade is an eligible teacher when revisited,
        # including a grade numerically later than the active replay grade.
        return soup_weights(state.champions)
    return vote_counts(state.champions,
                       grade_order=tuple(g.id for g in program.grades),
                       active_grade=state.grade)


def whole_school_soup_weights(state: SchoolState) -> dict[str, int]:
    if state.stage != "AWAITING_TEACHER_SOUP":
        raise ValueError("NOT_AT_WHOLE_SCHOOL_SOUP_BOUNDARY")
    return soup_weights(state.champions)


def save_new_state(path: Path, state: SchoolState) -> None:
    """Exclusive no-overwrite write, rather than silent continuation of old run."""
    payload = json.dumps(asdict(state), sort_keys=True, indent=2) + "\n"
    atomic_text(path, payload)


def read_state(path: Path, program) -> SchoolState:
    """Use only for an explicitly requested --resume operation."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw["active_grades"] = tuple(raw["active_grades"])
    raw["queue"] = tuple(raw["queue"])
    raw["first_recovery"] = tuple(raw["first_recovery"])
    raw["pending_failures"] = tuple(raw["pending_failures"])
    raw["main_sweep_visited"] = tuple(raw.get("main_sweep_visited", ()))
    raw["carried_mastery_debt"] = tuple(raw.get("carried_mastery_debt", ()))
    legacy_b_full_run_epoch = "non_b_training_turns_since_b_run" not in raw
    legacy_foundational_rehearsal_epoch = (
        "non_foundational_training_turns_since_foundational_run" not in raw)
    legacy_promotion_sweep_attempt_epoch = (
        "promotion_sweep_attempt_student_sha256" not in raw or
        "promotion_sweep_attempt_scope" not in raw)
    raw["promotion_sweep_scope"] = tuple(raw.get("promotion_sweep_scope", ()))
    raw["promotion_sweep_return_stage"] = raw.get(
        "promotion_sweep_return_stage")
    raw["promotion_sweep_scores"] = tuple(
        (capability, correct, total)
        for capability, correct, total in raw.get("promotion_sweep_scores", ()))
    raw["promotion_sweep_attempt_student_sha256"] = raw.get(
        "promotion_sweep_attempt_student_sha256")
    raw["promotion_sweep_attempt_scope"] = tuple(
        raw.get("promotion_sweep_attempt_scope", ()))
    raw["non_b_training_turns_since_b_run"] = raw.get(
        "non_b_training_turns_since_b_run", 0)
    raw["non_foundational_training_turns_since_foundational_run"] = raw.get(
        "non_foundational_training_turns_since_foundational_run", 0)
    raw["introduction_frontiers"] = tuple(
        (grade, stage) for grade, stage in raw.get("introduction_frontiers", ()))
    raw["current_student"] = Checkpoint(**raw["current_student"])
    raw["champions"] = {grade: Checkpoint(**cp)
                        for grade, cp in raw["champions"].items()}
    result = SchoolState(**raw)
    if legacy_b_full_run_epoch:
        result = migrate_b_full_run_epoch(program, result)
    if legacy_foundational_rehearsal_epoch:
        result = migrate_foundational_rehearsal_epoch(program, result)
    if legacy_promotion_sweep_attempt_epoch:
        result = migrate_promotion_sweep_attempt_epoch(program, result)
    verify_state(program, result)
    return result


def choose_best_whole_student(program,
                              candidates: tuple[tuple[Checkpoint, Assessment], ...],
                              assessed_grades: tuple[str, ...]) -> Checkpoint:
    """Select ONE complete model+optimizer by same-rubric whole-student score.

    Never blend per-capability maxima across checkpoints or prefer latest step
    merely because the optimizer has run longer. Candidates must use the exact
    same questions/rubric identity and cover the entire observed grade pool.
    """
    if not candidates or not assessed_grades:
        raise ValueError("WHOLE_STUDENT_CANDIDATE_POOL_EMPTY")
    program = _program(program)
    required = _caps(program, assessed_grades)
    rubrics = set()
    totals = set()
    for candidate,assessment in candidates:
        assessment.verify(candidate,program,required)
        rubrics.add(assessment.rubric_digest)
        totals.add(tuple((k,assessment.scores[k].total) for k in required))
    if len(rubrics) != 1 or len(totals) != 1:
        raise ValueError("WHOLE_STUDENT_CANDIDATES_NOT_COMPARABLE")
    def rank(row):
        candidate,assessment = row
        correct = sum(assessment.scores[c].correct for c in required)
        total = sum(assessment.scores[c].total for c in required)
        return (Fraction(correct,total),-candidate.optimizer_step,candidate.sha256)
    return max(candidates,key=rank)[0]
