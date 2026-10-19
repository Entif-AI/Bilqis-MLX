"""Per-human-command containment for capabilities that consume two failed recovery rounds.

This control deliberately reuses the school's already-authorized cadence rather
than inventing a new numeric z-score or loss threshold.  A capability is
temporarily withheld only after it remains in the relative weakest tail across
the existing two recovery rounds *and* both of its recovery teaching attempts
retain zero optimizer updates.  The capability remains required mastery debt.
"""
from __future__ import annotations

from copy import deepcopy


SCHEMA = "bilqis.mlx.stagnation-session/v1"
GRACE_SCHEMA = "bilqis.mlx.stagnation-grace/v1"
RECOVERY_PHASES = ("RECOVERY_1", "RECOVERY_2")


def _validate_grace(grace: dict | None) -> None:
    if grace is None:
        return
    if (not isinstance(grace, dict) or grace.get("schema") != GRACE_SCHEMA or
            not isinstance(grace.get("grade"), str) or not grace["grade"] or
            type(grace.get("started_optimizer_step")) is not int or
            grace["started_optimizer_step"] < 0 or
            type(grace.get("optimizer_step_budget")) is not int or
            grace["optimizer_step_budget"] <= 0 or
            type(grace.get("until_optimizer_step")) is not int or
            grace["until_optimizer_step"] !=
            grace["started_optimizer_step"] + grace["optimizer_step_budget"]):
        raise ValueError("STAGNATION_GRACE_STATE_DRIFT")


def _require_optimizer_step(optimizer_step: int) -> None:
    if type(optimizer_step) is not int or optimizer_step < 0:
        raise ValueError("STAGNATION_GRACE_INVALID_OPTIMIZER_STEP")


def create_optimizer_step_grace(*, grade: str, optimizer_step: int,
                                optimizer_steps: int) -> dict:
    """Create one absolute optimizer-step quarantine grace lease."""
    if (not isinstance(grade, str) or not grade or
            type(optimizer_step) is not int or optimizer_step < 0 or
            type(optimizer_steps) is not int or optimizer_steps <= 0):
        raise ValueError("STAGNATION_GRACE_INVALID_START")
    return {
        "schema": GRACE_SCHEMA,
        "grade": grade,
        "started_optimizer_step": optimizer_step,
        "optimizer_step_budget": optimizer_steps,
        "until_optimizer_step": optimizer_step + optimizer_steps,
        "reason": "HUMAN_AUTHORIZED_DEEP_REHABILITATION",
    }


def reconcile_optimizer_step_grace(
        existing: dict | None, *, requested_grade: str | None,
        requested_steps: int, optimizer_step: int) -> tuple[dict | None, bool]:
    """Persist an existing lease or explicitly create/renew one without drift."""
    _validate_grace(existing)
    _require_optimizer_step(optimizer_step)
    requested = requested_grade is not None or requested_steps != 0
    if not requested:
        return deepcopy(existing), False
    if (not isinstance(requested_grade, str) or not requested_grade or
            type(requested_steps) is not int or requested_steps <= 0):
        raise ValueError("STAGNATION_GRACE_INVALID_REQUEST")
    if existing is not None and optimizer_step < existing["until_optimizer_step"]:
        if (requested_grade != existing["grade"] or
                requested_steps != existing["optimizer_step_budget"]):
            raise ValueError("STAGNATION_GRACE_ACTIVE_CHANGE_FORBIDDEN")
        return deepcopy(existing), False
    return create_optimizer_step_grace(
        grade=requested_grade, optimizer_step=optimizer_step,
        optimizer_steps=requested_steps), True


def grace_suppressed_capabilities(
        grace: dict | None, *, required_capabilities: tuple[str, ...],
        optimizer_step: int) -> tuple[str, ...]:
    """Return capabilities whose quarantine actuator is disabled right now."""
    _validate_grace(grace)
    _require_optimizer_step(optimizer_step)
    if grace is None or optimizer_step >= grace["until_optimizer_step"]:
        return ()
    if (len(set(required_capabilities)) != len(required_capabilities) or
            any(not isinstance(capability, str) or not capability
                for capability in required_capabilities)):
        raise ValueError("STAGNATION_GRACE_REQUIRED_SCOPE_INVALID")
    prefix = grace["grade"] + "."
    return tuple(sorted(
        capability for capability in required_capabilities
        if capability.startswith(prefix)))


def start_session(*, session_id: str, generation: int,
                  required_capabilities: tuple[str, ...]) -> dict:
    if (not session_id or type(generation) is not int or generation < 0 or
            not required_capabilities or
            len(set(required_capabilities)) != len(required_capabilities)):
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
    }


def _validate(control: dict) -> None:
    if (not isinstance(control, dict) or control.get("schema") != SCHEMA or
            not isinstance(control.get("session_id"), str) or
            type(control.get("cycle_index")) is not int or
            not isinstance(control.get("cycle_visits"), dict) or
            not isinstance(control.get("quarantined"), dict) or
            not isinstance(control.get("alerts"), list)):
        raise ValueError("STAGNATION_SESSION_STATE_DRIFT")
    rehabilitation = control.get("rehabilitation")
    if rehabilitation is not None and (
            not isinstance(rehabilitation, dict) or
            not isinstance(rehabilitation.get("grade"), str) or
            not rehabilitation["grade"] or
            not isinstance(rehabilitation.get("capabilities"), list) or
            not rehabilitation["capabilities"] or
            len(set(rehabilitation["capabilities"])) !=
            len(rehabilitation["capabilities"]) or
            type(rehabilitation.get("started_generation")) is not int):
        raise ValueError("STAGNATION_REHABILITATION_STATE_DRIFT")


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


def record_visit(control: dict, *, capability: str, phase: str,
                 decision: str | None, retained_optimizer_updates: int,
                 generation: int) -> dict:
    """Record one actual teaching attempt without changing the learned teacher."""
    _validate(control)
    if (not capability or phase not in ("MAIN", *RECOVERY_PHASES) or
            type(retained_optimizer_updates) is not int or
            retained_optimizer_updates < 0 or type(generation) is not int):
        raise ValueError("STAGNATION_VISIT_RECEIPT_INVALID")
    updated = deepcopy(control)
    capability_visits = updated["cycle_visits"].setdefault(capability, {})
    receipt = capability_visits.setdefault(
        phase, {"attempts": 0, "rejected": 0, "retained_updates": 0,
                "last_generation": generation})
    receipt["attempts"] += 1
    receipt["retained_updates"] += retained_optimizer_updates
    receipt["last_generation"] = generation
    if decision == "REJECT" and retained_optimizer_updates == 0:
        receipt["rejected"] += 1
    return updated


def begin_recovery_cycle(control: dict, *, first_recovery: tuple[str, ...]) -> dict:
    """Start the two-round tail check after one fresh MAIN assessment."""
    _validate(control)
    if len(set(first_recovery)) != len(first_recovery):
        raise ValueError("STAGNATION_FIRST_RECOVERY_DUPLICATE")
    updated = deepcopy(control)
    updated["cycle_index"] += 1
    updated["cycle_first_recovery"] = list(first_recovery)
    updated["cycle_visits"] = {}
    return updated


def _rejected_without_retention(control: dict, capability: str, phase: str) -> bool:
    item = control["cycle_visits"].get(capability, {}).get(phase)
    return bool(item and item["rejected"] >= 1 and item["retained_updates"] == 0)


def complete_recovery_cycle(control: dict, *, weakest_tail: tuple[str, ...],
                            scores: dict[str, dict], generation: int,
                            active_warnings: tuple[dict, ...] = (),
                            quarantine_suppressed: tuple[str, ...] = ()) -> tuple[dict, tuple[dict, ...]]:
    """Contain only repeated tail failures already proven by both recovery rounds.

    `weakest_tail` is the scheduler's source-scored weakest-three result on the
    latest fresh routine examination.  No raw score from a different cohort is
    compared to another, and no new numeric cutoff is introduced here.
    """
    _validate(control)
    if (len(set(weakest_tail)) != len(weakest_tail) or
            type(generation) is not int or generation < 0):
        raise ValueError("STAGNATION_RECOVERY_RECEIPT_INVALID")
    if (len(set(quarantine_suppressed)) != len(quarantine_suppressed) or
            not set(quarantine_suppressed) <= set(control["required_capabilities"])):
        raise ValueError("STAGNATION_GRACE_SUPPRESSION_SCOPE_INVALID")
    updated = deepcopy(control)
    warning_by_capability: dict[str, list[str]] = {}
    for warning in active_warnings:
        if not isinstance(warning, dict):
            continue
        capability = warning.get("capability")
        signal = warning.get("signal")
        if isinstance(capability, str) and isinstance(signal, str):
            warning_by_capability.setdefault(capability, []).append(signal)
    candidates = set(updated["cycle_first_recovery"]) & set(weakest_tail)
    events = []
    rehabilitation_capabilities = set(
        (updated.get("rehabilitation") or {}).get("capabilities", ()))
    for capability in sorted(candidates):
        if capability in rehabilitation_capabilities:
            continue
        if capability in updated["quarantined"]:
            continue
        score = scores.get(capability)
        if (not isinstance(score, dict) or type(score.get("correct")) is not int or
                type(score.get("total")) is not int or
                score["correct"] == score["total"]):
            continue
        if not all(_rejected_without_retention(updated, capability, phase)
                   for phase in RECOVERY_PHASES):
            continue
        evidence = {
            "capability": capability,
            "cycle_index": updated["cycle_index"],
            "trigger_generation": generation,
            "latest_score": dict(score),
            "first_recovery": list(updated["cycle_first_recovery"]),
            "latest_weakest_tail": list(weakest_tail),
            "recovery_visits": deepcopy(updated["cycle_visits"].get(capability, {})),
            "active_warning_signals": sorted(set(warning_by_capability.get(capability, ()))),
            "reason": "REPEATED_WEAKEST_TAIL_WITH_TWO_REJECTED_RECOVERY_VISITS",
        }
        if capability in set(quarantine_suppressed):
            events.append({
                "event": "SCHOOL_CAPABILITY_STAGNATION_QUARANTINE_SUPPRESSED",
                **evidence,
                "required_mastery_debt": True,
                "would_quarantine": True,
                "diagnostic_only": True,
                "quarantine_suppressed": True,
            })
            continue
        updated["quarantined"][capability] = evidence
        alert = {
            "capability": capability,
            "delivery": "END_OF_RUN_REVIEW",
            "action": "WITHHELD_FOR_REMAINDER_OF_SESSION",
            "reason": evidence["reason"],
            "trigger_generation": generation,
            "required_mastery_debt": True,
        }
        updated["alerts"].append(alert)
        events.append({
            "event": "SCHOOL_CAPABILITY_STAGNATION_QUARANTINED",
            **evidence,
            "required_mastery_debt": True,
            "teacher_updates_after_trigger": 0,
        })
    return updated, tuple(events)


def end_of_run_alerts(control: dict | None) -> tuple[dict, ...]:
    if control is None:
        return ()
    _validate(control)
    return tuple(deepcopy(control["alerts"]))
