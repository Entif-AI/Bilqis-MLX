"""Durable authenticated terminal-attempt projection for #1333 cadence recovery."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL


_PROJECTION_KEY = "active-grade-cadence-terminal-attempts"
_PROJECTION_SCHEMA = "bilqis.mlx.bamf-active-grade-cadence-attempt-projection/v1"
_REBUILD_REQUIRED = "BAMF_ACTIVE_GRADE_CADENCE_PROJECTION_REBUILD_REQUIRED"


def _invalid(reason: str):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


def _canonical(value) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False)


def _digest(value) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _accepted_chain(run_dir: Path):
    from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle
    from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
        load_accepted_generation_with_pointer_if_cached,
    )
    from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
        accepted_binding_for_manifest,
        accepted_generation,
        parent_acceptance_anchor_from_manifest,
    )

    root = Path(run_dir)
    cached = load_accepted_generation_with_pointer_if_cached(root)
    if cached is None:
        pointer, student = accepted_generation(root / "bamf-state.json")
    else:
        pointer, student = cached
    manifest = pointer["manifest_sha256"]
    acceptance = pointer["acceptance_sha256"]
    result = {}
    while True:
        accepted_binding_for_manifest(
            root, manifest, student,
            expected_acceptance_sha256=acceptance)
        result[student.generation] = (student, manifest)
        if student.generation == 0:
            break
        parent_manifest = student.parent_manifest_sha256
        parent_acceptance = parent_acceptance_anchor_from_manifest(root, manifest)
        if parent_manifest is None or parent_acceptance is None:
            break
        student = load_bamf_bundle(
            root / "bamf-bundles" / parent_manifest,
            expected_manifest_sha256=parent_manifest)
        manifest, acceptance = parent_manifest, parent_acceptance
    return result


def _accepted_cadence_events(chain):
    events = {}
    for generation, (student, _manifest) in chain.items():
        parent = chain.get(generation - 1)
        for event in student.outbox:
            cadence = event.get("cadence") if isinstance(event, dict) else None
            if event.get("event") != "BAMF_C16_3_ACCEPTED" or not isinstance(cadence, dict):
                continue
            if (generation < 1 or parent is None
                    or event.get("parent_generation") != generation - 1
                    or event.get("accepted_manifest_sha256") != parent[1]
                    or event.get("capability") not in cadence.get(
                        "authorized_capability_ids", ())):
                _invalid("BAMF_ACTIVE_GRADE_CADENCE_ACCEPTED_EVENT_INVALID")
            events[_canonical(event)] = (generation, event)
    return events


def _current_accepted(run_dir: Path):
    from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
        _read_accepted,
        load_accepted_generation_with_pointer_if_cached,
    )

    root = Path(run_dir)
    cached = load_accepted_generation_with_pointer_if_cached(root)
    return cached if cached is not None else _read_accepted(root)


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


def _projection_payload(attempts, pointer, student, seen_accepted):
    return {
        "schema": _PROJECTION_SCHEMA,
        "run_id": student.run_id,
        "accepted_generation": student.generation,
        "accepted_manifest_sha256": pointer["manifest_sha256"],
        "accepted_acceptance_sha256": pointer["acceptance_sha256"],
        "attempts": [[record, capability] for record, capability in attempts],
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
            if (not isinstance(item, list) or len(item) != 2
                    or not isinstance(item[0], dict)
                    or not isinstance(item[1], str) or not item[1]):
                return None
            attempts.append((item[0], item[1]))
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


def _require_incremental_anchor(pointer, student, anchor):
    if anchor is None:
        if student.generation > 1:
            _invalid(_REBUILD_REQUIRED)
        return
    run_id, generation, manifest, acceptance = anchor
    if run_id != student.run_id:
        _invalid(_REBUILD_REQUIRED)
    if student.generation == generation:
        if (pointer["manifest_sha256"] != manifest
                or pointer["acceptance_sha256"] != acceptance):
            _invalid(_REBUILD_REQUIRED)
        return
    if (student.generation == generation + 1
            and student.parent_manifest_sha256 == manifest):
        return
    _invalid(_REBUILD_REQUIRED)


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
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("event") == "BAMF_C16_3_ACCEPTED" and isinstance(
                event.get("cadence"), dict):
            key = _canonical(event)
            if key in seen:
                continue
            item = current_accepted.get(key)
            if item is None:
                _invalid(_REBUILD_REQUIRED)
            seen.add(key)
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
        if key not in seen:
            seen.add(key)
            attempts.append(item)
    return tuple(attempts), seen


def _remember_projection(plane, root, tail, attempts, pointer, student, seen):
    identity = tail["ledger_identity"]
    if identity is None:
        return
    plane.remember_event_projection(
        root, _PROJECTION_KEY, _PROJECTION_SCHEMA, identity,
        tail["indexed_bytes"], _projection_payload(
            attempts, pointer, student, seen))


def authenticated_cadence_attempts(run_dir: Path):
    """Resume the durable cadence projection and authenticate only its unseen tail."""
    root = Path(run_dir).resolve()
    if not (root / "bamf-state.json").exists():
        return ()
    from bilqis_mlx.data_plane import data_plane

    plane = data_plane()
    state = plane.event_projection_state(root, _PROJECTION_KEY, _PROJECTION_SCHEMA)
    attempts, seen, anchor = (), set(), None
    offset = 0
    identity = None
    if state is not None:
        restored = _restore_projection(state["payload"])
        if restored is None:
            _invalid(_REBUILD_REQUIRED)
        attempts, seen, anchor = restored
        offset = state["indexed_bytes"]
        identity = state["ledger_identity"]
    tail = plane.indexed_event_tail(root, offset)
    if state is not None and (
            tail["rebuilt"] or tail["ledger_identity"] != identity):
        _invalid(_REBUILD_REQUIRED)
    pointer, student = _current_accepted(root)
    _require_incremental_anchor(pointer, student, anchor)
    projected, seen = _incremental_attempts(
        root, tail["events"], pointer, student, list(attempts), seen, anchor)
    _remember_projection(plane, root, tail, projected, pointer, student, seen)
    return projected


def rebuild_authenticated_cadence_attempts(run_dir: Path):
    """Explicitly rebuild the durable projection by replaying accepted history."""
    root = Path(run_dir).resolve()
    if not (root / "bamf-state.json").exists():
        return ()
    from bilqis_mlx.data_plane import data_plane
    from .priority_rejection_replay import authenticated_rejection_event

    plane = data_plane()
    tail = plane.indexed_event_tail(root, 0)
    chain = _accepted_chain(root)
    accepted = _accepted_cadence_events(chain)
    seen = set()
    attempts = []
    for event in tail["events"]:
        if not isinstance(event, dict):
            continue
        if event.get("event") == "BAMF_C16_3_ACCEPTED" and isinstance(
                event.get("cadence"), dict):
            key = _canonical(event)
            if key not in accepted:
                _invalid("BAMF_ACTIVE_GRADE_CADENCE_ACCEPTED_EVENT_INVALID")
            if key not in seen:
                seen.add(key)
                attempts.append((event["cadence"], event["capability"]))
            continue
        evidence = event.get("evidence")
        cadence = evidence.get("cadence") if isinstance(evidence, dict) else None
        if event.get("event") != "BAMF_CANDIDATE_REJECTED" or not isinstance(
                cadence, dict):
            continue
        parent = chain.get(event.get("generation"))
        if parent is None:
            _invalid("BAMF_ACTIVE_GRADE_CADENCE_REJECTION_GENERATION_INVALID")
        if not authenticated_rejection_event(event, parent[0], parent[1]):
            _invalid("BAMF_ACTIVE_GRADE_CADENCE_REJECTION_EVENT_INVALID")
        capability = evidence.get("capability")
        if capability not in cadence.get("authorized_capability_ids", ()):
            _invalid("BAMF_ACTIVE_GRADE_CADENCE_REJECTION_EVENT_INVALID")
        attempts.append((cadence, capability))
    for key, (generation, event) in sorted(
            accepted.items(), key=lambda item: item[1][0]):
        if key not in seen:
            seen.add(key)
            attempts.append((event["cadence"], event["capability"]))
    pointer, student = _current_accepted(root)
    current = chain.get(student.generation)
    if (current is None or current[1] != pointer["manifest_sha256"]
            or current[0].run_id != student.run_id):
        _invalid(_REBUILD_REQUIRED)
    projected = tuple(attempts)
    _remember_projection(plane, root, tail, projected, pointer, student, seen)
    return projected


__all__ = (
    "authenticated_cadence_attempts", "rebuild_authenticated_cadence_attempts",
)
