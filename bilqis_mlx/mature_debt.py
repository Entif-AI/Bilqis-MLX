"""Bounded mature-skill debt bookkeeping independent of scheduler mechanics."""
from __future__ import annotations

REPAIR_THRESHOLD = 2
HARD_LIMIT = 4
RELEASE_THRESHOLD = 1


def as_mapping(state) -> dict[str, int]:
    return dict(getattr(state, "mature_capability_debt", ()))


def apply_frontier(current, mature_capabilities, frontier) -> tuple[tuple[str, int], ...]:
    if not frontier or frontier.get("status") != "MEASURED":
        return tuple(current)
    mature = set(mature_capabilities)
    debt = dict(current)
    for item in frontier.get("regressions", ()):
        capability = item.get("capability")
        if capability in mature:
            debt[capability] = debt.get(capability, 0) + 1
    for item in frontier.get("repaired", ()):
        capability = item.get("capability")
        if capability not in mature:
            continue
        remaining = debt.get(capability, 0) - 1
        if remaining > 0:
            debt[capability] = remaining
        else:
            debt.pop(capability, None)
    return tuple(sorted(debt.items()))


def grade_totals(current: dict[str, int], mature_grades) -> dict[str, int]:
    totals = {}
    for capability, amount in current.items():
        grade = capability.partition(".")[0]
        if grade in mature_grades:
            totals[grade] = totals.get(grade, 0) + amount
    return totals


def project_grade_debt(frontier, mature_grades, current):
    before = grade_totals(current, mature_grades)
    projected_items = apply_frontier(
        tuple(current.items()),
        tuple(capability for capability in current) + tuple(
            item.get("capability") for key in ("regressions", "repaired")
            for item in frontier.get(key, ())
            if item.get("capability", "").partition(".")[0] in mature_grades),
        frontier,
    )
    projected = grade_totals(dict(projected_items), mature_grades)
    exceeded = any(
        amount > HARD_LIMIT and amount > before.get(grade, 0)
        for grade, amount in projected.items())
    return projected, exceeded


def retention_reason(reason, frontier, mature_grades, current):
    projected, exceeded = project_grade_debt(frontier, mature_grades, current)
    if exceeded and reason == "PAIRED_SCREEN_WITHIN_BUDGET":
        reason = "MATURE_GRADE_DEBT_LIMIT"
    return projected, reason


def repair_grade(active_grades, champions, current, grade_capabilities):
    debt = dict(current)
    due = []
    for grade in champions:
        if grade not in active_grades:
            continue
        amount = sum(debt.get(capability, 0)
                     for capability in grade_capabilities.get(grade, ()))
        if amount >= REPAIR_THRESHOLD:
            due.append((amount, active_grades.index(grade), grade))
    return max(due, key=lambda item: (item[0], -item[1]))[2] if due else None


def repair_queue(current, capabilities, allowed=None):
    debt = dict(current)
    eligible = set(capabilities) if allowed is None else set(allowed)
    ranked = ((capability, debt.get(capability, 0)) for capability in capabilities
              if capability in eligible and debt.get(capability, 0) > 0)
    return tuple(capability for capability, _ in sorted(
        ranked, key=lambda item: (-item[1], item[0])))


def retained_frontier(outcome):
    if outcome is None or outcome.get("decision") != "PROVISIONAL":
        return None
    return outcome.get("fixed_frontier_replay")
