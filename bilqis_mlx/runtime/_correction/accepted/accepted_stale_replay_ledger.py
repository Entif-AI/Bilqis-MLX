"""Durable codecs for accepted-run remediation, replay, and process-fault evidence."""
from __future__ import annotations

import hashlib
import json

from .atlas_revalidation_common import _invalid
from .atlas_stale_replay import (
    DerivedClaim, ProcessFault, RemediationReceipt, RemediationStatus,
)


REMEDIATION_EVENT = "BAMF_C09_REMEDIATION"
DERIVED_CLAIM_EVENT = "BAMF_C09_DERIVED_CLAIM"
PROCESS_FAULT_EVENT = "BAMF_C09_PROCESS_FAULT"


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def remediation_record(
    manifest_sha256: str, remediation: RemediationReceipt,
) -> dict:
    if not isinstance(remediation, RemediationReceipt):
        _invalid("BAMF_C09_REMEDIATION_RECEIPT_INVALID")
    body = {
        "event": REMEDIATION_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "remediation": {
            "remediation_id": remediation.remediation_id,
            "correction_event_id": remediation.correction_event_id,
            "correction_receipt_sha256": remediation.correction_receipt_sha256,
            "original_actor_id": remediation.original_actor_id,
            "original_source_event_id": remediation.original_source_event_id,
            "original_source_time": remediation.original_source_time,
            "superseded_fact_digest": remediation.superseded_fact_digest,
            "superseded_source_receipt_sha256": remediation.superseded_source_receipt_sha256,
            "affected_artifact_ids": list(remediation.affected_artifact_ids),
            "retained_generation_sha256": remediation.retained_generation_sha256,
            "completed_at": remediation.completed_at,
            "status": remediation.status.value,
            "schema_version": remediation.schema_version,
        },
    }
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def remediation_from_record(record: dict) -> RemediationReceipt:
    try:
        item = record["remediation"]
        return RemediationReceipt(
            remediation_id=item["remediation_id"],
            correction_event_id=item["correction_event_id"],
            correction_receipt_sha256=item["correction_receipt_sha256"],
            original_actor_id=item["original_actor_id"],
            original_source_event_id=item["original_source_event_id"],
            original_source_time=item["original_source_time"],
            superseded_fact_digest=item["superseded_fact_digest"],
            superseded_source_receipt_sha256=item["superseded_source_receipt_sha256"],
            affected_artifact_ids=tuple(item["affected_artifact_ids"]),
            retained_generation_sha256=item["retained_generation_sha256"],
            completed_at=item["completed_at"],
            status=RemediationStatus(item["status"]),
            schema_version=item["schema_version"],
        )
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_REMEDIATION_LEDGER_INVALID")


def derived_claim_record(manifest_sha256: str, claim: DerivedClaim) -> dict:
    if not isinstance(claim, DerivedClaim):
        _invalid("BAMF_C09_DERIVED_CLAIM_INVALID")
    body = {
        "event": DERIVED_CLAIM_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "claim": {
            "claim_id": claim.claim_id,
            "actor_id": claim.actor_id,
            "source_event_id": claim.source_event_id,
            "source_time": claim.source_time,
            "source_receipt_sha256": claim.source_receipt_sha256,
            "fact_digest": claim.fact_digest,
            "observed_at": claim.observed_at,
            "derived_path": list(claim.derived_path),
            "schema_version": claim.schema_version,
        },
    }
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def derived_claim_from_record(record: dict) -> DerivedClaim:
    try:
        item = record["claim"]
        return DerivedClaim(
            claim_id=item["claim_id"], actor_id=item["actor_id"],
            source_event_id=item["source_event_id"], source_time=item["source_time"],
            source_receipt_sha256=item["source_receipt_sha256"],
            fact_digest=item["fact_digest"], observed_at=item["observed_at"],
            derived_path=tuple(item["derived_path"]),
            schema_version=item["schema_version"],
        )
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_DERIVED_CLAIM_LEDGER_INVALID")


def process_fault_record(manifest_sha256: str, fault: ProcessFault,
                         requalification=None) -> dict:
    if not isinstance(fault, ProcessFault):
        _invalid("BAMF_C09_PROCESS_FAULT_INVALID")
    body = {
        "event": PROCESS_FAULT_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "fault": {
            "original_source_event_id": fault.original_source_event_id,
            "original_source_time": fault.original_source_time,
            "correction_event_id": fault.correction_event_id,
            "correction_receipt_sha256": fault.correction_receipt_sha256,
            "remediation_id": fault.remediation_id,
            "offending_claim_id": fault.offending_claim_id,
            "offending_derived_path": list(fault.offending_derived_path),
            "held_artifact_ids": list(fault.held_artifact_ids),
            "retained_generation_sha256": fault.retained_generation_sha256,
            "reason_code": fault.reason_code,
            "error_code": fault.error_code,
            "schema_version": fault.schema_version,
        },
    }
    if requalification is not None:
        from .accepted_requalification_codec import update_record
        body["requalification"] = update_record(requalification)
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def process_fault_from_record(record: dict) -> ProcessFault:
    try:
        item = record["fault"]
        return ProcessFault(
            original_source_event_id=item["original_source_event_id"],
            original_source_time=item["original_source_time"],
            correction_event_id=item["correction_event_id"],
            correction_receipt_sha256=item["correction_receipt_sha256"],
            remediation_id=item["remediation_id"],
            offending_claim_id=item["offending_claim_id"],
            offending_derived_path=tuple(item["offending_derived_path"]),
            held_artifact_ids=tuple(item["held_artifact_ids"]),
            retained_generation_sha256=item["retained_generation_sha256"],
            reason_code=item["reason_code"], error_code=item["error_code"],
            schema_version=item["schema_version"],
        )
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_PROCESS_FAULT_LEDGER_INVALID")


def process_fault_requalification_from_record(record: dict):
    if "requalification" not in record:
        return None
    try:
        from .accepted_requalification_codec import update_from_record
        return update_from_record(record["requalification"])
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_PROCESS_FAULT_LEDGER_INVALID")


__all__ = (
    "DERIVED_CLAIM_EVENT", "PROCESS_FAULT_EVENT", "REMEDIATION_EVENT",
    "derived_claim_from_record", "derived_claim_record",
    "process_fault_from_record", "process_fault_record",
    "process_fault_requalification_from_record",
    "remediation_from_record", "remediation_record",
)
