"""Durable autonomy recovery helpers separated from live session orchestration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...factory.autonomy import (
    RejectedTeachingAttemptReceipt,
    TeachingReceipt,
    record_rejected_teaching_attempt,
    record_teaching_intervention,
)
from ...factory.teaching import content_digest
from ..autonomy_state import persist_autonomy_state


def _recoverable_teaching_event(event: dict, checkpoint):
    delivery = event.get("autonomy_teaching")
    if not isinstance(delivery, dict):
        return None
    retained_updates = event.get("retained_optimizer_updates")
    if type(retained_updates) is not int or retained_updates < 1:
        return None
    if (event.get("recovered_at_student_sha256") != checkpoint.sha256 or
            event.get("optimizer_step") != checkpoint.optimizer_step):
        return None
    capability = event.get("capability")
    if not isinstance(capability, str) or not capability:
        raise ValueError("AUTONOMY_TEACHING_RECOVERY_CAPABILITY_INVALID")
    return delivery, capability


def _verify_recovery_specimen(run_dir: Path, delivery: dict) -> str:
    specimen_file = delivery.get("specimen_file")
    digest = delivery.get("specimen_content_sha256")
    expected_file = "autonomy/teaching/" + str(digest) + ".json"
    if specimen_file != expected_file:
        raise ValueError("AUTONOMY_TEACHING_RECOVERY_SPECIMEN_PATH_DRIFT")
    path = run_dir / expected_file
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("AUTONOMY_TEACHING_RECOVERY_SPECIMEN_MISSING")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if (not isinstance(rows, list) or content_digest(rows) != digest or
            tuple(dict.fromkeys(row.get("id") for row in rows)) !=
            tuple(delivery.get("specimen_ids", ()))):
        raise ValueError("AUTONOMY_TEACHING_RECOVERY_SPECIMEN_DRIFT")
    return digest


def _failed_recovery_evidence(ledger, obligations: dict, checkpoint):
    return next((
        receipt for receipt in reversed(ledger.receipts)
        if (not receipt.passed and
            receipt.obligation_id in obligations and
            receipt.optimizer_step < checkpoint.optimizer_step)
    ), None)


def _existing_recovered_intervention(ledger, failed, checkpoint, digest: str):
    return next((
        item for item in ledger.interventions
        if (item.obligation_id == failed.obligation_id and
            item.checkpoint_sha256 == checkpoint.sha256 and
            item.specimen_content_sha256 == digest)
    ), None)


def _recovery_intervention_id(school_receipt: dict, failed, checkpoint) -> str:
    return hashlib.sha256(json.dumps({
        "run_id": school_receipt.get("run_id"),
        "generation": school_receipt.get("generation"),
        "obligation": failed.obligation_id,
        "parent": failed.checkpoint_sha256,
        "student": checkpoint.sha256,
        "optimizer_step": checkpoint.optimizer_step,
    }, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _recovered_teaching_receipt(
        school_receipt: dict, delivery: dict, failed, checkpoint,
        digest: str) -> TeachingReceipt:
    return TeachingReceipt(
        obligation_id=failed.obligation_id,
        intervention_id=_recovery_intervention_id(
            school_receipt, failed, checkpoint),
        teaching_option_id=delivery["option_id"],
        selected_provider_id=delivery["provider_id"],
        provider_implementation_sha256=delivery["provider_implementation_sha256"],
        specimen_ids=tuple(delivery["specimen_ids"]),
        specimen_content_sha256=digest,
        variation_axes=tuple(delivery["variation_axes"]),
        optimizer_step_delta=checkpoint.optimizer_step - failed.optimizer_step,
        parent_checkpoint_sha256=failed.checkpoint_sha256,
        parent_optimizer_step=failed.optimizer_step,
        checkpoint_sha256=checkpoint.sha256,
        optimizer_step=checkpoint.optimizer_step,
    )


def rejected_attempt_id(event: dict, delivery: dict, obligation_id: str) -> str:
    return hashlib.sha256(json.dumps({
        "generation": event.get("generation"),
        "obligation": obligation_id,
        "candidate_optimizer_step": event.get("candidate_attempt_optimizer_step"),
        "retained_optimizer_step": event.get("optimizer_step"),
        "retained_checkpoint_sha256": event.get("recovered_at_student_sha256"),
        "specimen_content_sha256": delivery.get("specimen_content_sha256"),
        "paired_scores_sha256": (
            event.get("candidate_retention", {}).get("paired_scores_sha256")
            if isinstance(event.get("candidate_retention"), dict) else None),
    }, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def rejected_attempt_from_event(session, event: dict, failed):
    delivery = event.get("autonomy_teaching")
    if (not isinstance(delivery, dict) or
            event.get("retained_optimizer_updates") != 0):
        raise ValueError("AUTONOMY_REJECTED_ATTEMPT_EVENT_INVALID")
    retention = event.get("candidate_retention")
    reason = retention.get("reason") if isinstance(retention, dict) else None
    if not isinstance(reason, str) or not reason:
        reason = "REJECTED_WITHOUT_RETAINED_GAIN"
    receipt = RejectedTeachingAttemptReceipt(
        obligation_id=failed.obligation_id,
        parent_evidence_id=failed.evidence_id,
        attempt_id=rejected_attempt_id(event, delivery, failed.obligation_id),
        teaching_option_id=delivery["option_id"],
        retained_checkpoint_sha256=event["recovered_at_student_sha256"],
        retained_optimizer_step=event["optimizer_step"],
        candidate_optimizer_step=event["candidate_attempt_optimizer_step"],
        retention_reason=reason,
        selected_provider_id=delivery["provider_id"],
        provider_implementation_sha256=delivery["provider_implementation_sha256"],
        specimen_content_sha256=delivery["specimen_content_sha256"],
    )
    session.record_rejected_attempt(receipt)
    return receipt


def recover_rejected_attempts_from_events(session) -> int:
    path = session.run_dir / "events.jsonl"
    if path.is_symlink() or not path.is_file():
        return 0
    before = len(session.ledger.rejected_attempts)
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        delivery = event.get("autonomy_teaching")
        if (not isinstance(delivery, dict) or
                event.get("retained_optimizer_updates") != 0):
            continue
        capability = event.get("capability")
        checkpoint_sha256 = event.get("recovered_at_student_sha256")
        optimizer_step = event.get("optimizer_step")
        candidate_step = event.get("candidate_attempt_optimizer_step")
        if (not isinstance(capability, str) or
                not isinstance(checkpoint_sha256, str) or
                type(optimizer_step) is not int or type(candidate_step) is not int):
            continue
        obligation_ids = {
            item.obligation_id for item in session._obligations_for_capability(capability)}
        failed = tuple(
            item for item in session.ledger.receipts
            if (not item.passed and item.obligation_id in obligation_ids and
                item.checkpoint_sha256 == checkpoint_sha256 and
                item.optimizer_step == optimizer_step))
        if len(failed) != 1:
            continue
        parent = failed[0]
        raw_reason = (
            event.get("candidate_retention", {}).get("reason")
            if isinstance(event.get("candidate_retention"), dict) else None)
        reason = raw_reason if isinstance(raw_reason, str) and raw_reason else (
            "REJECTED_WITHOUT_RETAINED_GAIN")
        try:
            attempt = RejectedTeachingAttemptReceipt(
                obligation_id=parent.obligation_id,
                parent_evidence_id=parent.evidence_id,
                attempt_id=rejected_attempt_id(event, delivery, parent.obligation_id),
                teaching_option_id=delivery.get("option_id", ""),
                retained_checkpoint_sha256=checkpoint_sha256,
                retained_optimizer_step=optimizer_step,
                candidate_optimizer_step=candidate_step,
                retention_reason=reason,
                selected_provider_id=delivery.get("provider_id", ""),
                provider_implementation_sha256=delivery.get(
                    "provider_implementation_sha256", ""),
                specimen_content_sha256=delivery.get("specimen_content_sha256", ""),
            )
            session.ledger = record_rejected_teaching_attempt(
                session.release, session.ledger, attempt, plan=session.plan)
        except ValueError as error:
            if str(error) == "AUTONOMY_REJECTED_ATTEMPT_PARENT_EVIDENCE_MISMATCH":
                continue
            raise
    added = len(session.ledger.rejected_attempts) - before
    if added:
        persist_autonomy_state(
            session.run_dir, session.release, plan=session.plan, ledger=session.ledger)
    return added


def recover_teaching(session, school_receipt: dict, checkpoint):
    outbox = school_receipt.get("delivery_outbox")
    if not isinstance(outbox, list):
        return None
    for event in reversed(outbox):
        recoverable = _recoverable_teaching_event(event, checkpoint)
        if recoverable is None:
            continue
        delivery, capability = recoverable
        digest = _verify_recovery_specimen(session.run_dir, delivery)
        obligations = {
            item.obligation_id: item
            for item in session._obligations_for_capability(capability)}
        failed = _failed_recovery_evidence(session.ledger, obligations, checkpoint)
        if failed is None:
            continue
        existing = _existing_recovered_intervention(
            session.ledger, failed, checkpoint, digest)
        if existing is not None:
            return existing
        intervention = _recovered_teaching_receipt(
            school_receipt, delivery, failed, checkpoint, digest)
        session.ledger = record_teaching_intervention(
            session.release, session.ledger, intervention, plan=session.plan,
            current_checkpoint_sha256=failed.checkpoint_sha256,
            current_optimizer_step=failed.optimizer_step)
        persist_autonomy_state(
            session.run_dir, session.release, plan=session.plan, ledger=session.ledger)
        return intervention
    return None
