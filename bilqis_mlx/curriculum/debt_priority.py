"""Grade-neutral priority policy for frontier and immediate-predecessor debt."""
from __future__ import annotations

from .school_state import SchoolState, Score, _caps, _program


NONGATING_DEBT_RUN_INTERVAL = 4
NONGATING_PRIORITY_GRADE_COUNT = 3


def roles(program, state: SchoolState) -> tuple[str, str] | None:
    """Return immediate prior debt grade and newest progression frontier."""
    program = _program(program)
    if len(state.active_grades) < NONGATING_PRIORITY_GRADE_COUNT:
        return None
    debt_grade, frontier_grade = state.active_grades[-2:]
    debt = set(state.carried_mastery_debt)
    if (not debt & set(_caps(program, (debt_grade,))) or
            not debt & set(_caps(program, (frontier_grade,)))):
        return None
    return debt_grade, frontier_grade


def debt_run_due(program, state: SchoolState) -> bool:
    return (roles(program, state) is not None and
            state.non_b_training_turns_since_b_run >= NONGATING_DEBT_RUN_INTERVAL)


def debt_run_queue(program, state: SchoolState, scores: dict[str, Score],
                   allowed_capabilities: tuple[str, ...] | None = None
                   ) -> tuple[str, ...]:
    """Return imperfect admitted capabilities in the nongating debt grade."""
    pair = roles(program, state)
    if pair is None:
        return ()
    debt_grade, _ = pair
    allowed = set(scores) if allowed_capabilities is None else set(allowed_capabilities)
    debt = set(state.carried_mastery_debt)
    return tuple(
        capability for capability in _caps(program, (debt_grade,))
        if capability in allowed and capability in debt and
        capability in scores and not scores[capability].perfect)


def imperfect_ranked(scores: dict[str, Score],
                     capabilities: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(
        (capability for capability in capabilities
         if capability in scores and not scores[capability].perfect),
        key=lambda capability: (scores[capability].accuracy, capability),
    ))


def frontier_recovery_queue(program, state: SchoolState,
                            scores: dict[str, Score],
                            pool: tuple[str, ...]) -> tuple[str, ...]:
    """Keep frontier recovery frontier-only; debt gets bounded full turns."""
    pair = roles(program, state)
    if pair is None:
        ranking = imperfect_ranked(scores, pool)
        return ranking[:3]
    _, frontier_grade = pair
    allowed = set(pool)
    ranking = imperfect_ranked(
        scores, tuple(
            capability for capability in _caps(program, (frontier_grade,))
            if capability in allowed))
    return ranking[:3]
