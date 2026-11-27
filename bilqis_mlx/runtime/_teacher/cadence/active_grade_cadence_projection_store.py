"""Durable storage helpers for the active-grade cadence attempt projection."""
from __future__ import annotations


_PROJECTION_KEY = "active-grade-cadence-terminal-attempts"
_LEGACY_PROJECTION_SCHEMA = "bilqis.mlx.bamf-active-grade-cadence-attempt-projection/v2"
_PROJECTION_SCHEMA = "bilqis.mlx.bamf-active-grade-cadence-attempt-projection/v3"
_LEGACY_ATTEMPT_RECORD_SIZE = 2
_ATTEMPT_RECORD_SIZE = 3
_ATTEMPT_OUTCOME_INDEX = 2


def _digest(value) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _projection_payload(attempts, pointer, student, seen_accepted):
    return {
        "schema": _PROJECTION_SCHEMA,
        "run_id": student.run_id,
        "accepted_generation": student.generation,
        "accepted_manifest_sha256": pointer["manifest_sha256"],
        "accepted_acceptance_sha256": pointer["acceptance_sha256"],
        "attempts": [
            [record, capability, outcome]
            for record, capability, outcome in attempts
        ],
        "seen_accepted_events": sorted(seen_accepted),
    }


def _restore_projection(record):
    expected = {
        "schema", "run_id", "accepted_generation", "accepted_manifest_sha256",
        "accepted_acceptance_sha256", "attempts", "seen_accepted_events",
    }
    try:
        if (not isinstance(record, dict) or set(record) != expected
                or record.get("schema") != _PROJECTION_SCHEMA
                or not isinstance(record.get("run_id"), str) or not record["run_id"]
                or type(record.get("accepted_generation")) is not int
                or record["accepted_generation"] < 0
                or not _digest(record.get("accepted_manifest_sha256"))
                or not _digest(record.get("accepted_acceptance_sha256"))
                or not isinstance(record.get("attempts"), list)
                or not isinstance(record.get("seen_accepted_events"), list)):
            return None
        attempts = []
        for item in record["attempts"]:
            if (not isinstance(item, list) or len(item) != _ATTEMPT_RECORD_SIZE
                    or not isinstance(item[0], dict)
                    or not isinstance(item[1], str) or not item[1]
                    or item[_ATTEMPT_OUTCOME_INDEX] not in {
                        "RETAINED", "REJECTED", "PERFECT_TARGET_SKIPPED"}):
                return None
            attempts.append((item[0], item[1], item[_ATTEMPT_OUTCOME_INDEX]))
        seen = set(record["seen_accepted_events"])
        if len(seen) != len(record["seen_accepted_events"]) or any(
                not isinstance(item, str) for item in seen):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    anchor = (
        record["run_id"], record["accepted_generation"],
        record["accepted_manifest_sha256"], record["accepted_acceptance_sha256"],
    )
    return tuple(attempts), seen, anchor


def _restore_legacy_projection(record):
    if (not isinstance(record, dict)
            or record.get("schema") != _LEGACY_PROJECTION_SCHEMA):
        return None
    expected = {
        "schema", "run_id", "accepted_generation", "accepted_manifest_sha256",
        "accepted_acceptance_sha256", "attempts", "seen_accepted_events",
    }
    try:
        if (set(record) != expected
                or not isinstance(record.get("run_id"), str) or not record["run_id"]
                or type(record.get("accepted_generation")) is not int
                or record["accepted_generation"] < 0
                or not _digest(record.get("accepted_manifest_sha256"))
                or not _digest(record.get("accepted_acceptance_sha256"))
                or not isinstance(record.get("attempts"), list)
                or not isinstance(record.get("seen_accepted_events"), list)):
            return None
        if any(
                not isinstance(item, list)
                or len(item) != _LEGACY_ATTEMPT_RECORD_SIZE
                or not isinstance(item[0], dict)
                or not isinstance(item[1], str) or not item[1]
                for item in record["attempts"]):
            return None
        seen = set(record["seen_accepted_events"])
        if len(seen) != len(record["seen_accepted_events"]) or any(
                not isinstance(item, str) for item in seen):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    anchor = (
        record["run_id"], record["accepted_generation"],
        record["accepted_manifest_sha256"], record["accepted_acceptance_sha256"],
    )
    # v2 did not preserve terminal outcome semantics. Its attempts cannot become
    # v3 recovery exposure; retain only the authenticated stream frontier.
    return (), seen, anchor


def _pending_attempts(attempts, cadence_state):
    """Keep only terminal attempts not already represented by durable cadence state."""
    if cadence_state is None:
        return tuple(attempts)
    attempted = set(cadence_state.attempted_capability_ids)
    return tuple(
        (record, capability, outcome)
        for record, capability, outcome in attempts
        if (record.get("phase_sha256") == cadence_state.phase_sha256
            and capability not in attempted)
    )


def _remember_projection(plane, root, tail, attempts, pointer, student, seen):
    identity = tail["ledger_identity"]
    if identity is None:
        return
    plane.remember_event_projection(
        root, _PROJECTION_KEY, _PROJECTION_SCHEMA, identity,
        tail["indexed_bytes"], _projection_payload(
            attempts, pointer, student, seen))


__all__ = (
    "_LEGACY_PROJECTION_SCHEMA", "_PROJECTION_KEY", "_PROJECTION_SCHEMA",
    "_pending_attempts", "_remember_projection", "_restore_legacy_projection",
    "_restore_projection",
)
