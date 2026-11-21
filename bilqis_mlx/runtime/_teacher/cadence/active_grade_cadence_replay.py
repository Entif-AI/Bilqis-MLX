"""Durable authenticated terminal-attempt projection for #1333 cadence recovery."""
from __future__ import annotations

from pathlib import Path

from .active_grade_cadence_projection_store import (
    _PROJECTION_KEY, _PROJECTION_SCHEMA, _pending_attempts,
    _remember_projection, _restore_projection,
)
from .active_grade_cadence_replay_support import (
    _REBUILD_REQUIRED, _canonical, _incremental_attempts, _invalid,
)


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


def _require_incremental_anchor(pointer, student, anchor):
    if anchor is None:
        if student.generation != 0:
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
    pointer, student = _current_accepted(root)
    from .active_grade_cadence_custody import read_current_cadence
    cadence_state = read_current_cadence(root)
    if state is None:
        if student.generation != 0 or cadence_state is not None:
            _invalid(_REBUILD_REQUIRED)
    if state is not None:
        restored = _restore_projection(state["payload"])
        if restored is None:
            _invalid(_REBUILD_REQUIRED)
        attempts, seen, anchor = restored
        attempts = _pending_attempts(attempts, cadence_state)
        offset = state["indexed_bytes"]
        identity = state["ledger_identity"]
    tail = plane.indexed_event_tail(root, offset)
    if state is not None and (
            tail["rebuilt"] or tail["ledger_identity"] != identity):
        _invalid(_REBUILD_REQUIRED)
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
