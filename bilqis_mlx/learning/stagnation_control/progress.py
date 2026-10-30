"""Progress for the existing stagnation control contract."""
from __future__ import annotations

from copy import deepcopy
from .contracts import (
    RECOVERY_PHASES, _valid_checkpoint, _validate,
)


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
