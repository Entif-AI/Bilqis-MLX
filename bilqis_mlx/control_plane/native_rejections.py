"""Authenticate rejection-only BAMF evidence and project it into CP02."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.mission_control import (
    CandidateDecision, CandidateOutcome, CoverageState, LearningEpisode,
)

from .event_stream import EventFamily
from .native_contracts import (
    AuthenticatedGeneration, canonical, derived_event_id, invalid, is_digest,
    native_outbox_event_id, record_meta, run_ref, sha,
)


def _verified_rejection(native, generation, data_plane):
    event_id = native.get("event_id")
    authority_sha = native.get("rejection_authority_sha256")
    evidence = native.get("evidence")
    if (not is_digest(event_id) or not is_digest(authority_sha)
            or not isinstance(evidence, dict)):
        invalid("CONTROL_PLANE_NATIVE_REJECTION_INVALID")
    payload = {key: value for key, value in native.items() if key != "event_id"}
    expected = native_outbox_event_id(
        generation.manifest["run_id"], generation.manifest["generation"], 0,
        payload)
    if event_id != expected:
        invalid("CONTROL_PLANE_NATIVE_REJECTION_EVENT_ID_DRIFT")
    authority = {
        "schema": "bilqis.mlx.bamf-rejection-authority/v1",
        "run_id": generation.manifest["run_id"],
        "generation": generation.manifest["generation"],
        "student_manifest_sha256": generation.manifest_sha256,
        "optimizer_step": generation.manifest["optimizer"].get("step"),
        "evidence": evidence,
    }
    authority_raw = canonical(authority)
    try:
        stored_authority = data_plane.get_object(authority_sha)
    except ValueError:
        invalid("CONTROL_PLANE_NATIVE_REJECTION_AUTHORITY_DRIFT")
    if sha(authority_raw) != authority_sha or stored_authority != authority_raw:
        invalid("CONTROL_PLANE_NATIVE_REJECTION_AUTHORITY_DRIFT")
    receipt = {
        "schema": "bilqis.mlx.bamf-rejection-receipt/v1",
        "run_id": authority["run_id"], "generation": authority["generation"],
        "student_manifest_sha256": generation.manifest_sha256, "event": native,
    }
    receipt_raw = canonical(receipt)
    receipt_sha = sha(receipt_raw)
    try:
        stored_receipt = data_plane.get_object(receipt_sha)
    except ValueError:
        invalid("CONTROL_PLANE_NATIVE_REJECTION_RECEIPT_DRIFT")
    if stored_receipt != receipt_raw:
        invalid("CONTROL_PLANE_NATIVE_REJECTION_RECEIPT_DRIFT")
    return event_id, authority_sha, receipt_sha, evidence


def _project_rejection(native, generation, data_plane):
    event_id, authority_sha, receipt_sha, evidence = _verified_rejection(
        native, generation, data_plane)
    capability = evidence.get("capability")
    visit_id = evidence.get("visit_id")
    if not isinstance(capability, str) or not isinstance(visit_id, str):
        invalid("CONTROL_PLANE_NATIVE_REJECTION_INVALID")
    run = run_ref(generation)
    refs = (f"rejection-authority:{authority_sha}",)
    receipts = (f"bamf-rejection:{receipt_sha}",)
    episode = LearningEpisode(
        record_meta(
            f"episode:{visit_id}", run, generation, evidence_refs=refs,
            receipt_refs=receipts, coverage=CoverageState.PARTIAL),
        visit_id, capability, visit_id, "REJECTED", run.generation, run.generation)
    candidate = CandidateDecision(
        record_meta(
            f"candidate:{event_id}", run, generation, evidence_refs=refs,
            receipt_refs=receipts, coverage=CoverageState.PARTIAL),
        authority_sha, capability, CandidateOutcome.REJECTED,
        str(evidence.get("retention_reason") or "REJECTED"))
    return (episode, candidate), (
        (EventFamily.LESSON_VISIT_COMPLETED, episode,
         derived_event_id(event_id, "episode")),
        (EventFamily.CANDIDATE_REJECTED, candidate, event_id),
    )


def rejection_material(run_dir: Path, history: tuple[AuthenticatedGeneration, ...]):
    ledger = Path(run_dir) / "events.jsonl"
    if not ledger.exists() and not ledger.is_symlink():
        return (), ()
    if ledger.is_symlink() or not ledger.is_file():
        invalid("CONTROL_PLANE_NATIVE_EVENT_LEDGER_INVALID")
    by_manifest = {item.manifest_sha256: item for item in history}
    records, events, seen = [], [], set()
    from bilqis_mlx.data_plane import data_plane

    with ledger.open("rb") as stream:
        for raw in stream:
            if not raw.endswith(b"\n"):
                invalid("CONTROL_PLANE_NATIVE_EVENT_LEDGER_INVALID")
            try:
                native = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                invalid("CONTROL_PLANE_NATIVE_EVENT_LEDGER_INVALID")
            if not isinstance(native, dict) or native.get("event") != "BAMF_CANDIDATE_REJECTED":
                continue
            event_id = native.get("event_id")
            generation = by_manifest.get(native.get("student_manifest_sha256"))
            if generation is None or not is_digest(event_id):
                invalid("CONTROL_PLANE_NATIVE_REJECTION_INVALID")
            if event_id in seen:
                continue
            seen.add(event_id)
            projected_records, projected_events = _project_rejection(
                native, generation, data_plane())
            records.extend(projected_records)
            events.extend(projected_events)
    return tuple(records), tuple(events)


__all__ = ("rejection_material",)
