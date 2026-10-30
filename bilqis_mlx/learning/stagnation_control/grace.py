"""Grace for the existing stagnation control contract."""
from __future__ import annotations

from copy import deepcopy
from .contracts import (
    GRACE_SCHEMA, _require_optimizer_step, _validate_grace,
)


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
