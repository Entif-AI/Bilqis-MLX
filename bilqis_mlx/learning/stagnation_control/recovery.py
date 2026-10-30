"""Recovery for the existing stagnation control contract."""
from __future__ import annotations

from copy import deepcopy
from .contracts import (
    MINIMUM_NO_PROGRESS_SECONDS, NON_TERMINAL_STAGNATION_GRADES, RECOVERY_PHASES, _validate, _validated_score,
)


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
    rehabilitation_capabilities = set(
        (updated.get("rehabilitation") or {}).get("capabilities", ()))
    for capability in sorted(candidates):
        if capability in rehabilitation_capabilities:
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
