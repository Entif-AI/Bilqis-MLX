"""Bounded mature-skill debt bookkeeping independent of scheduler mechanics."""
from __future__ import annotations

REPAIR_THRESHOLD = 2
HARD_LIMIT = 4
RELEASE_THRESHOLD = 1


def as_mapping(state) -> dict[str, int]:
    return dict(getattr(state, "mature_grade_debt", ()))


def apply_frontier(current, mature_grades, frontier) -> tuple[tuple[str, int], ...]:
    if not frontier or frontier.get("status") != "MEASURED":
        return tuple(current)
    mature = set(mature_grades)
    debt = dict(current)
    for grade, evidence in (frontier.get("grades") or {}).items():
        if grade not in mature:
            continue
        delta = evidence.get("net_correct_delta")
        if type(delta) is not int:
            continue
        remaining = debt.get(grade, 0) - delta
        if remaining > 0:
            debt[grade] = remaining
        else:
            debt.pop(grade, None)
    return tuple(sorted(debt.items()))


def project_grade_debt(frontier, mature_grades, current):
    before = {grade: amount for grade, amount in current.items()
              if grade in mature_grades}
    projected = dict(apply_frontier(tuple(current.items()), mature_grades, frontier))
    exceeded = any(
        amount > HARD_LIMIT and amount > before.get(grade, 0)
        for grade, amount in projected.items())
    return projected, exceeded


def retention_reason(reason, frontier, mature_grades, current):
    projected, exceeded = project_grade_debt(frontier, mature_grades, current)
    if exceeded and reason == "PAIRED_SCREEN_WITHIN_BUDGET":
        reason = "MATURE_GRADE_DEBT_LIMIT"
    return projected, reason


def repair_grade(active_grades, champions, current, grade_capabilities=None):
    debt = dict(current)
    due = []
    for grade in champions:
        if grade not in active_grades:
            continue
        amount = debt.get(grade, 0)
        if amount >= REPAIR_THRESHOLD:
            due.append((amount, active_grades.index(grade), grade))
    return max(due, key=lambda item: (item[0], -item[1]))[2] if due else None


def retained_frontier(outcome):
    if outcome is None or outcome.get("decision") != "PROVISIONAL":
        return None
    return outcome.get("fixed_frontier_replay")
