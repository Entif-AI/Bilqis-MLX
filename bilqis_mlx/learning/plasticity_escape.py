"""Bounded retention-starvation plasticity without weakening hard safety gates."""
from __future__ import annotations

from fractions import Fraction

ORDINARY_STARVATION_ATTEMPTS = 32
FRONTIER_STARVATION_ATTEMPTS = 16
SCHOOL_DROUGHT_ATTEMPTS = 24
MASTERY_DEBT_POWER = 2
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


def _mastery_debt_utility(scores: dict, capabilities=None) -> tuple[Fraction, dict]:
    """Value one vote per capability by normalized squared distance from mastery."""
    if not isinstance(scores, dict):
        raise ValueError("PLASTICITY_MASTERY_DEBT_SCORES_INVALID")
    selected = tuple(sorted(scores if capabilities is None else capabilities))
    if not selected or any(cap not in scores for cap in selected):
        raise ValueError("PLASTICITY_MASTERY_DEBT_SCOPE_INVALID")
    net = Fraction(0, 1)
    details = {}
    for capability in selected:
        score = scores[capability]
        if not isinstance(score, dict):
            raise ValueError("PLASTICITY_MASTERY_DEBT_SCORE_INVALID")
        before, after, total = (score.get(name) for name in ("before", "after", "total"))
        if (any(type(value) is not int for value in (before, after, total)) or
                total <= 0 or not 0 <= before <= total or not 0 <= after <= total):
            raise ValueError("PLASTICITY_MASTERY_DEBT_SCORE_INVALID")
        before_accuracy = Fraction(before, total)
        after_accuracy = Fraction(after, total)
        before_debt = Fraction(1, 1) - before_accuracy
        after_debt = Fraction(1, 1) - after_accuracy
        utility = before_debt ** MASTERY_DEBT_POWER - after_debt ** MASTERY_DEBT_POWER
        net += utility
        details[capability] = {
            "before_accuracy": round(float(before_accuracy), 12),
            "after_accuracy": round(float(after_accuracy), 12),
            "before_debt": round(float(before_debt), 12),
            "after_debt": round(float(after_debt), 12),
            "utility_delta": round(float(utility), 12),
        }
    return net, {
        "net": round(float(net), 12),
        "positive": net > 0,
        "capability_count": len(selected),
        "capabilities": details,
    }


def mastery_debt_utility(scores: dict, capabilities=None) -> dict:
    """JSON-safe public description of normalized quadratic mastery-debt utility."""
    _net, result = _mastery_debt_utility(scores, capabilities)
    return {"power": MASTERY_DEBT_POWER, **result}


def _optional_utility(scores: dict | None, capabilities=None):
    if not scores:
        return None, None
    net, result = _mastery_debt_utility(scores, capabilities)
    return net, result


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
        "mastery_debt_power": MASTERY_DEBT_POWER,
        "plasticity_trade_policy": "NORMALIZED_QUADRATIC_MASTERY_DEBT",
    }


def allows_early_grade_net(state: dict | None, paired: dict,
                           capabilities) -> bool:
    if not state or not state.get("active"):
        return False
    utility, _details = _mastery_debt_utility(paired, capabilities)
    return utility > 0


def maybe_relax(reason: str, *, state: dict | None, no_target_gain: bool,
                paired: dict, same_grade_capabilities,
                fixed_grade_scores: dict | None,
                frontier_scores: dict | None,
                protected_frontier_grade: str | None,
                fixed_grade_net_gain: int | None,
                active_frontier_grade_net_gain: int | None,
                whole_school_net_gain: int | None,
                fragile_losses: bool) -> tuple[str, dict]:
    telemetry = {**(state or {}), "applied": False, "waived_reason": None}
    if (not telemetry.get("active") or no_target_gain or fragile_losses or
            reason not in _RELAXABLE_REASONS):
        return reason, telemetry
    paired_net, paired_utility = _mastery_debt_utility(paired)
    same_grade_net, same_grade_utility = _mastery_debt_utility(
        paired, same_grade_capabilities)
    fixed_grade_utility_net, fixed_grade_utility = _optional_utility(
        fixed_grade_scores)
    frontier_utility_net, frontier_utility = _optional_utility(frontier_scores)
    active_frontier_scores = None
    if frontier_scores and protected_frontier_grade is not None:
        active_frontier_scores = {
            capability: score for capability, score in frontier_scores.items()
            if capability.partition(".")[0] == protected_frontier_grade
        }
    active_frontier_utility_net, active_frontier_utility = _optional_utility(
        active_frontier_scores)
    telemetry["mastery_debt_utility"] = {
        "power": MASTERY_DEBT_POWER,
        "paired": paired_utility,
        "same_grade": same_grade_utility,
        "fixed_grade": fixed_grade_utility,
        "active_frontier_grade": active_frontier_utility,
        "whole_school_frontier": frontier_utility,
    }
    # Plasticity trades only when measured learning reduces normalized mastery
    # debt. Each capability contributes one vote regardless of probe-row count.
    # Squared deficit makes near-perfect surplus cheap to borrow from, while the
    # cost accelerates if the same capability keeps being cannibalized.
    if same_grade_net <= 0 or paired_net <= 0:
        return reason, telemetry
    if (fixed_grade_net_gain is not None and fixed_grade_net_gain < 0 and
            (fixed_grade_utility_net is None or fixed_grade_utility_net <= 0)):
        return reason, telemetry
    if (active_frontier_grade_net_gain is not None and
            active_frontier_grade_net_gain < 0 and
            (active_frontier_utility_net is None or active_frontier_utility_net <= 0)):
        return reason, telemetry
    if (whole_school_net_gain is not None and
            whole_school_net_gain < 0 and
            (frontier_utility_net is None or frontier_utility_net <= 0)):
        return reason, telemetry
    telemetry["applied"] = True
    telemetry["waived_reason"] = reason
    return "PAIRED_SCREEN_WITHIN_BUDGET", telemetry
