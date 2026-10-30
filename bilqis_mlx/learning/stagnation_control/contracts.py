"""Contracts for the existing stagnation control contract."""
from __future__ import annotations



SCHEMA = "bilqis.mlx.stagnation-session/v1"


GRACE_SCHEMA = "bilqis.mlx.stagnation-grace/v1"


RECOVERY_PHASES = ("RECOVERY_1", "RECOVERY_2")


NON_TERMINAL_STAGNATION_GRADES = frozenset(("B",))


MINIMUM_NO_PROGRESS_SECONDS = 20 * 60


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


def _valid_checkpoint(pointer: dict | None) -> bool:
    return bool(
        isinstance(pointer, dict) and
        isinstance(pointer.get("filename"), str) and pointer["filename"] and
        isinstance(pointer.get("sha256"), str) and len(pointer["sha256"]) == 64 and
        type(pointer.get("optimizer_step")) is int and pointer["optimizer_step"] >= 0 and
        pointer.get("model_and_native_adamw") is True)


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


def _validated_score(score: dict) -> dict:
    if (not isinstance(score, dict) or
            type(score.get("correct")) is not int or
            type(score.get("total")) is not int or
            score["total"] <= 0 or
            not 0 <= score["correct"] <= score["total"]):
        raise ValueError("STAGNATION_SCORE_OBSERVATION_INVALID")
    return {"correct": score["correct"], "total": score["total"]}
