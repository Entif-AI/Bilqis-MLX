"""Deterministic, neural-inert school-grade scheduler and promotion contract.

No optimizer, teacher/model or exam generator is invoked here. This state
machine accepts only explicit same-checkpoint scores from a separate evaluator.
It prevents an old mixed-step score board from certifying new grade mastery.
"""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL

from dataclasses import asdict, replace
from fractions import Fraction
from .debt_control import (
    _apply_mature_debt_frontier, _debt_cadence_mode, _debt_run_due,
    _debt_run_queue, _frontier_recovery_queue, _imperfect_ranked,
    _frontier_catchup_target_passes, _mature_debt_repair_grade,
    _next_imperfect_grade_index,
)
from .state import (
    SCHOOL_STATE_SCHEMA, STAGES, _program, ScheduleTopology,
    classify_schedule_topology, Score, DebtCadencePolicy, Assessment, SchoolState,
    _caps, _score_pool, _school_state_boundary_issue, verify_state,
    assessment_capabilities, next_capability, weakest_three,
)
from .promotion import (PROMOTION_SWEEP_FAILURE_FLOOR, PromotionError, _promotion_debt, _boundary_mastery_debt, _failed_promotion_blockers, _introduced_grade_capabilities, _mean_accuracy, _promotion_sweep_fields_cleared, _promotion_sweep_due, _start_promotion_sweep, migrate_promotion_sweep_attempt_epoch, restore_promotion_attempt_fields)
import hashlib
import json
from pathlib import Path

from bilqis_mlx.learning.champions import Checkpoint, repoint_earlier, vote_counts, soup_weights
from bilqis_mlx.factory.schedule import ScheduleProgram
from bilqis_mlx.runtime.disk import atomic_text


def _enter_due_debt_run(program, state: SchoolState,
                        snapshot: Assessment, *,
                        allowed_capabilities: tuple[str, ...] | None = None,
                        reset_sweep: bool = True) -> SchoolState | None:
    if not _debt_run_due(program, state):
        return None
    queue = _debt_run_queue(
        program, state, snapshot.scores,
        allowed_capabilities=allowed_capabilities)
    if not queue:
        return None
    bounded_grade_id = state.debt_cadence_policy.bounded_debt_grade_id
    entered = _enter_grade(
        program, state, state.active_grades.index(bounded_grade_id),
        stage="MAIN", first_recovery=(),
        main_sweep_visited=() if reset_sweep else state.main_sweep_visited,
        latest_rubric_digest=snapshot.rubric_digest)
    return replace(entered, queue=queue)


def _enter_mature_debt_repair(program, state: SchoolState, *,
                              allowed_capabilities: tuple[str, ...] | None = None,
                              reset_sweep: bool = True) -> SchoolState | None:
    grade = _mature_debt_repair_grade(program, state)
    if grade is None or (not reset_sweep and grade in state.main_sweep_visited):
        return None
    entered = _enter_grade(
        program, state, state.active_grades.index(grade),
        stage="MAIN", first_recovery=(),
        main_sweep_visited=() if reset_sweep else state.main_sweep_visited,
        latest_rubric_digest=state.latest_rubric_digest)
    if allowed_capabilities is None:
        return entered
    queue = tuple(capability for capability in entered.queue
                  if capability in set(allowed_capabilities))
    return replace(entered, queue=queue) if queue else None


def migrate_legacy_debt_cadence_policy(program, state: SchoolState) -> SchoolState:
    """Decode the historical policy only for a saved C-frontier course."""
    program = _program(program)
    if state.debt_cadence_policy is not None:
        return state
    policy = DebtCadencePolicy.from_legacy_adr094()
    if (not state.active_grades or
            not {policy.bounded_debt_grade_id,
             policy.progression_priority_grade_id} <= set(state.active_grades) or
            state.active_grades[-1] != policy.progression_priority_grade_id):
        return state
    return replace(state, debt_cadence_policy=policy)


def migrate_legacy_debt_cadence_queue(program, state: SchoolState) -> SchoolState:
    """Re-anchor an older debt-role queue to the explicitly named priority role."""
    program = _program(program)
    if (not _debt_cadence_mode(program, state) or
            state.stage not in ("MAIN", "RECOVERY_1", "RECOVERY_2")):
        return state
    bounded_caps = set(_caps(
        program, (state.debt_cadence_policy.bounded_debt_grade_id,)))
    if not state.queue or state.queue[0] not in bounded_caps:
        return state
    priority_grade_id = state.debt_cadence_policy.progression_priority_grade_id
    return _enter_grade(
        program, state, state.active_grades.index(priority_grade_id),
        stage="MAIN", first_recovery=(), main_sweep_visited=(),
        latest_rubric_digest=state.latest_rubric_digest)


def migrate_legacy_debt_cadence_epoch(program, state: SchoolState) -> SchoolState:
    """Adopt legacy turn accounting without rewriting visits or scores."""
    program = _program(program)
    if not _debt_cadence_mode(program, state):
        return replace(state, non_b_training_turns_since_b_run=0)
    migrated = replace(
        state,
        non_b_training_turns_since_b_run=(
            state.debt_cadence_policy.non_debt_turns_per_run))
    if migrated.stage not in ("MAIN", "RECOVERY_1", "RECOVERY_2"):
        return migrated
    policy = migrated.debt_cadence_policy
    bounded_caps = set(_caps(program, (policy.bounded_debt_grade_id,)))
    if (migrated.grade != policy.bounded_debt_grade_id and
            any(cap in bounded_caps for cap in migrated.queue)):
        priority_grade_id = policy.progression_priority_grade_id
        return _enter_grade(
            program, migrated, migrated.active_grades.index(priority_grade_id),
            stage="MAIN", first_recovery=(), main_sweep_visited=(),
            latest_rubric_digest=migrated.latest_rubric_digest)
    return migrated


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
    if (changes.get("main_sweep_visited") == () and
            "frontier_catchup_passes" not in changes):
        changes["frontier_catchup_passes"] = 0
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


def start_new(program, initial_student: Checkpoint, *,
              debt_cadence_policy: DebtCadencePolicy | None = None) -> SchoolState:
    program = _program(program)
    state = SchoolState(schema="bilqis.mlx.letter-grade/v1",
                       course_digest=program.digest(),
                       active_grades=tuple(g.id for g in program.grades),
                       grade_index=0, stage="MAIN",
                       queue=_caps(program, (program.grades[0].id,)),
                       first_recovery=(), current_student=initial_student,
                       champions={}, debt_cadence_policy=debt_cadence_policy)
    return replace(state, queue=_main_queue(program, state))




def visit(program, state: SchoolState, capability: str,
          student_after_visit: Checkpoint, *, retention_frontier: dict | None = None
          ) -> SchoolState:
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
    if _debt_cadence_mode(program, state):
        policy = state.debt_cadence_policy
        if capability in set(_caps(program, (policy.progression_priority_grade_id,))):
            frontier_priority_visits += 1
        elif capability in set(_caps(program, (policy.bounded_debt_grade_id,))):
            nongating_b_visits += 1
        if not rest:
            if state.grade == policy.bounded_debt_grade_id:
                non_b_training_turns_since_b_run = 0
            else:
                non_b_training_turns_since_b_run += 1
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
                   mature_grade_debt=_apply_mature_debt_frontier(
                       program, state, retention_frontier))


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




def _perfect_in_grade(program, grade: str, scores: dict[str, Score]) -> bool:
    return all(c in scores and scores[c].perfect for c in _caps(program, (grade,)))


def _resume_ordinary_spiral(program, state: SchoolState,
                            snapshot: Assessment, *,
                            allowed_capabilities: tuple[str, ...] | None = None,
                            reset_sweep: bool = True) -> SchoolState | None:
    mature_repair = _enter_mature_debt_repair(
        program, state, allowed_capabilities=allowed_capabilities,
        reset_sweep=reset_sweep)
    if mature_repair is not None:
        return mature_repair
    if _debt_cadence_mode(program, state):
        due = _enter_due_debt_run(
            program, state, snapshot,
            allowed_capabilities=allowed_capabilities,
            reset_sweep=reset_sweep)
        if due is not None:
            return due
        allowed = (set(snapshot.scores) if allowed_capabilities is None
                   else set(allowed_capabilities))
        priority_grade_id = state.debt_cadence_policy.progression_priority_grade_id
        priority_caps = tuple(cap for cap in _caps(program, (priority_grade_id,))
                              if cap in allowed)
        if _imperfect_ranked(snapshot.scores, priority_caps):
            return _enter_grade(
                program, state, state.active_grades.index(priority_grade_id),
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
    frontier = state.active_grades[-1]
    frontier_passes = state.frontier_catchup_passes
    if state.grade == frontier and state.main_sweep_visited:
        frontier_passes += 1
        target_passes = _frontier_catchup_target_passes(
            program, state, snapshot.scores,
            allowed_capabilities=allowed_capabilities)
        if frontier_passes < target_passes:
            return _enter_grade(
                program, state, state.grade_index, stage="MAIN",
                first_recovery=(), main_sweep_visited=state.main_sweep_visited,
                frontier_catchup_passes=frontier_passes,
                latest_rubric_digest=snapshot.rubric_digest)
        state = replace(state, frontier_catchup_passes=frontier_passes)
    visited = state.main_sweep_visited
    if state.grade not in visited:
        visited = visited + (state.grade,)
    mature_repair = _enter_mature_debt_repair(
        program, replace(state, main_sweep_visited=visited),
        allowed_capabilities=allowed_capabilities,
        reset_sweep=False)
    if mature_repair is not None:
        return mature_repair
    if _debt_cadence_mode(program, state):
        due = _enter_due_debt_run(
            program, state, snapshot,
            allowed_capabilities=allowed_capabilities,
            reset_sweep=False)
        if due is not None:
            return due
        priority_grade_id = state.debt_cadence_policy.progression_priority_grade_id
        if state.grade == priority_grade_id:
            return None
        allowed = (set(snapshot.scores) if allowed_capabilities is None
                   else set(allowed_capabilities))
        priority_caps = tuple(cap for cap in _caps(program, (priority_grade_id,))
                              if cap in allowed)
        if _imperfect_ranked(snapshot.scores, priority_caps):
            return _enter_grade(
                program, state, state.active_grades.index(priority_grade_id),
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
        due = _enter_due_debt_run(program, state, snapshot)
        if due is not None:
            return due
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
    grade = next(g for g in program.grades if g.id == state.grade)
    if grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1:
        cleared = _promotion_sweep_fields_cleared(
            state, carried_mastery_debt=debt,
            promotion_sweep_retry_scores=(),
            latest_rubric_digest=snapshot.rubric_digest)
        next_stage = state.introduction_stage + 1
        advanced = _at_introduction_stage(
            cleared, next_stage, stage="MAIN",
            queue=grade.teaching_stages[next_stage], first_recovery=())
        due = _enter_due_debt_run(program, advanced, snapshot)
        return due if due is not None else advanced
    if _perfect_in_grade(program, state.grade, snapshot.scores):
        cleared = _promotion_sweep_fields_cleared(
            state, carried_mastery_debt=debt,
            promotion_sweep_retry_scores=(),
            latest_rubric_digest=snapshot.rubric_digest)
        return replace(_promote(program, cleared, snapshot),
                       grade_exam_epoch=state.grade_exam_epoch + 1)
    boundary_debt = _boundary_mastery_debt(
        program, state, snapshot, debt)
    next_index = state.grade_index + 1
    if next_index < len(state.active_grades):
        cleared = _promotion_sweep_fields_cleared(
            state, carried_mastery_debt=boundary_debt,
            promotion_sweep_retry_scores=_failed_promotion_blockers(state, snapshot),
            latest_rubric_digest=snapshot.rubric_digest)
        return _enter_grade(
            program, cleared, next_index, stage="MAIN", first_recovery=(),
            main_sweep_visited=(), latest_rubric_digest=None)
    if not program.program_complete:
        cleared = _promotion_sweep_fields_cleared(
            state, carried_mastery_debt=boundary_debt,
            promotion_sweep_retry_scores=(),
            latest_rubric_digest=snapshot.rubric_digest)
        return replace(
            cleared, stage="AWAITING_NEXT_GRADE_WITH_DEBT", queue=(),
            first_recovery=(), main_sweep_visited=())
    cleared = _promotion_sweep_fields_cleared(
        state, carried_mastery_debt=boundary_debt,
        promotion_sweep_retry_scores=_failed_promotion_blockers(state, snapshot),
        latest_rubric_digest=snapshot.rubric_digest)
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
    if _mean_accuracy(running, scope) < PROMOTION_SWEEP_FAILURE_FLOOR:
        return_stage = state.promotion_sweep_return_stage
        ordinary = _promotion_sweep_fields_cleared(
            running_state, stage=return_stage, queue=(),
            promotion_sweep_retry_scores=_failed_promotion_blockers(
                running_state, effective_snapshot),
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

    entered = _advance_unblocked_introduction(
        program, state, snapshot, active_pool, blocked)
    if entered is not None:
        return entered
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
        due = _enter_due_debt_run(
            program, state, snapshot, allowed_capabilities=active_pool)
        if due is not None:
            return due
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


def adopt_appended_program(previous: ScheduleProgram,
                           successor: ScheduleProgram,
                           state: SchoolState) -> SchoolState:
    """Admit exactly one appended projected grade without knowing its identity."""
    if (not isinstance(previous, ScheduleProgram) or
            not isinstance(successor, ScheduleProgram)):
        raise TypeError(SCHOOL.SCHEDULE.PROGRAM_REQUIRED.legacy_codes[0])
    verify_state(previous, state)
    previous_ids = tuple(grade.id for grade in previous.grades)
    successor_ids = tuple(grade.id for grade in successor.grades)
    if (previous.program_complete or
            state.stage != "AWAITING_NEXT_GRADE" or
            len(successor_ids) != len(previous_ids) + 1 or
            successor_ids[:-1] != previous_ids or
            successor.grades[:-1] != previous.grades):
        raise ValueError("FACTORY_SCHEDULE_APPEND_INVALID")
    if state.grade not in state.champions:
        raise ValueError("FACTORY_SCHEDULE_APPEND_REQUIRES_GRADUATED_PREFIX")
    added = successor_ids[-1]
    if added in state.champions:
        raise ValueError("FACTORY_SCHEDULE_APPEND_FUTURE_CHAMPION_EXISTS")
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
        carried_mastery_debt=(),
    )
    return _enter_grade(successor, extended, len(previous.grades))


def append_next_grade_with_debt(
        previous, successor, state: SchoolState,
        mastery_debt: tuple[str, ...]) -> SchoolState:
    """Human-authorized append while preserving unresolved prior mastery debt.

    This is progression, not graduation.  It never fabricates a champion for
    an unresolved grade and it never clears debt merely because a later grade
    becomes available.  One later cumulative checkpoint must still perfect the
    complete active program before the ordinary next-grade boundary is reached.
    """
    previous, successor = _program(previous), _program(successor)
    verify_state(previous, state)
    if previous.program_complete:
        raise ValueError("DEBT_GRADE_APPEND_REQUIRES_PARTIAL_PROGRAM")
    if not mastery_debt or len(set(mastery_debt)) != len(mastery_debt):
        raise ValueError("DEBT_GRADE_APPEND_REQUIRES_EXPLICIT_MASTERY_DEBT")
    previous_caps = set(_caps(previous, tuple(g.id for g in previous.grades)))
    if not set(mastery_debt) <= previous_caps:
        raise ValueError("DEBT_GRADE_APPEND_DEBT_OUTSIDE_PREVIOUS_PROGRAM")
    if len(successor.grades) != len(previous.grades) + 1:
        raise ValueError("GRADE_APPEND_REQUIRES_EXACTLY_ONE_NEW_GRADE")
    if tuple(successor.grades[:len(previous.grades)]) != previous.grades:
        raise ValueError("GRADE_APPEND_WOULD_CHANGE_PREVIOUS_GRADE")
    if any(g.assessment_sha256 is None for g in previous.grades):
        raise ValueError("GRADE_APPEND_UNSEALED_PREVIOUS_GRADE")
    if state.revalidation_target_grade is not None:
        raise ValueError("DEBT_GRADE_APPEND_DURING_REVALIDATION_FORBIDDEN")
    grade_by_capability = {
        capability.id: grade.id
        for grade in previous.grades for capability in grade.capabilities
    }
    debt_grades = {grade_by_capability[capability] for capability in mastery_debt}
    mastered_required = set(state.active_grades) - debt_grades
    if not mastered_required <= set(state.champions):
        raise ValueError("DEBT_GRADE_APPEND_NONDEBT_GRADE_NOT_MASTERED")
    added = successor.grades[-1].id
    if added in state.champions:
        raise ValueError("GRADE_APPEND_FUTURE_CHAMPION_ALREADY_EXISTS")
    extended = replace(
        state, course_digest=successor.digest(),
        grade_exam_epoch=state.grade_exam_epoch + 1,
        active_grades=tuple(g.id for g in successor.grades),
        stage="MAIN", first_recovery=(), main_sweep_visited=(),
        revalidation_target_grade=None, latest_rubric_digest=None,
        pending_failures=(), teacher_soup_digest=None,
        carried_mastery_debt=tuple(mastery_debt))
    return _enter_grade(successor, extended, len(previous.grades))


def adopt_expanded_prior_grade(previous: ScheduleProgram,
                               successor: ScheduleProgram,
                               state: SchoolState) -> tuple[SchoolState, str]:
    """Add capability debt to an earlier admitted grade without leaving the active frontier."""
    if (not isinstance(previous, ScheduleProgram) or
            not isinstance(successor, ScheduleProgram)):
        raise TypeError(SCHOOL.SCHEDULE.PROGRAM_REQUIRED.legacy_codes[0])
    verify_state(previous, state)
    previous_ids = tuple(grade.id for grade in previous.grades)
    successor_ids = tuple(grade.id for grade in successor.grades)
    changed = tuple(
        index for index, (old, new) in enumerate(zip(previous.grades, successor.grades))
        if (old.capabilities != new.capabilities or
            old.teaching_stages != new.teaching_stages))
    if (previous_ids != successor_ids or len(changed) != 1 or
            changed[0] >= len(state.active_grades) - 1):
        ErrorBus.raise_legacy(SCHOOL.SCHEDULE.PRIOR_GRADE_EXPANSION_INVALID)
    index = changed[0]
    old_grade, new_grade = previous.grades[index], successor.grades[index]
    old_caps = tuple(cap.id for cap in old_grade.capabilities)
    new_caps = tuple(cap.id for cap in new_grade.capabilities)
    if (not set(old_caps) < set(new_caps) or
            tuple(cap for cap in new_caps if cap in set(old_caps)) != old_caps):
        ErrorBus.raise_legacy(SCHOOL.SCHEDULE.PRIOR_GRADE_EXPANSION_NOT_ADDITIVE)
    old_by_id = {cap.id: cap for cap in old_grade.capabilities}
    new_by_id = {cap.id: cap for cap in new_grade.capabilities}
    if any(new_by_id[cap] != old for cap, old in old_by_id.items()):
        ErrorBus.raise_legacy(SCHOOL.SCHEDULE.PRIOR_GRADE_EXPANSION_CHANGED_EXISTING_CAPABILITY)
    added = tuple(cap for cap in new_caps if cap not in old_by_id)
    debt = tuple((*state.carried_mastery_debt,
                  *(cap for cap in added if cap not in state.carried_mastery_debt)))
    champions = dict(state.champions)
    champions.pop(old_grade.id, None)
    rebound = replace(
        state, course_digest=successor.digest(), champions=champions,
        carried_mastery_debt=debt, grade_exam_epoch=state.grade_exam_epoch + 1,
        latest_rubric_digest=None, teacher_soup_digest=None,
        revalidation_target_grade=None,
        promotion_sweep_attempt_student_sha256=None,
        promotion_sweep_attempt_scope=(),
        promotion_sweep_retry_scores=())
    rebound = _promotion_sweep_fields_cleared(
        rebound, stage="MAIN", queue=(), first_recovery=(),
        main_sweep_visited=())
    rebound = _enter_grade(
        successor, rebound, len(state.active_grades) - 1,
        stage="MAIN", first_recovery=(), main_sweep_visited=(),
        latest_rubric_digest=None)
    verify_state(successor, rebound)
    return rebound, old_grade.id


def adopt_revised_program(previous: ScheduleProgram,
                          successor: ScheduleProgram,
                          state: SchoolState) -> tuple[SchoolState, str]:
    """Rebind one active projected grade after a profile roster revision."""
    if (not isinstance(previous, ScheduleProgram) or
            not isinstance(successor, ScheduleProgram)):
        raise TypeError(SCHOOL.SCHEDULE.PROGRAM_REQUIRED.legacy_codes[0])
    verify_state(previous, state)
    previous_ids = tuple(grade.id for grade in previous.grades)
    successor_ids = tuple(grade.id for grade in successor.grades)
    changed = tuple(
        index for index, (old, new) in
        enumerate(zip(previous.grades, successor.grades))
        if old != new)
    if (previous_ids != successor_ids or len(changed) != 1 or
            changed[0] != len(previous.grades) - 1):
        raise ValueError("FACTORY_SCHEDULE_REVISION_INVALID")
    revised_grade = successor_ids[changed[0]]
    if state.grade != revised_grade:
        raise ValueError("FACTORY_SCHEDULE_REVISION_REQUIRES_ACTIVE_GRADE")
    champions = dict(state.champions)
    champions.pop(revised_grade, None)
    successor_caps = set(_caps(successor, state.active_grades))
    active_debt = tuple(
        capability for capability in state.carried_mastery_debt
        if capability in successor_caps)
    rebound = replace(
        state,
        course_digest=successor.digest(),
        stage="MAIN",
        queue=(),
        first_recovery=(),
        champions=champions,
        carried_mastery_debt=active_debt,
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
    return rebound, revised_grade


def append_next_grade(previous, successor, state: SchoolState) -> SchoolState:
    """Historical Course append migration; canonical v2 uses release deltas."""
    from bilqis_mlx.compatibility.scheduler_transitions import append_next_grade as legacy
    return legacy(previous, successor, state)


def revise_admitted_grade(previous, successor, state: SchoolState):
    """Historical Course revision; canonical v2 uses release deltas."""
    from bilqis_mlx.compatibility.scheduler_transitions import revise_admitted_grade as legacy
    return legacy(previous, successor, state)


def replace_admitted_grade(previous, successor, state: SchoolState):
    """Historical Course replacement; canonical v2 uses release deltas."""
    from bilqis_mlx.compatibility.scheduler_transitions import replace_admitted_grade as legacy
    return legacy(previous, successor, state)


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
    raw["frontier_catchup_passes"] = int(raw.get("frontier_catchup_passes", 0))
    raw["carried_mastery_debt"] = tuple(raw.get("carried_mastery_debt", ()))
    raw["mature_capability_debt"] = tuple(
        (capability, amount)
        for capability, amount in raw.get("mature_capability_debt", ()))
    raw["mature_grade_debt"] = tuple(
        (grade, amount) for grade, amount in raw.get("mature_grade_debt", ()))
    if not raw["mature_grade_debt"] and raw["mature_capability_debt"]:
        totals = {}
        for capability, amount in raw["mature_capability_debt"]:
            grade = capability.partition(".")[0]
            totals[grade] = totals.get(grade, 0) + amount
        raw["mature_grade_debt"] = tuple(sorted(totals.items()))
        raw["mature_capability_debt"] = ()
    legacy_debt_cadence_policy = "debt_cadence_policy" not in raw
    legacy_b_full_run_epoch = "non_b_training_turns_since_b_run" not in raw
    legacy_promotion_sweep_attempt_epoch = restore_promotion_attempt_fields(raw)
    legacy_frontier_priority_epoch = (
        "frontier_priority_visits" not in raw and
        "nongating_b_visits" not in raw)
    policy_value = raw.get("debt_cadence_policy")
    if policy_value is not None:
        if not isinstance(policy_value, dict):
            ErrorBus.raise_legacy(SCHOOL.SCHEDULE.INVALID_DEBT_CADENCE_POLICY)
        raw["debt_cadence_policy"] = DebtCadencePolicy(**policy_value)
    else:
        raw["debt_cadence_policy"] = None
    raw["promotion_sweep_scope"] = tuple(raw.get("promotion_sweep_scope", ()))
    raw["promotion_sweep_return_stage"] = raw.get(
        "promotion_sweep_return_stage")
    raw["promotion_sweep_scores"] = tuple(
        (capability, correct, total)
        for capability, correct, total in raw.get("promotion_sweep_scores", ()))
    raw["non_b_training_turns_since_b_run"] = raw.get(
        "non_b_training_turns_since_b_run", 0)
    raw["introduction_frontiers"] = tuple(
        (grade, stage) for grade, stage in raw.get("introduction_frontiers", ()))
    raw["current_student"] = Checkpoint(**raw["current_student"])
    raw["champions"] = {grade: Checkpoint(**cp)
                        for grade, cp in raw["champions"].items()}
    result = SchoolState(**raw)
    if legacy_debt_cadence_policy:
        result = migrate_legacy_debt_cadence_policy(program, result)
    if legacy_frontier_priority_epoch:
        result = migrate_legacy_debt_cadence_queue(program, result)
    if legacy_b_full_run_epoch:
        result = migrate_legacy_debt_cadence_epoch(program, result)
    result = (migrate_promotion_sweep_attempt_epoch(program, result)
              if legacy_promotion_sweep_attempt_epoch else result)
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


def _advance_unblocked_introduction(program, state, snapshot, active_pool, blocked):
    """Advance a fully eligible introduction without clearing withheld debt."""
    grade = next(g for g in program.grades if g.id == state.grade)
    current_caps = set(_caps(program, (state.grade,)))
    blocked_current = current_caps & set(blocked)
    if (grade.teaching_stages and state.introduction_stage < len(grade.teaching_stages)-1 and
            not blocked_current):
        own = tuple(c for c in _main_queue(program, state) if c in active_pool)
        if own and all(snapshot.scores[c].perfect for c in own):
            next_stage = state.introduction_stage + 1
            entered = _at_introduction_stage(
                state, next_stage, stage="MAIN", first_recovery=(),
                latest_rubric_digest=snapshot.rubric_digest)
            queue = tuple(c for c in grade.teaching_stages[next_stage]
                          if c not in set(blocked))
            if queue:
                return replace(entered, queue=queue)
