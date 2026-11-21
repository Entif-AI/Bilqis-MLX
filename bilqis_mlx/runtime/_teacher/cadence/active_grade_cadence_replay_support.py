"""Incremental accepted-event authentication helpers for cadence replay."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL


_REBUILD_REQUIRED = "BAMF_ACTIVE_GRADE_CADENCE_PROJECTION_REBUILD_REQUIRED"


def _invalid(reason: str):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


def _canonical(value) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False)


def _current_accepted_events(student):
    result = {}
    if student.generation == 0:
        return result
    parent_manifest = student.parent_manifest_sha256
    for event in student.outbox:
        cadence = event.get("cadence") if isinstance(event, dict) else None
        if event.get("event") != "BAMF_C16_3_ACCEPTED" or not isinstance(cadence, dict):
            continue
        capability = event.get("capability")
        if (event.get("parent_generation") != student.generation - 1
                or parent_manifest is None
                or event.get("accepted_manifest_sha256") != parent_manifest
                or capability not in cadence.get("authorized_capability_ids", ())):
            _invalid("BAMF_ACTIVE_GRADE_CADENCE_ACCEPTED_EVENT_INVALID")
        result[_canonical(event)] = (cadence, capability)
    return result


def _anchored_parent(run_dir: Path, anchor, student):
    if anchor is None or student.generation != anchor[1] + 1:
        return None
    from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle

    manifest = anchor[2]
    parent = load_bamf_bundle(
        Path(run_dir) / "bamf-bundles" / manifest,
        expected_manifest_sha256=manifest)
    if (parent.run_id != anchor[0]
            or parent.generation != anchor[1]
            or student.parent_manifest_sha256 != manifest):
        _invalid(_REBUILD_REQUIRED)
    return parent


def _incremental_attempts(run_dir, events, pointer, student, attempts, seen, anchor):
    current_accepted = _current_accepted_events(student)
    parent = None
    observed_accepted = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("event") == "BAMF_C16_3_ACCEPTED" and isinstance(
                event.get("cadence"), dict):
            key = _canonical(event)
            observed_accepted.add(key)
            if key in seen:
                seen.remove(key)
                continue
            item = current_accepted.get(key)
            if item is None:
                _invalid(_REBUILD_REQUIRED)
            attempts.append(item)
            continue
        evidence = event.get("evidence")
        cadence = evidence.get("cadence") if isinstance(evidence, dict) else None
        if event.get("event") != "BAMF_CANDIDATE_REJECTED" or not isinstance(
                cadence, dict):
            continue
        generation = event.get("generation")
        if generation == student.generation:
            owner, manifest = student, pointer["manifest_sha256"]
        elif (anchor is not None and generation == anchor[1]
                and student.generation == anchor[1] + 1):
            if parent is None:
                parent = _anchored_parent(Path(run_dir), anchor, student)
            owner, manifest = parent, anchor[2]
        else:
            _invalid(_REBUILD_REQUIRED)
        from .priority_rejection_replay import authenticated_rejection_event
        if not authenticated_rejection_event(event, owner, manifest):
            _invalid("BAMF_ACTIVE_GRADE_CADENCE_REJECTION_EVENT_INVALID")
        capability = evidence.get("capability")
        if capability not in cadence.get("authorized_capability_ids", ()):
            _invalid("BAMF_ACTIVE_GRADE_CADENCE_REJECTION_EVENT_INVALID")
        attempts.append((cadence, capability))
    for key, item in current_accepted.items():
        if key not in seen and key not in observed_accepted:
            seen.add(key)
            attempts.append(item)
    return tuple(attempts), seen


__all__ = ("_REBUILD_REQUIRED", "_canonical", "_incremental_attempts", "_invalid")
