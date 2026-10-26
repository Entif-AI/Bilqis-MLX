"""Pure mean-stability sweep eligibility and serialized-state invariants."""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scheduler import SchoolState, Score

class PromotionError(str, Enum):
    GRADE_MEAN_REQUIRES_COMPLETE_SEMANTIC_SET = "GRADE_MEAN_REQUIRES_COMPLETE_SEMANTIC_SET"
    INVALID_PROMOTION_SWEEP_STATE = "INVALID_PROMOTION_SWEEP_STATE"
    PROMOTION_SWEEP_STATE_OUTSIDE_SWEEP = "PROMOTION_SWEEP_STATE_OUTSIDE_SWEEP"
    INVALID_DEBT_BEARING_GRADE_BOUNDARY = "INVALID_DEBT_BEARING_GRADE_BOUNDARY"
    PROMOTION_SWEEP_ASSESSMENT_WITHOUT_VISIT = "PROMOTION_SWEEP_ASSESSMENT_WITHOUT_VISIT"


PROMOTION_SWEEP_ENTRY_FLOOR = Fraction(92, 100)
PROMOTION_SWEEP_FAILURE_FLOOR = Fraction(87, 100)


def _introduced_grade_capabilities(program, state: SchoolState) -> tuple[str, ...]:
    grade = next(g for g in program.grades if g.id == state.grade)
    if not grade.teaching_stages:
        return tuple(capability.id for capability in grade.capabilities)
    return tuple(
        capability
        for stage in grade.teaching_stages[:state.introduction_stage + 1]
        for capability in stage
    )


def _mean_accuracy(scores: dict[str, Score],
                   capabilities: tuple[str, ...]) -> Fraction:
    if not capabilities or not set(capabilities) <= set(scores):
        raise ValueError(PromotionError.GRADE_MEAN_REQUIRES_COMPLETE_SEMANTIC_SET.value)
    return sum((scores[capability].accuracy for capability in capabilities),
               Fraction(0, 1)) / len(capabilities)


def _promotion_sweep_fields_cleared(state: SchoolState, **changes) -> SchoolState:
    return replace(
        state,
        promotion_sweep_scope=(),
        promotion_sweep_return_stage=None,
        promotion_sweep_scores=(),
        **changes,
    )


def _verify_promotion_sweep_state(program, state: SchoolState) -> None:
    sweep_active = state.stage in ("PROMOTION_SWEEP", "ASSESS_PROMOTION_SWEEP")
    scope = state.promotion_sweep_scope
    return_stage = state.promotion_sweep_return_stage
    scores = state.promotion_sweep_scores
    attempt_student = state.promotion_sweep_attempt_student_sha256
    attempt_scope = state.promotion_sweep_attempt_scope
    attempt_pair_valid = (
        (attempt_student is None and not attempt_scope) or
        (isinstance(attempt_student, str) and len(attempt_student) == 64 and
         all(char in "0123456789abcdef" for char in attempt_student) and
         bool(attempt_scope) and len(set(attempt_scope)) == len(attempt_scope))
    )
    if not attempt_pair_valid:
        raise ValueError(PromotionError.INVALID_PROMOTION_SWEEP_STATE.value)
    if not sweep_active:
        if scope or return_stage is not None or scores:
            raise ValueError(PromotionError.PROMOTION_SWEEP_STATE_OUTSIDE_SWEEP.value)
        return

    introduced = _introduced_grade_capabilities(program, state)
    valid_return_stage = return_stage in (
        "ASSESS_MAIN", "ASSESS_RECOVERY_1", "ASSESS_RECOVERY_2")
    valid_queue = (
        len(state.queue) <= len(scope) and
        state.queue == scope[len(scope)-len(state.queue):])
    valid_phase_queue = (
        (state.stage == "PROMOTION_SWEEP" and bool(state.queue)) or
        (state.stage == "ASSESS_PROMOTION_SWEEP" and
         len(state.queue) < len(scope)))
    valid_scores = (
        len(scores) == len(scope) and
        tuple(item[0] for item in scores) == scope and
        all(
            isinstance(item, tuple) and len(item) == 3 and
            isinstance(item[0], str) and type(item[1]) is int and
            type(item[2]) is int and 0 <= item[1] <= item[2] and item[2] > 0
            for item in scores)
    )
    if (not scope or scope != introduced or attempt_scope != scope or
            not valid_return_stage or not valid_queue or not valid_phase_queue):
        raise ValueError(PromotionError.INVALID_PROMOTION_SWEEP_STATE.value)
    if not valid_scores:
        raise ValueError(PromotionError.INVALID_PROMOTION_SWEEP_STATE.value)


def _promotion_sweep_due(program, state: SchoolState,
                         snapshot: Assessment) -> bool:
    if state.revalidation_target_grade is not None or state.grade in state.champions:
        return False
    scope = _introduced_grade_capabilities(program, state)
    if (state.promotion_sweep_attempt_student_sha256 == state.current_student.sha256 and
            state.promotion_sweep_attempt_scope == scope):
        return False
    return _mean_accuracy(snapshot.scores, scope) >= PROMOTION_SWEEP_ENTRY_FLOOR


def _start_promotion_sweep(program, state: SchoolState,
                           snapshot: Assessment) -> SchoolState:
    scope = _introduced_grade_capabilities(program, state)
    return replace(
        state, stage="PROMOTION_SWEEP", queue=scope,
        promotion_sweep_scope=scope,
        promotion_sweep_return_stage=state.stage,
        promotion_sweep_attempt_student_sha256=state.current_student.sha256,
        promotion_sweep_attempt_scope=scope,
        promotion_sweep_scores=tuple(
            (capability, snapshot.scores[capability].correct,
             snapshot.scores[capability].total)
            for capability in scope),
        latest_rubric_digest=snapshot.rubric_digest,
    )



def _active_capabilities(program, state):
    lookup = {grade.id: grade for grade in program.grades}
    return tuple(capability.id for grade_id in state.active_grades
                 for capability in lookup[grade_id].capabilities)


def _promotion_debt(program, state: SchoolState,
                    snapshot: Assessment) -> tuple[str, ...]:
    unresolved = set(state.carried_mastery_debt)
    unresolved.update(
        capability for capability in state.promotion_sweep_scope
        if not snapshot.scores[capability].perfect)
    return tuple(
        capability for capability in _active_capabilities(program, state)
        if capability in unresolved
    )


def _boundary_mastery_debt(program, state: SchoolState,
                           snapshot: Assessment,
                           fallback: tuple[str, ...]) -> tuple[str, ...]:
    all_caps = _active_capabilities(program, state)
    if not set(all_caps) <= set(snapshot.scores):
        return fallback
    return tuple(capability for capability in all_caps
                 if not snapshot.scores[capability].perfect)
