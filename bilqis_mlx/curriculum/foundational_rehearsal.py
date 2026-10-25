"""Bounded rehearsal policy for decayed previously mastered foundation grades."""
from __future__ import annotations

from fractions import Fraction

from .debt_priority import NONGATING_DEBT_RUN_INTERVAL
from .school_state import SchoolState, Score, _caps, _program


# Foundations get half the rehearsal frequency of the immediate predecessor:
# enough to recover measured decay without crowding the active frontier/debt pair.
FOUNDATIONAL_DEBT_RUN_INTERVAL = NONGATING_DEBT_RUN_INTERVAL * 2
MINIMUM_ACTIVE_GRADES_FOR_FOUNDATIONAL_REHEARSAL = 3


def rehearsal_plan(
        program, state: SchoolState, scores: dict[str, Score], *,
        allowed_capabilities: tuple[str, ...] | None = None,
        priority_active: bool) -> tuple[str, tuple[str, ...]] | None:
    """Return the weakest mastered foundation and its imperfect live capabilities."""
    if (not priority_active or
            state.non_foundational_training_turns_since_foundational_run <
            FOUNDATIONAL_DEBT_RUN_INTERVAL):
        return None
    program = _program(program)
    if len(state.active_grades) < MINIMUM_ACTIVE_GRADES_FOR_FOUNDATIONAL_REHEARSAL:
        return None
    allowed = set(scores) if allowed_capabilities is None else set(allowed_capabilities)
    candidates = []
    for grade_index, grade in enumerate(state.active_grades[:-2]):
        if grade not in state.champions:
            continue
        caps = tuple(capability for capability in _caps(program, (grade,))
                     if capability in allowed and capability in scores)
        imperfect = tuple(
            capability for capability in caps if not scores[capability].perfect)
        if not imperfect:
            continue
        mean = sum(
            (scores[capability].accuracy for capability in caps), Fraction()) / len(caps)
        candidates.append((mean, grade_index, grade, imperfect))
    if not candidates:
        return None
    _mean, _index, grade, queue = min(candidates)
    return grade, queue
