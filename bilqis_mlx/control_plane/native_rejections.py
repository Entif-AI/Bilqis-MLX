"""Authenticate rejection-only BAMF evidence and project it into CP02."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control import (
    CandidateDecision, CandidateOutcome, CoverageState, LearningEpisode,
    UnavailableEnvelope, UnavailableReason,
)
from bilqis_mlx.runtime.bamf_rejection import (
    portable_rejection_receipt, rejection_registry,
    verify_portable_rejection_authority,
)

from .event_stream import EventFamily
from .native_contracts import (
    AuthenticatedGeneration, accepted_student_sha256, canonical, derived_event_id,
    invalid, is_digest, native_outbox_event_id, record_meta, run_ref, sha,
)


class _LegacyRejectionUnavailable(Exception):
    """A legacy rejection is shaped, but its optional backing object is gone."""


def _missing_data_plane_object(error: ValueError) -> bool:
    return str(error).split(":", 1)[0] == DataPlaneError.OBJECT_MISSING.value


def _unavailable_rejection(native, generation):
    run = run_ref(generation)
    event_id = native.get("event_id")
    return UnavailableEnvelope(
        record_meta(
            f"rejection-unavailable:{event_id}", run, generation,
            native=native, coverage=CoverageState.UNKNOWN),
        f"episode:{run.run_id}", UnavailableReason.UNAVAILABLE, None)


def _verified_legacy_rejection(
        native, generation, data_plane, *, event_id, authority_sha, evidence):
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
    except ValueError as error:
        if _missing_data_plane_object(error):
            raise _LegacyRejectionUnavailable from None
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
    except ValueError as error:
        if _missing_data_plane_object(error):
            raise _LegacyRejectionUnavailable from None
        invalid("CONTROL_PLANE_NATIVE_REJECTION_RECEIPT_DRIFT")
    if stored_receipt != receipt_raw:
        invalid("CONTROL_PLANE_NATIVE_REJECTION_RECEIPT_DRIFT")
    return event_id, authority_sha, receipt_sha, evidence, False


def _verified_rejection(native, generation, data_plane=None):
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
    portable_authority = native.get("rejection_authority")
    if portable_authority is not None:
        registry = rejection_registry(generation.correction_frontier)
        accepted_registry = generation.acceptance.get(
            "source_authority_registry_sha256")
        genesis_registry = (
            generation.manifest.get("generation") == 0
            and generation.acceptance.get("schema_version")
            == "bilqis.mlx.bamf-initial-generation-binding/v1"
            and generation.acceptance.get("run_identity_sha256")
            == generation.run_identity.get("run_identity_sha256")
        )
        if (registry is None
                or (accepted_registry != registry.digest and not genesis_registry)):
            invalid("CONTROL_PLANE_NATIVE_REJECTION_AUTHORITY_DRIFT")
        authority_raw = canonical(portable_authority)
        if sha(authority_raw) != authority_sha:
            invalid("CONTROL_PLANE_NATIVE_REJECTION_AUTHORITY_DRIFT")
        try:
            verify_portable_rejection_authority(
                portable_authority, registry,
                run_id=generation.manifest["run_id"],
                generation=generation.manifest["generation"],
                student_manifest_sha256=generation.manifest_sha256,
                optimizer_step=generation.manifest["optimizer"].get("step"),
                evidence=evidence)
        except BilqisError:
            invalid("CONTROL_PLANE_NATIVE_REJECTION_AUTHORITY_DRIFT")
        receipt = portable_rejection_receipt(
            run_id=generation.manifest["run_id"],
            generation=generation.manifest["generation"],
            student_manifest_sha256=generation.manifest_sha256,
            optimizer_step=generation.manifest["optimizer"].get("step"),
            authority_sha256=authority_sha)
        receipt_sha = sha(canonical(receipt))
        if native.get("rejection_receipt_sha256") != receipt_sha:
            invalid("CONTROL_PLANE_NATIVE_REJECTION_RECEIPT_DRIFT")
        return event_id, authority_sha, receipt_sha, evidence, True
    if data_plane is None:
        return None
    return _verified_legacy_rejection(
        native, generation, data_plane, event_id=event_id,
        authority_sha=authority_sha, evidence=evidence)


def _project_verified_rejection(verified, generation):
    event_id, authority_sha, receipt_sha, evidence, portable = verified
    if evidence.get("schema") != "bilqis.bamf.c16.3-rejection/v2":
        return (), ()
    capability = evidence.get("capability")
    visit_id = evidence.get("visit_id")
    policy_key = evidence.get("selected_policy_key")
    option_id = evidence.get("selected_option_id")
    candidate_step = evidence.get("candidate_optimizer_step")
    retained_step = evidence.get("retained_optimizer_step")
    rejection_attempt_ordinal = evidence.get("rejection_attempt_ordinal")
    from bilqis_mlx.learning.atlas_retention_decision import CandidateRetentionDecision

    decision = CandidateRetentionDecision.from_record(evidence.get("decision"))
    decision_fields = decision.fields
    if (not isinstance(capability, str) or not capability
            or not isinstance(visit_id, str) or not visit_id
            or not isinstance(policy_key, str) or not policy_key
            or not isinstance(option_id, str) or not option_id
            or type(candidate_step) is not int
            or candidate_step <= generation.manifest["optimizer"].get("step")
            or retained_step != generation.manifest["optimizer"].get("step")
            or (rejection_attempt_ordinal is not None
                and (type(rejection_attempt_ordinal) is not int
                     or rejection_attempt_ordinal < 1))
            or decision.decision != "REJECT"
            or decision_fields.get("parent_generation")
            != accepted_student_sha256(generation)
            or evidence.get("retention_reason") != decision.reason):
        invalid("CONTROL_PLANE_NATIVE_REJECTION_INVALID")
    from bilqis_mlx.learning.teacher_visit_identity import (
        TeacherVisitIdentity, require_teacher_visit_receipt,
    )

    state = generation.teacher_state
    expected_visit = TeacherVisitIdentity.from_record(evidence.get("teacher_visit"))
    if (visit_id != expected_visit.visit_id
            or expected_visit.run_identity_sha256
            != generation.run_identity["run_identity_sha256"]
            or expected_visit.run_seed != generation.run_identity["run_seed"]
            or expected_visit.generation != generation.manifest["generation"]
            or expected_visit.accepted_manifest_sha256 != generation.manifest_sha256
            or expected_visit.student_sha256 != accepted_student_sha256(generation)
            or expected_visit.selection_seed != state["next_seed"]
            or expected_visit.cursor != state["cursor"]
            or expected_visit.capability_id != capability
            or expected_visit.policy_key != policy_key
            or ("c03_lineage" in state
                and (expected_visit.teacher_identity != state["teacher_identity"]
                     or expected_visit.teacher_epoch != state["teacher_epoch"]))):
        invalid("CONTROL_PLANE_NATIVE_REJECTION_VISIT_DRIFT")
    if not portable:
        require_teacher_visit_receipt(expected_visit)
    run = run_ref(generation)
    refs = (f"rejection-authority:{authority_sha}",)
    receipts = (f"bamf-rejection:{receipt_sha}",)
    episode_id = (
        f"{visit_id}:rejection:{event_id}"
        if rejection_attempt_ordinal is None
        else f"{visit_id}:rejection:{rejection_attempt_ordinal}")
    episode = LearningEpisode(
        record_meta(
            f"episode:{episode_id}", run, generation, evidence_refs=refs,
            receipt_refs=receipts, coverage=CoverageState.PARTIAL),
        episode_id, capability, visit_id, "REJECTED", run.generation, run.generation)
    candidate = CandidateDecision(
        record_meta(
            f"candidate:{event_id}", run, generation, evidence_refs=refs,
            receipt_refs=receipts, coverage=CoverageState.PARTIAL),
        decision_fields["candidate_generation"], capability, CandidateOutcome.REJECTED,
        str(evidence.get("retention_reason") or "REJECTED"))
    return (episode, candidate), (
        (EventFamily.LESSON_VISIT_COMPLETED, episode,
         derived_event_id(event_id, "episode")),
        (EventFamily.CANDIDATE_REJECTED, candidate, event_id),
    )


def rejection_material(
        run_dir: Path, history: tuple[AuthenticatedGeneration, ...], *,
        portable_only: bool = False):
    ledger = Path(run_dir) / "events.jsonl"
    if not ledger.exists() and not ledger.is_symlink():
        return (), ()
    if ledger.is_symlink() or not ledger.is_file():
        invalid("CONTROL_PLANE_NATIVE_EVENT_LEDGER_INVALID")
    by_manifest = {item.manifest_sha256: item for item in history}
    records, events, seen_receipts = [], [], set()
    plane = None
    if not portable_only:
        from bilqis_mlx.data_plane import data_plane
        plane = data_plane()

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
            generation = by_manifest.get(native.get("student_manifest_sha256"))
            if generation is None:
                invalid("CONTROL_PLANE_NATIVE_REJECTION_INVALID")
            try:
                verified = _verified_rejection(native, generation, plane)
            except _LegacyRejectionUnavailable:
                records.append(_unavailable_rejection(native, generation))
                continue
            if verified is None:
                continue
            receipt_sha = verified[2]
            if receipt_sha in seen_receipts:
                continue
            seen_receipts.add(receipt_sha)
            projected_records, projected_events = _project_verified_rejection(
                verified, generation)
            records.extend(projected_records)
            events.extend(projected_events)
    return tuple(records), tuple(events)


__all__ = ("rejection_material",)
