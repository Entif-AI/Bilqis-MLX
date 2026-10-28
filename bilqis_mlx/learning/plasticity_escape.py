"""Bounded retention-starvation plasticity without weakening hard safety gates."""
from __future__ import annotations

ORDINARY_STARVATION_ATTEMPTS = 32
FRONTIER_STARVATION_ATTEMPTS = 16
MAX_SAME_GRADE_NET_LOSS = 1
PROTECTED_EXTRA_LOSS = 1
MAX_FIXED_GRADE_NET_LOSS = 1
MAX_ACTIVE_FRONTIER_GRADE_NET_LOSS = 1
MAX_WHOLE_SCHOOL_NET_LOSS = 1
_TRAINING_STAGES = frozenset({"MAIN", "RECOVERY_1", "RECOVERY_2"})
_RELAXABLE_REASONS = frozenset({
    "PROTECTED_CAPABILITY_REGRESSION", "SAME_GRADE_NET_REGRESSION",
    "NO_POSITIVE_SAME_GRADE_GAIN", "FIXED_GRADE_COHORT_REGRESSION",
    "FIXED_LESSON_GRADE_REGRESSION", "ACTIVE_SCHOOL_GRADE_REGRESSION",
    "WHOLE_SCHOOL_NET_REGRESSION",
})


def activation(teacher: dict, capability: str, curriculum_scope: str,
               school, program) -> dict:
    grade = capability.partition(".")[0]
    newest_grade = bool(school.active_grades) and grade == school.active_grades[-1]
    current_stage_semantic = False
    if grade == school.grade:
        grade_spec = next((g for g in program.grades if g.id == grade), None)
        stages = () if grade_spec is None else grade_spec.teaching_stages
        if stages and 0 <= school.introduction_stage < len(stages):
            current_stage_semantic = capability in stages[school.introduction_stage]
    frontier_priority = newest_grade or current_stage_semantic
    threshold = (FRONTIER_STARVATION_ATTEMPTS if frontier_priority
                 else ORDINARY_STARVATION_ATTEMPTS)
    record = teacher.get("causal_experiment", {}).get(
        "capability_stagnation", {}).get(capability + "|" + curriculum_scope, {})
    attempts = int(record.get("attempts_since_retained", 0))
    active = school.stage in _TRAINING_STAGES and attempts >= threshold
    return {
        "active": active, "attempts_since_retained": attempts,
        "activation_threshold": threshold, "frontier_priority": frontier_priority,
        "newest_grade": newest_grade,
        "current_introduction_semantic": current_stage_semantic,
        "max_same_grade_net_loss": MAX_SAME_GRADE_NET_LOSS,
        "protected_extra_loss": PROTECTED_EXTRA_LOSS,
        "max_fixed_grade_net_loss": MAX_FIXED_GRADE_NET_LOSS,
        "max_active_frontier_grade_net_loss": MAX_ACTIVE_FRONTIER_GRADE_NET_LOSS,
        "max_whole_school_net_loss": MAX_WHOLE_SCHOOL_NET_LOSS,
    }


def allows_early_grade_net(state: dict | None, grade_net: int) -> bool:
    return bool(state and state.get("active") and
                grade_net >= -MAX_SAME_GRADE_NET_LOSS)


def maybe_relax(reason: str, *, state: dict | None, no_target_gain: bool,
                same_grade_net_gain: int, fixed_grade_net_gain: int | None,
                active_frontier_grade_net_gain: int | None,
                whole_school_net_gain: int | None, regressions: dict,
                tolerances: dict, fragile_losses: bool) -> tuple[str, dict]:
    telemetry = {**(state or {}), "applied": False, "waived_reason": None}
    if (not telemetry.get("active") or no_target_gain or fragile_losses or
            reason not in _RELAXABLE_REASONS):
        return reason, telemetry
    if same_grade_net_gain < -MAX_SAME_GRADE_NET_LOSS:
        return reason, telemetry
    if (fixed_grade_net_gain is not None and
            fixed_grade_net_gain < -MAX_FIXED_GRADE_NET_LOSS):
        return reason, telemetry
    if (active_frontier_grade_net_gain is not None and
            active_frontier_grade_net_gain < -MAX_ACTIVE_FRONTIER_GRADE_NET_LOSS):
        return reason, telemetry
    if (whole_school_net_gain is not None and
            whole_school_net_gain < -MAX_WHOLE_SCHOOL_NET_LOSS):
        return reason, telemetry
    if any(loss > tolerances.get(cap, 0) + PROTECTED_EXTRA_LOSS
           for cap, loss in regressions.items()):
        return reason, telemetry
    telemetry["applied"] = True
    telemetry["waived_reason"] = reason
    return "PAIRED_SCREEN_WITHIN_BUDGET", telemetry
