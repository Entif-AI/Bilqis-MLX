"""Scope for the existing stagnation control contract."""
from __future__ import annotations

from copy import deepcopy
from .contracts import (
    MINIMUM_NO_PROGRESS_SECONDS, SCHEMA, _valid_checkpoint, _validate, _validate_required_capabilities,
)


def start_session(*, session_id: str, generation: int,
                  required_capabilities: tuple[str, ...],
                  progress_checkpoint: dict | None = None) -> dict:
    if (not session_id or type(generation) is not int or generation < 0 or
            not required_capabilities or
            len(set(required_capabilities)) != len(required_capabilities) or
            (progress_checkpoint is not None and
             not _valid_checkpoint(progress_checkpoint))):
        raise ValueError("STAGNATION_SESSION_INVALID_START")
    return {
        "schema": SCHEMA,
        "session_id": session_id,
        "started_generation": generation,
        "required_capabilities": list(required_capabilities),
        "cycle_index": 0,
        "cycle_first_recovery": [],
        "cycle_visits": {},
        "quarantined": {},
        "alerts": [],
        "score_peaks": {},
        "last_progress_elapsed_seconds": {},
        "minimum_no_progress_seconds": MINIMUM_NO_PROGRESS_SECONDS,
        "progress_checkpoint": deepcopy(progress_checkpoint),
    }


def reconcile_required_scope(
        control: dict, *, required_capabilities: tuple[str, ...],
        generation: int) -> tuple[dict, dict | None]:
    """Rebase one command-local controller when the scheduler changes scope."""
    _validate(control)
    _validate_required_capabilities(required_capabilities)
    if type(generation) is not int or generation < 0:
        raise ValueError("STAGNATION_SCOPE_RECONCILIATION_INVALID_GENERATION")
    previous = tuple(control["required_capabilities"])
    if previous == required_capabilities:
        return deepcopy(control), None

    previous_set = set(previous)
    required_set = set(required_capabilities)
    updated = deepcopy(control)
    previous_cycle_index = updated["cycle_index"]
    updated["required_capabilities"] = list(required_capabilities)
    updated["cycle_index"] = 0
    updated["cycle_first_recovery"] = []
    updated["cycle_visits"] = {}

    removed_quarantined = sorted(set(updated["quarantined"]) - required_set)
    updated["quarantined"] = {
        capability: evidence
        for capability, evidence in updated["quarantined"].items()
        if capability in required_set
    }
    removed_alerts = sorted({
        alert.get("capability") for alert in updated["alerts"]
        if alert.get("capability") not in required_set
    } - {None})
    updated["alerts"] = [
        alert for alert in updated["alerts"]
        if alert.get("capability") in required_set
    ]
    rehabilitation = updated.get("rehabilitation")
    rehabilitation_cleared = bool(
        rehabilitation and
        not set(rehabilitation.get("capabilities", ())) <= required_set)
    if rehabilitation_cleared:
        updated.pop("rehabilitation", None)

    return updated, {
        "event": "SCHOOL_STAGNATION_SCOPE_RECONCILED",
        "generation": generation,
        "session_id": control["session_id"],
        "previous_required_capabilities": list(previous),
        "required_capabilities": list(required_capabilities),
        "added_capabilities": sorted(required_set - previous_set),
        "removed_capabilities": sorted(previous_set - required_set),
        "retained_quarantined": sorted(updated["quarantined"]),
        "removed_quarantined": removed_quarantined,
        "removed_alert_capabilities": removed_alerts,
        "rehabilitation_cleared": rehabilitation_cleared,
        "previous_cycle_index": previous_cycle_index,
        "cycle_index": 0,
        "cycle_evidence_reset": True,
        "actual_neural_updates": 0,
        "model_and_own_adamw_unchanged": True,
    }


def quarantined_capabilities(control: dict | None) -> tuple[str, ...]:
    if control is None:
        return ()
    _validate(control)
    return tuple(sorted(control["quarantined"]))


def activate_sole_grade_rehabilitation(
        control: dict, *, capabilities: tuple[str, ...],
        generation: int) -> tuple[dict, dict]:
    """Release one sole remaining grade from containment for active remediation."""
    _validate(control)
    if (not capabilities or len(set(capabilities)) != len(capabilities) or
            any(not isinstance(capability, str) or not capability
                for capability in capabilities) or
            type(generation) is not int or generation < 0):
        raise ValueError("STAGNATION_REHABILITATION_INVALID_START")
    required = set(control["required_capabilities"])
    if not set(capabilities) <= required:
        raise ValueError("STAGNATION_REHABILITATION_OUTSIDE_REQUIRED_SCOPE")
    grades = {capability.partition(".")[0] for capability in capabilities}
    if len(grades) != 1:
        raise ValueError("STAGNATION_REHABILITATION_REQUIRES_SOLE_GRADE")
    grade = next(iter(grades))

    updated = deepcopy(control)
    rehabilitated = set(capabilities)
    for capability in capabilities:
        updated["quarantined"].pop(capability, None)
    for alert in updated["alerts"]:
        if (alert.get("capability") in rehabilitated and
                alert.get("action") == "WITHHELD_FOR_REMAINDER_OF_SESSION"):
            alert["action"] = "RELEASED_FOR_SOLE_GRADE_REHABILITATION"
            alert["resolution_generation"] = generation
            alert["resolution_reason"] = "SOLE_REMAINING_GRADE_MASTERY_DEBT"
    updated["rehabilitation"] = {
        "grade": grade,
        "capabilities": list(capabilities),
        "started_generation": generation,
        "reason": "SOLE_REMAINING_GRADE_MASTERY_DEBT",
    }
    updated["cycle_first_recovery"] = []
    updated["cycle_visits"] = {}
    return updated, {
        "event": "SCHOOL_STAGNATION_REHABILITATION_STARTED",
        "generation": generation,
        "grade": grade,
        "capabilities": list(capabilities),
        "reason": "SOLE_REMAINING_GRADE_MASTERY_DEBT",
        "quarantine_override": True,
        "required_mastery_debt": True,
    }
