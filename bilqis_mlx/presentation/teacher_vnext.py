"""Compact operator projection for Teacher vNext shadow evidence."""
from __future__ import annotations
from types import MappingProxyType


HEALTH_LABELS = MappingProxyType({
    "PRODUCTIVE": "PRODUCTIVE",
    "UNCERTAIN_EXPLORING": "EXPLORE",
    "LOW_YIELD": "LOW-YIELD",
    "SEARCH_NEIGHBORHOOD_EXHAUSTED": "EXHAUSTED",
})


def teacher_fields(event: dict) -> dict:
    fields = {}
    prediction = event.get("teacher_outcome_prediction_before")
    if isinstance(prediction, dict):
        probability = prediction.get("retention_probability")
        if isinstance(probability, (int, float)) and 0 <= probability <= 1:
            fields["p_ret"] = f"{probability * 100:.1f}%"
    health = event.get("teacher_health")
    if isinstance(health, dict) and health.get("status") in HEALTH_LABELS:
        fields["health"] = HEALTH_LABELS[health["status"]]
    shadow = event.get("teacher_multifidelity_shadow")
    if isinstance(shadow, dict):
        stop = shadow.get("first_would_stop_step")
        if type(stop) is int:
            fields["shadow"] = (
                f"KILL!@{stop}" if shadow.get("false_kill") else f"STOP@{stop}")
        elif shadow.get("would_continue_to_full_budget") is True:
            fields["shadow"] = "FULL"
    return fields


def health_transition(event: dict, previous_status) -> tuple[str | None, dict | None]:
    health = event.get("teacher_health")
    if not isinstance(health, dict):
        return previous_status, None
    status = health.get("status")
    if status not in HEALTH_LABELS or status == previous_status:
        return previous_status, None
    detail = HEALTH_LABELS[status]
    rate = health.get("retention_rate")
    steps = health.get("optimizer_steps_per_retention")
    brier = health.get("retention_brier_score")
    if isinstance(rate, (int, float)):
        detail += f" | retain {rate * 100:.1f}%"
    if isinstance(steps, (int, float)):
        detail += f" | {steps:.1f} steps/retain"
    if isinstance(brier, (int, float)):
        detail += f" | Brier {brier:.3f}"
    return status, {"kind": "TEACHER", "detail": detail}
