"""Pure grade-debt scheduling helpers shared by the school state machine."""
from __future__ import annotations

from fractions import Fraction
from math import ceil

import bilqis_mlx.mature_debt as _mature_debt

from .state import Score, SchoolState, _caps, _program, _score_pool, weakest_three


FRONTIER_CATCHUP_SHARE_DENOMINATOR = 4
FRONTIER_CATCHUP_MINIMUM_ACTIVE_GRADES = 2
FRONTIER_DEFICIT_WEIGHT_BUCKET = Fraction(1, 10)
FRONTIER_DEFICIT_MAX_VISITS = 6
_ALLOWED_CAPABILITY_OUTSIDE_ASSESSMENT = "SPIRAL_ALLOWED_CAPABILITY_OUTSIDE_ASSESSMENT"
_EXCLUDED_GRADE_OUTSIDE_ACTIVE_PROGRAM = "SPIRAL_EXCLUDED_GRADE_OUTSIDE_ACTIVE_PROGRAM"


def _next_imperfect_grade_index(program, state: SchoolState,
                                scores: dict[str, Score], *,
                                allowed_capabilities: tuple[str, ...] | None = None,
                                excluded_grades: tuple[str, ...] = ()) -> int | None:
    """Find the next imperfect eligible grade in canonical wrapped order."""
    program = _program(program)
    allowed = set(scores) if allowed_capabilities is None else set(allowed_capabilities)
    if not allowed <= set(scores):
        raise ValueError(_ALLOWED_CAPABILITY_OUTSIDE_ASSESSMENT)
    excluded = set(excluded_grades)
    if not excluded <= set(state.active_grades):
        raise ValueError(_EXCLUDED_GRADE_OUTSIDE_ACTIVE_PROGRAM)
    count = len(state.active_grades)
    for offset in range(1, count + 1):
        index = (state.grade_index + offset) % count
        if state.active_grades[index] in excluded:
            continue
        grade_caps = _caps(program, (state.active_grades[index],))
        eligible = tuple(cap for cap in grade_caps if cap in allowed)
        if eligible and any(not scores[cap].perfect for cap in eligible):
            return index
    return None


def _frontier_catchup_target_passes(program, state: SchoolState,
                                    scores: dict[str, Score],
                                    allowed_capabilities: tuple[str, ...] | None = None
                                    ) -> int:
    """Return total frontier MAIN passes due while progression remains imperfect."""
    program = _program(program)
    if len(state.active_grades) < FRONTIER_CATCHUP_MINIMUM_ACTIVE_GRADES:
        return 1
    eligible_pool = set(_score_pool(program, state))
    allowed = ((set(scores) if allowed_capabilities is None else set(allowed_capabilities)) &
               eligible_pool)
    frontier = state.active_grades[-1]
    frontier_caps = tuple(
        capability for capability in _caps(program, (frontier,))
        if capability in allowed and capability in scores)
    school_caps = tuple(
        capability for capability in _caps(program, state.active_grades)
        if capability in allowed and capability in scores)
    if not frontier_caps or len(school_caps) <= len(frontier_caps):
        return 1
    if all(scores[capability].perfect for capability in frontier_caps):
        return 1
    mature_count = len(school_caps) - len(frontier_caps)
    divisor = (FRONTIER_CATCHUP_SHARE_DENOMINATOR - 1) * len(frontier_caps)
    return max(1, (mature_count + divisor - 1) // divisor)


def _debt_cadence_mode(program, state: SchoolState) -> bool:
    program = _program(program)
    policy = state.debt_cadence_policy
    if (policy is None or
            not {policy.bounded_debt_grade_id,
                 policy.progression_priority_grade_id} <= set(state.active_grades)):
        return False
    debt = set(state.carried_mastery_debt)
    return bool(debt & set(_caps(program, (policy.bounded_debt_grade_id,)))) and bool(
        debt & set(_caps(program, (policy.progression_priority_grade_id,))))


def _debt_run_due(program, state: SchoolState) -> bool:
    return (_debt_cadence_mode(program, state) and
            state.non_b_training_turns_since_b_run >=
            state.debt_cadence_policy.non_debt_turns_per_run)


def _debt_run_queue(program, state: SchoolState, scores: dict[str, Score],
                    allowed_capabilities: tuple[str, ...] | None = None
                    ) -> tuple[str, ...]:
    if not _debt_cadence_mode(program, state):
        return ()
    program = _program(program)
    allowed = set(scores) if allowed_capabilities is None else set(allowed_capabilities)
    debt = set(state.carried_mastery_debt)
    grade = state.debt_cadence_policy.bounded_debt_grade_id
    return tuple(capability for capability in _caps(program, (grade,))
                 if capability in allowed and capability in debt and
                 capability in scores and not scores[capability].perfect)


def _imperfect_ranked(scores: dict[str, Score],
                      capabilities: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(
        (capability for capability in capabilities
         if capability in scores and not scores[capability].perfect),
        key=lambda capability: (scores[capability].accuracy, capability)))


def _frontier_recovery_queue(program, state: SchoolState,
                             scores: dict[str, Score],
                             pool: tuple[str, ...]) -> tuple[str, ...]:
    if not _debt_cadence_mode(program, state):
        return weakest_three(scores, pool)
    program = _program(program)
    allowed = set(pool)
    priority = state.debt_cadence_policy.progression_priority_grade_id
    ranked = _imperfect_ranked(
        scores, tuple(cap for cap in _caps(program, (priority,)) if cap in allowed))
    ranked = ranked[:3]
    if not ranked:
        return ()
    measured = tuple(scores[capability].accuracy for capability in pool
                     if capability in scores)
    school_mean = sum(measured, Fraction(0, 1)) / len(measured)
    weights = {
        capability: min(
            FRONTIER_DEFICIT_MAX_VISITS,
            1 + ceil(max(Fraction(0, 1),
                         school_mean - scores[capability].accuracy) /
                     FRONTIER_DEFICIT_WEIGHT_BUCKET))
        for capability in ranked
    }
    return tuple(
        capability
        for pass_index in range(max(weights.values()))
        for capability in ranked
        if weights[capability] > pass_index
    )


def _mature_debt_repair_grade(program, state: SchoolState) -> str | None:
    program = _program(program)
    return _mature_debt.repair_grade(
        state.active_grades, state.champions, state.mature_grade_debt,
        {grade: _caps(program, (grade,)) for grade in state.active_grades})


def _apply_mature_debt_frontier(program, state: SchoolState, frontier
                                ) -> tuple[tuple[str, int], ...]:
    return _mature_debt.apply_frontier(
        state.mature_grade_debt, tuple(state.champions), frontier)
