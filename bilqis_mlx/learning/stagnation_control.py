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
# Grade B is developmental learning territory: it may be scored as unfinished
# mastery debt and repeatedly taught, but it never actuates run containment.
NON_TERMINAL_STAGNATION_GRADES = frozenset(("B",))
MINIMUM_NO_PROGRESS_SECONDS = 20 * 60
BOUNDED_REPROBE_COOLDOWN_CYCLES = 1
BOUNDED_REPROBE_MODE = "BOUNDED_REPROBE"
BOUNDED_REPROBE_GRADE_INVALID = "STAGNATION_BOUNDED_REPROBE_GRADE_INVALID"
BOUNDED_REPROBE_INVALID_START = "STAGNATION_BOUNDED_REPROBE_INVALID_START"
BOUNDED_REPROBE_REQUIRES_ONE_GRADE = (
    "STAGNATION_BOUNDED_REPROBE_REQUIRES_ONE_GRADE")


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


def _valid_checkpoint(pointer: dict | None) -> bool:
    return bool(
        isinstance(pointer, dict) and
        isinstance(pointer.get("filename"), str) and pointer["filename"] and
        isinstance(pointer.get("sha256"), str) and len(pointer["sha256"]) == 64 and
        type(pointer.get("optimizer_step")) is int and pointer["optimizer_step"] >= 0 and
        pointer.get("model_and_native_adamw") is True)


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


def _validate(control: dict) -> None:
    if (not isinstance(control, dict) or control.get("schema") != SCHEMA or
            not isinstance(control.get("session_id"), str) or
            type(control.get("cycle_index")) is not int or
            not isinstance(control.get("required_capabilities"), list) or
            not control["required_capabilities"] or
            len(set(control["required_capabilities"])) !=
            len(control["required_capabilities"]) or
            any(not isinstance(capability, str) or not capability
                for capability in control["required_capabilities"]) or
            not isinstance(control.get("cycle_visits"), dict) or
            not isinstance(control.get("quarantined"), dict) or
            not isinstance(control.get("alerts"), list) or
            not isinstance(control.get("score_peaks", {}), dict) or
            not isinstance(control.get("last_progress_elapsed_seconds", {}), dict) or
            (control.get("progress_checkpoint") is not None and
             not _valid_checkpoint(control.get("progress_checkpoint"))) or
            type(control.get("minimum_no_progress_seconds",
                             MINIMUM_NO_PROGRESS_SECONDS)) is not int or
            control.get("minimum_no_progress_seconds",
                        MINIMUM_NO_PROGRESS_SECONDS) <= 0):
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


def _validate_required_capabilities(required_capabilities: tuple[str, ...]) -> None:
    if (not required_capabilities or
            len(set(required_capabilities)) != len(required_capabilities) or
            any(not isinstance(capability, str) or not capability
                for capability in required_capabilities)):
        raise ValueError("STAGNATION_REQUIRED_SCOPE_INVALID")


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
                alert.get("action") in {
                    "WITHHELD_FOR_REMAINDER_OF_SESSION",
                    "WITHHELD_UNTIL_BOUNDED_REPROBE",
                }):
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


def bounded_reprobe_due(control: dict, *, grade: str) -> tuple[str, ...]:
    """Return current-grade quarantined debt after one full recovery-cycle cooldown."""
    _validate(control)
    if not isinstance(grade, str) or not grade:
        raise ValueError(BOUNDED_REPROBE_GRADE_INVALID)
    if control.get("rehabilitation") is not None:
        return ()
    current_cycle = control["cycle_index"]
    prefix = grade + "."
    due = []
    for capability, evidence in control["quarantined"].items():
        if not capability.startswith(prefix) or not isinstance(evidence, dict):
            continue
        trigger_cycle = evidence.get("cycle_index")
        if (type(trigger_cycle) is int and
                current_cycle - trigger_cycle > BOUNDED_REPROBE_COOLDOWN_CYCLES):
            due.append(capability)
    return tuple(sorted(due))


def activate_bounded_reprobe(
        control: dict, *, capabilities: tuple[str, ...],
        generation: int) -> tuple[dict, dict]:
    """Release quarantined debt for one ordinary recovery cycle, then re-evaluate it."""
    _validate(control)
    if (not capabilities or len(set(capabilities)) != len(capabilities) or
            any(not isinstance(capability, str) or not capability
                for capability in capabilities) or
            type(generation) is not int or generation < 0 or
            control.get("rehabilitation") is not None or
            not set(capabilities) <= set(control["quarantined"])):
        raise ValueError(BOUNDED_REPROBE_INVALID_START)
    grades = {capability.partition(".")[0] for capability in capabilities}
    if len(grades) != 1:
        raise ValueError(BOUNDED_REPROBE_REQUIRES_ONE_GRADE)
    updated = deepcopy(control)
    released = set(capabilities)
    for capability in capabilities:
        updated["quarantined"].pop(capability, None)
    for alert in updated["alerts"]:
        if (alert.get("capability") in released and
                alert.get("action") in {
                    "WITHHELD_FOR_REMAINDER_OF_SESSION",
                    "WITHHELD_UNTIL_BOUNDED_REPROBE",
                }):
            alert["action"] = "RELEASED_FOR_BOUNDED_REPROBE"
            alert["resolution_generation"] = generation
            alert["resolution_reason"] = "BOUNDED_RECOVERY_CYCLE_REPROBE"
    grade = next(iter(grades))
    updated["rehabilitation"] = {
        "mode": BOUNDED_REPROBE_MODE,
        "grade": grade,
        "capabilities": list(capabilities),
        "started_generation": generation,
        "started_cycle_index": updated["cycle_index"],
        "reason": "BOUNDED_RECOVERY_CYCLE_REPROBE",
    }
    return updated, {
        "event": "SCHOOL_STAGNATION_BOUNDED_REPROBE_STARTED",
        "generation": generation,
        "grade": grade,
        "capabilities": list(capabilities),
        "cycle_index": updated["cycle_index"],
        "cooldown_cycles": BOUNDED_REPROBE_COOLDOWN_CYCLES,
        "required_mastery_debt": True,
        "quarantine_override": True,
    }


def record_visit(control: dict, *, capability: str, phase: str,
                 decision: str | None, retained_optimizer_updates: int,
                 generation: int) -> dict:
    """Record one actual teaching attempt without changing the learned teacher."""
    _validate(control)
    if (not capability or phase not in ("MAIN", "PROMOTION_SWEEP", *RECOVERY_PHASES) or
            type(retained_optimizer_updates) is not int or
            retained_optimizer_updates < 0 or type(generation) is not int):
        raise ValueError("STAGNATION_VISIT_RECEIPT_INVALID")
    if capability not in set(control["required_capabilities"]):
        raise ValueError("STAGNATION_VISIT_OUTSIDE_REQUIRED_SCOPE")
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


def _validated_score(score: dict) -> dict:
    if (not isinstance(score, dict) or
            type(score.get("correct")) is not int or
            type(score.get("total")) is not int or
            score["total"] <= 0 or
            not 0 <= score["correct"] <= score["total"]):
        raise ValueError("STAGNATION_SCORE_OBSERVATION_INVALID")
    return {"correct": score["correct"], "total": score["total"]}


def observe_paired_progress(
        control: dict, *, measured_capabilities: tuple[str, ...],
        improved_capabilities: tuple[str, ...], measurement_usable: bool,
        elapsed_seconds: float, progress_checkpoint: dict) -> dict:
    """Advance the no-progress clock only from same-cohort checkpoint evidence.

    Routine cohorts intentionally redraw at every assessment boundary, so raw
    scores from two different cohorts are not longitudinal evidence.  The
    trainer instead scores the previous assessment checkpoint and current
    checkpoint on the *same fresh cohort*.  A strict current>previous result
    resets only that capability's clock.  If the paired comparison is
    unavailable, the unknown interval cannot prove stagnation and therefore
    resets the measured capabilities' clocks conservatively.
    """
    _validate(control)
    required = set(control["required_capabilities"])
    measured = set(measured_capabilities)
    improved = set(improved_capabilities)
    if (type(measurement_usable) is not bool or
            not measured_capabilities or
            len(measured) != len(measured_capabilities) or
            len(improved) != len(improved_capabilities) or
            not measured <= required or not improved <= measured or
            not _valid_checkpoint(progress_checkpoint) or
            not isinstance(elapsed_seconds, (int, float)) or
            elapsed_seconds < 0):
        raise ValueError("STAGNATION_PAIRED_PROGRESS_INVALID")
    updated = deepcopy(control)
    progress = updated.setdefault("last_progress_elapsed_seconds", {})
    resets = improved if measurement_usable else measured
    for capability in resets:
        progress[capability] = float(elapsed_seconds)
    updated["progress_checkpoint"] = deepcopy(progress_checkpoint)
    updated["last_paired_progress_observation"] = {
        "elapsed_seconds": float(elapsed_seconds),
        "measurement_usable": measurement_usable,
        "measured_capabilities": sorted(measured),
        "improved_capabilities": sorted(improved) if measurement_usable else [],
    }
    return updated


def begin_recovery_cycle(control: dict, *, first_recovery: tuple[str, ...]) -> dict:
    """Start the two-round tail check after one fresh MAIN assessment."""
    _validate(control)
    if len(set(first_recovery)) != len(first_recovery):
        raise ValueError("STAGNATION_FIRST_RECOVERY_DUPLICATE")
    if not set(first_recovery) <= set(control["required_capabilities"]):
        raise ValueError("STAGNATION_RECOVERY_OUTSIDE_REQUIRED_SCOPE")
    updated = deepcopy(control)
    updated["cycle_index"] += 1
    updated["cycle_first_recovery"] = list(first_recovery)
    updated["cycle_visits"] = {}
    return updated


def _rejected_without_retention(control: dict, capability: str, phase: str) -> bool:
    item = control["cycle_visits"].get(capability, {}).get(phase)
    return bool(item and item["rejected"] >= 1 and item["retained_updates"] == 0)


def _warning_signals(active_warnings: tuple[dict, ...]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for warning in active_warnings:
        if not isinstance(warning, dict):
            continue
        capability = warning.get("capability")
        signal = warning.get("signal")
        if isinstance(capability, str) and isinstance(signal, str):
            result.setdefault(capability, []).append(signal)
    return result


def _stagnation_evidence(control: dict, *, capability: str, score: dict,
                         weakest_tail: tuple[str, ...], generation: int,
                         warning_by_capability: dict[str, list[str]],
                         elapsed_seconds: float) -> dict | None:
    if score["correct"] == score["total"]:
        return None
    if not all(_rejected_without_retention(control, capability, phase)
               for phase in RECOVERY_PHASES):
        return None
    minimum = control.get(
        "minimum_no_progress_seconds", MINIMUM_NO_PROGRESS_SECONDS)
    last_progress = control.get(
        "last_progress_elapsed_seconds", {}).get(capability, 0.0)
    stagnant_seconds = elapsed_seconds - last_progress
    if stagnant_seconds < minimum:
        return None
    return {
        "capability": capability,
        "cycle_index": control["cycle_index"],
        "trigger_generation": generation,
        "latest_score": dict(score),
        "first_recovery": list(control["cycle_first_recovery"]),
        "latest_weakest_tail": list(weakest_tail),
        "recovery_visits": deepcopy(control["cycle_visits"].get(capability, {})),
        "active_warning_signals": sorted(set(warning_by_capability.get(capability, ()))),
        "last_progress_elapsed_seconds": last_progress,
        "stagnant_seconds": stagnant_seconds,
        "minimum_no_progress_seconds": minimum,
        "reason": "SUSTAINED_NO_PROGRESS_AFTER_REPEATED_RECOVERY_FAILURE",
    }


def _finish_bounded_reprobe(control: dict, rehabilitation: dict,
                            generation: int, events: list[dict]):
    if rehabilitation.get("mode") != BOUNDED_REPROBE_MODE:
        return control, events
    updated = deepcopy(control)
    reprobe = set(rehabilitation.get("capabilities", ()))
    requarantined = tuple(sorted(reprobe & set(updated["quarantined"])))
    released = tuple(sorted(reprobe - set(updated["quarantined"])))
    updated.pop("rehabilitation", None)
    events.append({
        "event": "SCHOOL_STAGNATION_BOUNDED_REPROBE_COMPLETED",
        "generation": generation,
        "grade": rehabilitation["grade"],
        "capabilities": sorted(reprobe),
        "released_capabilities": list(released),
        "requarantined_capabilities": list(requarantined),
        "required_mastery_debt": bool(requarantined),
    })
    return updated, events


def complete_recovery_cycle(control: dict, *, weakest_tail: tuple[str, ...],
                            scores: dict[str, dict], generation: int,
                            active_warnings: tuple[dict, ...] = (),
                            quarantine_suppressed: tuple[str, ...] = (),
                            elapsed_seconds: float = float("inf")) -> tuple[dict, tuple[dict, ...]]:
    """Contain only repeated tail failures already proven by both recovery rounds.

    `weakest_tail` is the scheduler's source-scored weakest-three result on the
    latest fresh routine examination.  No raw score from a different cohort is
    compared to another, and no new numeric cutoff is introduced here.
    """
    _validate(control)
    if (len(set(weakest_tail)) != len(weakest_tail) or
            type(generation) is not int or generation < 0):
        raise ValueError("STAGNATION_RECOVERY_RECEIPT_INVALID")
    if not set(weakest_tail) <= set(control["required_capabilities"]):
        raise ValueError("STAGNATION_RECOVERY_OUTSIDE_REQUIRED_SCOPE")
    if (len(set(quarantine_suppressed)) != len(quarantine_suppressed) or
            not set(quarantine_suppressed) <= set(control["required_capabilities"])):
        raise ValueError("STAGNATION_GRACE_SUPPRESSION_SCOPE_INVALID")
    if (not isinstance(elapsed_seconds, (int, float)) or
            elapsed_seconds < 0):
        raise ValueError("STAGNATION_RECOVERY_ELAPSED_INVALID")
    updated = deepcopy(control)
    warning_by_capability = _warning_signals(active_warnings)
    candidates = set(updated["cycle_first_recovery"]) & set(weakest_tail)
    events = []
    rehabilitation = updated.get("rehabilitation") or {}
    rehabilitation_capabilities = set(rehabilitation.get("capabilities", ()))
    bounded_reprobe = rehabilitation.get("mode") == BOUNDED_REPROBE_MODE
    for capability in sorted(candidates):
        if capability in rehabilitation_capabilities and not bounded_reprobe:
            continue
        if capability in updated["quarantined"]:
            continue
        raw_score = scores.get(capability)
        if not isinstance(raw_score, dict):
            continue
        score = _validated_score(raw_score)
        evidence = _stagnation_evidence(
            updated, capability=capability, score=score,
            weakest_tail=weakest_tail, generation=generation,
            warning_by_capability=warning_by_capability,
            elapsed_seconds=elapsed_seconds)
        if evidence is None:
            continue
        developmental = (
            capability.partition(".")[0] in NON_TERMINAL_STAGNATION_GRADES)
        if developmental or capability in set(quarantine_suppressed):
            events.append({
                "event": "SCHOOL_CAPABILITY_STAGNATION_QUARANTINE_SUPPRESSED",
                **evidence,
                "required_mastery_debt": True,
                "would_quarantine": True,
                "diagnostic_only": True,
                "quarantine_suppressed": True,
                **({"suppression_reason": "GRADE_B_DEVELOPMENTAL_LEARNING"}
                   if developmental else {}),
            })
            continue
        updated["quarantined"][capability] = evidence
        alert = {
            "capability": capability,
            "delivery": "END_OF_RUN_REVIEW",
            "action": "WITHHELD_UNTIL_BOUNDED_REPROBE",
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
    updated, events = _finish_bounded_reprobe(
        updated, rehabilitation, generation, events)
    return updated, tuple(events)


def end_of_run_alerts(control: dict | None) -> tuple[dict, ...]:
    if control is None:
        return ()
    _validate(control)
    return tuple(deepcopy(control["alerts"]))
