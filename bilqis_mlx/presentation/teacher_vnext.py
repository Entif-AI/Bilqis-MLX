"""Compact dashboard projection for current and historical teacher health."""
from __future__ import annotations

from types import MappingProxyType


HEALTH_LABELS = MappingProxyType({
    "PRODUCTIVE": "PRODUCTIVE",
    "UNCERTAIN_EXPLORING": "UNCERTAIN",
    "LOW_YIELD": "LOW-YIELD",
    "SEARCH_NEIGHBORHOOD_EXHAUSTED": "EXHAUSTED",
})
MINIMUM_SUPPORT = 8
LOW_YIELD_RETENTION_FRACTION = .10
PREDICTION_MINIMUM_SUPPORT = 8


def _record(history: dict, key) -> dict:
    return history.setdefault(key, {"trials": 0, "retained": 0})


def _prediction_before(event: dict, history: dict) -> float:
    explicit = event.get("teacher_outcome_prediction_before")
    if isinstance(explicit, dict):
        probability = explicit.get("retention_probability")
        if isinstance(probability, (int, float)) and 0 <= probability <= 1:
            return float(probability)
    retention = event.get("candidate_retention")
    capability = event.get("capability")
    policy = event.get("teacher_policy")
    if not isinstance(retention, dict):
        return .5
    phase = retention.get("phase")
    grade = event.get("grade") or (
        capability.partition(".")[0] if isinstance(capability, str) else None)
    keys = (
        ("exact", capability, phase, policy),
        ("capability", capability, policy),
        ("grade_phase", grade, phase, policy),
        ("grade", grade, policy),
    )
    for key in keys:
        row = history.get(key)
        if isinstance(row, dict) and row.get("trials", 0) >= PREDICTION_MINIMUM_SUPPORT:
            return row.get("retained", 0) / row["trials"]
    return .5


def _derived_health(event: dict, history: dict) -> dict | None:
    retention = event.get("candidate_retention")
    capability = event.get("capability")
    policy = event.get("teacher_policy")
    if not isinstance(retention, dict):
        return None
    phase = retention.get("phase")
    decision = retention.get("decision")
    if (not all(isinstance(value, str) and value
                for value in (capability, policy, phase)) or
            decision not in ("PROVISIONAL", "REJECT")):
        return None
    grade = event.get("grade") or capability.partition(".")[0]
    keys = (
        ("exact", capability, phase, policy),
        ("capability", capability, policy),
        ("grade_phase", grade, phase, policy),
        ("grade", grade, policy),
    )
    for key in keys:
        row = _record(history, key)
        row["trials"] += 1
        row["retained"] += decision == "PROVISIONAL"
    record = history[keys[0]]
    trials, retained = record["trials"], record["retained"]
    rate = retained / trials
    if trials < MINIMUM_SUPPORT:
        status = "UNCERTAIN_EXPLORING"
    elif rate < LOW_YIELD_RETENTION_FRACTION:
        status = "LOW_YIELD"
    else:
        status = "PRODUCTIVE"
    return {"status": status, "retention_rate": rate,
            "attempted_candidates": trials, "retained_candidates": retained}


def teacher_fields(event: dict, history: dict | None = None) -> dict:
    fields = {}
    if history is not None:
        fields["p_ret"] = f"{_prediction_before(event, history) * 100:.1f}%"
    else:
        explicit = event.get("teacher_outcome_prediction_before")
        if isinstance(explicit, dict):
            probability = explicit.get("retention_probability")
            if isinstance(probability, (int, float)) and 0 <= probability <= 1:
                fields["p_ret"] = f"{probability * 100:.1f}%"
    health = event.get("teacher_policy_health")
    if not isinstance(health, dict):
        # Preserve readback of the original 349 Teacher vNext events.
        health = event.get("teacher_health")
    if not isinstance(health, dict) and history is not None:
        health = _derived_health(event, history)
    status = health.get("status") if isinstance(health, dict) else None
    if status in HEALTH_LABELS:
        fields["health"] = HEALTH_LABELS[status]
    if event.get("teacher_selection_reason") == "FRESH_MUTATED_CHALLENGER":
        fields["health"] = "EXPLORE"
    return fields
