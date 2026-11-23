"""Zero-authority multi-fidelity evidence for persistent BAMF candidates."""
from __future__ import annotations

from bilqis_mlx.learning.teacher_multifidelity import MIN_SHADOW_EVIDENCE_BUDGET_STEPS

from .support import _invalid, _plain


def configure_multifidelity(
        capture, *, full_budget_steps: int, rungs, policy_version: str,
        minimum_target_delta_to_continue: int, minimum_decision_step: int):
    rungs = tuple(rungs)
    if (type(full_budget_steps) is not int
            or full_budget_steps < MIN_SHADOW_EVIDENCE_BUDGET_STEPS
            or not isinstance(policy_version, str) or not policy_version
            or type(minimum_target_delta_to_continue) is not int
            or minimum_target_delta_to_continue < 1
            or type(minimum_decision_step) is not int
            or minimum_decision_step < 1
            or not rungs or tuple(sorted(set(rungs))) != rungs
            or rungs[-1] != full_budget_steps
            or any(type(step) is not int or step < 1 for step in rungs)):
        _invalid("BAMF_MULTIFIDELITY_SHADOW_CONFIG_INVALID")
    configured = {
        "schema": "bilqis.bamf.multifidelity-shadow-trace/v1",
        "mode": "SHADOW",
        "policy_version": policy_version,
        "minimum_target_delta_to_continue": minimum_target_delta_to_continue,
        "minimum_decision_step": minimum_decision_step,
        "full_budget_steps": full_budget_steps,
        "expected_rungs": list(rungs),
        "rungs": [],
        "actual_authority_changed": False,
    }
    if capture._multifidelity is not None and capture._multifidelity != configured:
        _invalid("BAMF_MULTIFIDELITY_SHADOW_CONFIG_DRIFT")
    capture._multifidelity = configured


def record_multifidelity_rung(
        capture, *, step: int, target_probe: dict, probe_wall_seconds: float):
    trace = capture._multifidelity
    if (not isinstance(trace, dict) or not isinstance(target_probe, dict)
            or type(step) is not int or step < 1
            or not isinstance(probe_wall_seconds, (int, float))
            or probe_wall_seconds < 0):
        _invalid("BAMF_MULTIFIDELITY_SHADOW_RUNG_INVALID")
    expected = trace["expected_rungs"]
    observed = trace["rungs"]
    if len(observed) >= len(expected) or step != expected[len(observed)]:
        _invalid("BAMF_MULTIFIDELITY_SHADOW_RUNG_ORDER_INVALID")
    if (target_probe.get("actual_authority_changed") is not False
            or type(target_probe.get("target_correct_delta")) not in (int, float)):
        _invalid("BAMF_MULTIFIDELITY_SHADOW_PROBE_INVALID")
    deltas = [
        float(row["target_probe"]["target_correct_delta"])
        for row in observed
    ] + [float(target_probe["target_correct_delta"])]
    if step < trace["minimum_decision_step"]:
        recommendation = "OBSERVE"
    elif max(deltas) < trace["minimum_target_delta_to_continue"]:
        recommendation = "WOULD_STOP"
    else:
        recommendation = "WOULD_CONTINUE"
    step_walls = []
    for delivery in capture._steps:
        realized = delivery.get("controls", {}).get("realized_cost", {})
        wall = realized.get("candidate_step_wall_seconds")
        if isinstance(wall, (int, float)) and wall >= 0:
            step_walls.append(float(wall))
        else:
            step_walls = []
            break
    observed.append({
        "step": step,
        "target_probe": _plain(target_probe),
        "controller_recommendation": recommendation,
        "predicted_retention": {
            "status": "NOT_MEASURED",
            "reason": "TARGET_DELTA_RULE_IS_NOT_A_RETENTION_PROBABILITY",
        },
        "predicted_effect": {
            "status": "MEASURED_TARGET_SENTINEL",
            "target_correct_delta": float(target_probe["target_correct_delta"]),
        },
        "uncertainty": {
            "status": "NOT_MEASURED",
            "reason": "DETERMINISTIC_SHADOW_THRESHOLD_HAS_NO_CALIBRATED_UNCERTAINTY",
        },
        "predicted_cost": {
            "remaining_optimizer_steps": trace["full_budget_steps"] - step,
            "future_wall_seconds": "NOT_MEASURED",
        },
        "bounded_preservation_sentinel": {
            "status": "NOT_MEASURED",
            "reason": "TARGET_ONLY_SHADOW_PROBE",
        },
        "probe_wall_seconds": float(probe_wall_seconds),
        "cumulative_candidate_step_wall_seconds": (
            sum(step_walls) if step_walls else None),
        "actual_authority_changed": False,
    })


def finalize_multifidelity(capture, accepted: bool):
    trace = capture._multifidelity
    if trace is None:
        return None
    result = _plain(trace)
    observed_steps = [row["step"] for row in result["rungs"]]
    if observed_steps != result["expected_rungs"]:
        result.update({
            "status": "INCOMPLETE",
            "final_retained": accepted,
            "review": None,
            "activation": {
                "status": "NOT_QUALIFIED",
                "reason": "INCOMPLETE_CURRENT_BAMF_SHADOW_TRACE",
                "authority_changed": False,
            },
        })
        return result
    from bilqis_mlx.learning.teacher_multifidelity import (
        DEFAULT_SHADOW_POLICY, evaluate_shadow, qualify_activation,
    )
    if (result["policy_version"] != DEFAULT_SHADOW_POLICY.version
            or result["minimum_target_delta_to_continue"]
            != DEFAULT_SHADOW_POLICY.minimum_target_delta_to_continue
            or result["minimum_decision_step"]
            != DEFAULT_SHADOW_POLICY.minimum_decision_step):
        _invalid("BAMF_MULTIFIDELITY_SHADOW_POLICY_DRIFT")
    probes = tuple(
        (row["step"], row["target_probe"]["target_correct_delta"])
        for row in result["rungs"])
    review = evaluate_shadow(
        DEFAULT_SHADOW_POLICY, probes=probes,
        final_retained=accepted, full_budget_steps=result["full_budget_steps"])
    first_stop = review["first_would_stop_step"]
    candidate_wall_saved = probe_wall_saved = 0.0
    wall_measured = True
    if first_stop is not None:
        for delivery in capture._steps:
            realized = delivery.get("controls", {}).get("realized_cost", {})
            ordinal = realized.get("candidate_optimizer_steps")
            if type(ordinal) is not int or ordinal < 1:
                ordinal = delivery["step"] - capture.proposal["parent_optimizer_step"]
            if ordinal <= first_stop:
                continue
            wall = realized.get("candidate_step_wall_seconds")
            if not isinstance(wall, (int, float)) or wall < 0:
                wall_measured = False
                break
            candidate_wall_saved += float(wall)
        if wall_measured:
            probe_wall_saved = sum(
                float(row["probe_wall_seconds"])
                for row in result["rungs"] if row["step"] > first_stop)
    review.update({
        "projected_candidate_wall_saved_seconds": (
            candidate_wall_saved if wall_measured else None),
        "projected_probe_wall_saved_seconds": (
            probe_wall_saved if wall_measured else None),
        "projected_wall_saved_seconds": (
            candidate_wall_saved + probe_wall_saved if wall_measured else None),
        "retained_would_kill": bool(review["false_kill"]),
        "retentions_per_hour_effect": {
            "status": "NOT_MEASURED",
            "reason": "REQUIRES_FRESH_CURRENT_BAMF_WINDOW_WITH_RETENTION_ECONOMICS",
        },
    })
    result.update({
        "status": "COMPLETE",
        "final_retained": accepted,
        "review": review,
        "activation": {
            **qualify_activation((review,)),
            "basis": "FRESH_CURRENT_BAMF_REVIEW_WINDOW",
        },
    })
    return result


__all__ = (
    "configure_multifidelity", "finalize_multifidelity",
    "record_multifidelity_rung",
)
