"""Pure grade-debt scheduling helpers shared by the school state machine."""
from __future__ import annotations

import bilqis_mlx.mature_debt as _mature_debt

from .state import Score, SchoolState, _caps, _program, weakest_three


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
    return ranked[:3]


def _mature_debt_repair_grade(program, state: SchoolState) -> str | None:
    program = _program(program)
    return _mature_debt.repair_grade(
        state.active_grades, state.champions, state.mature_grade_debt,
        {grade: _caps(program, (grade,)) for grade in state.active_grades})


def _apply_mature_debt_frontier(program, state: SchoolState, frontier
                                ) -> tuple[tuple[str, int], ...]:
    return _mature_debt.apply_frontier(
        state.mature_grade_debt, tuple(state.champions), frontier)
