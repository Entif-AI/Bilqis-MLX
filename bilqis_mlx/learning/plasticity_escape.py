"""Bounded retention-starvation plasticity without weakening hard safety gates."""
from __future__ import annotations

from fractions import Fraction

ORDINARY_STARVATION_ATTEMPTS = 32
FRONTIER_STARVATION_ATTEMPTS = 16
SCHOOL_DROUGHT_ATTEMPTS = 24
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


def record_school_visit(teacher: dict, *, retained: bool) -> int:
    """Record one committed teacher visit in the school-wide retention drought."""
    channel = teacher.setdefault("causal_experiment", {})
    attempts = 0 if retained else int(
        channel.get("school_attempts_since_retained", 0)) + 1
    channel["school_attempts_since_retained"] = attempts
    return attempts


def _school_score_context(receipt: dict | None, capability: str):
    scores = ((receipt or {}).get("last_exam") or {}).get("scores") or {}
    valid = []
    current = None
    for name, score in scores.items():
        if (not isinstance(score, dict) or type(score.get("correct")) is not int or
                type(score.get("total")) is not int or score["total"] <= 0 or
                score["correct"] < 0 or score["correct"] > score["total"]):
            continue
        accuracy = Fraction(score["correct"], score["total"])
        valid.append(accuracy)
        if name == capability:
            current = (score["correct"], score["total"], accuracy)
    if current is None or not valid:
        return None, None, len(valid)
    return current, sum(valid, Fraction(0, 1)) / len(valid), len(valid)


def activation(teacher: dict, capability: str, curriculum_scope: str,
               school, program, *, receipt: dict | None = None) -> dict:
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
    channel = teacher.get("causal_experiment", {})
    record = channel.get(
        "capability_stagnation", {}).get(capability + "|" + curriculum_scope, {})
    attempts = int(record.get("attempts_since_retained", 0))
    local_active = attempts >= threshold
    school_attempts = int(channel.get("school_attempts_since_retained", 0))
    current_score, school_mean, measured_count = _school_score_context(
        receipt, capability)
    drought_below_mean = bool(
        school_attempts >= SCHOOL_DROUGHT_ATTEMPTS and
        current_score is not None and school_mean is not None and
        current_score[2] < school_mean)
    training_stage = school.stage in _TRAINING_STAGES
    active = training_stage and (local_active or drought_below_mean)
    triggers = []
    if training_stage and local_active:
        triggers.append("LOCAL_STARVATION")
    if training_stage and drought_below_mean:
        triggers.append("SCHOOL_RETENTION_DROUGHT_BELOW_MEAN")
    return {
        "active": active, "attempts_since_retained": attempts,
        "activation_threshold": threshold, "frontier_priority": frontier_priority,
        "activation_triggers": triggers,
        "school_attempts_since_retained": school_attempts,
        "school_drought_threshold": SCHOOL_DROUGHT_ATTEMPTS,
        "school_exam_capability_count": measured_count,
        "current_capability_score": (
            {"correct": current_score[0], "total": current_score[1]}
            if current_score is not None else None),
        "current_capability_accuracy": (
            float(current_score[2]) if current_score is not None else None),
        "school_mean_accuracy": float(school_mean) if school_mean is not None else None,
        "school_drought_below_mean": drought_below_mean,
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
