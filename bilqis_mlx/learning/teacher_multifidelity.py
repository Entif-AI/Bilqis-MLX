"""Neural-inert multi-fidelity shadow evaluation for teacher candidates."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


SCHEMA = "bilqis.teacher-multifidelity-shadow/v1"


class TeacherMultifidelityError(str, Enum):
    ACTIVATION_POLICY_INVALID = "TEACHER_MULTIFIDELITY_ACTIVATION_POLICY_INVALID"
    BUDGET_INVALID = "TEACHER_MULTIFIDELITY_BUDGET_INVALID"
    OUTCOME_INVALID = "TEACHER_MULTIFIDELITY_OUTCOME_INVALID"
    POLICY_INVALID = "TEACHER_MULTIFIDELITY_POLICY_INVALID"
    PROBES_INVALID = "TEACHER_MULTIFIDELITY_PROBES_INVALID"
    REVIEW_INVALID = "TEACHER_MULTIFIDELITY_REVIEW_INVALID"


@dataclass(frozen=True)
class ShadowPolicy:
    version: str
    rungs: tuple[int, ...]
    minimum_target_delta_to_continue: int
    minimum_decision_step: int = 1

    def __post_init__(self) -> None:
        if (not self.version or not self.rungs or
                any(type(step) is not int or step < 1 for step in self.rungs) or
                tuple(sorted(set(self.rungs))) != self.rungs or
                type(self.minimum_target_delta_to_continue) is not int or
                self.minimum_target_delta_to_continue < 1 or
                type(self.minimum_decision_step) is not int or
                self.minimum_decision_step < 1):
            raise ValueError(TeacherMultifidelityError.POLICY_INVALID.value)


DEFAULT_SHADOW_POLICY = ShadowPolicy(
    version="teacher-multifidelity-shadow/v2",
    rungs=(2, 4, 8, 16),
    minimum_target_delta_to_continue=1,
    minimum_decision_step=8,
)


@dataclass(frozen=True)
class ActivationPolicy:
    version: str
    minimum_reviews: int
    maximum_false_kill_rate: float
    minimum_mean_steps_saved: float

    def __post_init__(self) -> None:
        if (not self.version or type(self.minimum_reviews) is not int or
                self.minimum_reviews < 1 or
                not isinstance(self.maximum_false_kill_rate, (int, float)) or
                not 0 <= self.maximum_false_kill_rate <= 1 or
                not isinstance(self.minimum_mean_steps_saved, (int, float)) or
                self.minimum_mean_steps_saved < 0):
            raise ValueError(TeacherMultifidelityError.ACTIVATION_POLICY_INVALID.value)


DEFAULT_ACTIVATION_POLICY = ActivationPolicy(
    version="teacher-multifidelity-activation/v1",
    minimum_reviews=64,
    maximum_false_kill_rate=.01,
    minimum_mean_steps_saved=2.,
)


def active_rungs(policy: ShadowPolicy, full_budget_steps: int) -> tuple[int, ...]:
    if type(full_budget_steps) is not int or full_budget_steps < 1:
        raise ValueError(TeacherMultifidelityError.BUDGET_INVALID.value)
    rungs = tuple(step for step in policy.rungs if step <= full_budget_steps)
    if not rungs or rungs[-1] != full_budget_steps:
        rungs = (*rungs, full_budget_steps)
    return rungs


def evaluate_shadow(policy: ShadowPolicy, *, probes,
                    final_retained: bool, full_budget_steps: int) -> dict:
    if type(final_retained) is not bool:
        raise ValueError(TeacherMultifidelityError.OUTCOME_INVALID.value)
    expected = active_rungs(policy, full_budget_steps)
    rows = tuple(probes)
    if (not rows or tuple(step for step, _ in rows) != expected or
            any(type(step) is not int or not isinstance(delta, (int, float))
                for step, delta in rows)):
        raise ValueError(TeacherMultifidelityError.PROBES_INVALID.value)
    first_stop = next((
        step for index, (step, delta) in enumerate(rows[:-1])
        if (step >= policy.minimum_decision_step and
            delta < policy.minimum_target_delta_to_continue and
            max(prior_delta for _, prior_delta in rows[:index + 1]) <
            policy.minimum_target_delta_to_continue)
    ), None)
    shadow_steps = first_stop if first_stop is not None else full_budget_steps
    return {
        "schema": SCHEMA,
        "policy_version": policy.version,
        "mode": "SHADOW",
        "rungs": [step for step, _ in rows],
        "target_deltas": [float(delta) for _, delta in rows],
        "first_would_stop_step": first_stop,
        "would_continue_to_full_budget": first_stop is None,
        "final_retained": final_retained,
        "false_kill": bool(first_stop is not None and final_retained),
        "false_continue": bool(first_stop is None and not final_retained),
        "actual_steps_spent": full_budget_steps,
        "shadow_steps_if_active": shadow_steps,
        "shadow_steps_saved": full_budget_steps - shadow_steps,
        "actual_authority_changed": False,
    }


def qualify_activation(reviews, *,
                       policy: ActivationPolicy = DEFAULT_ACTIVATION_POLICY) -> dict:
    rows = tuple(reviews)
    if any(not isinstance(row, dict) or row.get("mode") != "SHADOW" for row in rows):
        raise ValueError(TeacherMultifidelityError.REVIEW_INVALID.value)
    false_kills = sum(bool(row.get("false_kill")) for row in rows)
    stops = sum(row.get("first_would_stop_step") is not None for row in rows)
    mean_saved = (
        sum(float(row.get("shadow_steps_saved", 0)) for row in rows) / len(rows)
        if rows else 0.)
    false_kill_rate = false_kills / stops if stops else 0. if rows else None
    qualified = (
        len(rows) >= policy.minimum_reviews and
        false_kill_rate is not None and
        false_kill_rate <= policy.maximum_false_kill_rate and
        mean_saved >= policy.minimum_mean_steps_saved)
    return {
        "schema": "bilqis.teacher-multifidelity-activation/v1",
        "policy_version": policy.version,
        "status": "QUALIFIED" if qualified else "NOT_QUALIFIED",
        "reviews": len(rows),
        "early_stop_recommendations": stops,
        "false_kills": false_kills,
        "false_kill_rate": false_kill_rate,
        "mean_shadow_steps_saved": mean_saved,
        "authority_changed": False,
    }
