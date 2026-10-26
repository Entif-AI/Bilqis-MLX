"""Compact dashboard projection for current and historical teacher health."""
from __future__ import annotations

from types import MappingProxyType


HEALTH_LABELS = MappingProxyType({
    "PRODUCTIVE": "PRODUCTIVE",
    "UNCERTAIN_EXPLORING": "EXPLORE",
    "LOW_YIELD": "LOW-YIELD",
    "SEARCH_NEIGHBORHOOD_EXHAUSTED": "EXHAUSTED",
})
MINIMUM_SUPPORT = 8
EXHAUSTED_ZERO_RETENTION_VISITS = 16
LOW_YIELD_RETENTION_FRACTION = .10


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
    record = history.setdefault(
        (capability, phase, policy), {"trials": 0, "retained": 0})
    record["trials"] += 1
    record["retained"] += decision == "PROVISIONAL"
    trials, retained = record["trials"], record["retained"]
    rate = retained / trials
    if trials < MINIMUM_SUPPORT:
        status = "UNCERTAIN_EXPLORING"
    elif retained == 0 and trials >= EXHAUSTED_ZERO_RETENTION_VISITS:
        status = "SEARCH_NEIGHBORHOOD_EXHAUSTED"
    elif rate < LOW_YIELD_RETENTION_FRACTION:
        status = "LOW_YIELD"
    else:
        status = "PRODUCTIVE"
    return {"status": status, "retention_rate": rate,
            "attempted_candidates": trials, "retained_candidates": retained}


def teacher_fields(event: dict, history: dict | None = None) -> dict:
    health = event.get("teacher_policy_health")
    if not isinstance(health, dict):
        # Preserve readback of the original 349 Teacher vNext events.
        health = event.get("teacher_health")
    if not isinstance(health, dict) and history is not None:
        health = _derived_health(event, history)
    status = health.get("status") if isinstance(health, dict) else None
    return (
        {"health": HEALTH_LABELS[status]}
        if status in HEALTH_LABELS else {}
    )
