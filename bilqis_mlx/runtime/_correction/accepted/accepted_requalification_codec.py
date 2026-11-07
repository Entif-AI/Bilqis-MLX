"""Typed durable codec for C09 requalification state."""
from __future__ import annotations

from bilqis_mlx.errors import BilqisError

from .atlas_requalification_contracts import (
    C10InvalidationIntent, CapabilitySupport, RequalificationLedger,
    RequalificationStatus, RequalificationUpdate, TargetedSourceTask,
)
from .atlas_revalidation_common import _invalid


def _support_record(item: CapabilitySupport) -> dict:
    return {
        "capability_id": item.capability_id,
        "support_artifact_ids": list(item.support_artifact_ids),
        "source_anchor_ids": list(item.source_anchor_ids),
        "retained_generation_sha256": item.retained_generation_sha256,
        "observation_ids": list(item.observation_ids),
        "status": item.status.value,
        "schema_version": item.schema_version,
    }


def _support_from_record(item: dict) -> CapabilitySupport:
    return CapabilitySupport(
        capability_id=item["capability_id"],
        support_artifact_ids=tuple(item["support_artifact_ids"]),
        source_anchor_ids=tuple(item["source_anchor_ids"]),
        retained_generation_sha256=item["retained_generation_sha256"],
        observation_ids=tuple(item["observation_ids"]),
        status=RequalificationStatus(item["status"]),
        schema_version=item["schema_version"],
    )


def _task_record(item: TargetedSourceTask) -> dict:
    return {
        "task_id": item.task_id,
        "capability_id": item.capability_id,
        "source_anchor_ids": list(item.source_anchor_ids),
        "correction_event_id": item.correction_event_id,
        "retained_generation_sha256": item.retained_generation_sha256,
        "reason_code": item.reason_code,
        "schema_version": item.schema_version,
    }


def _task_from_record(item: dict) -> TargetedSourceTask:
    return TargetedSourceTask(
        task_id=item["task_id"], capability_id=item["capability_id"],
        source_anchor_ids=tuple(item["source_anchor_ids"]),
        correction_event_id=item["correction_event_id"],
        retained_generation_sha256=item["retained_generation_sha256"],
        reason_code=item["reason_code"], schema_version=item["schema_version"],
    )


def _intent_record(item: C10InvalidationIntent) -> dict:
    return {
        "event_id": item.event_id, "payload_digest": item.payload_digest,
        "correction_event_id": item.correction_event_id,
        "source_receipt_sha256": item.source_receipt_sha256,
        "affected_artifact_ids": list(item.affected_artifact_ids),
        "capability_ids": list(item.capability_ids),
        "namespace": item.namespace, "delivery_state": item.delivery_state,
        "schema_version": item.schema_version,
    }


def _intent_from_record(item: dict) -> C10InvalidationIntent:
    return C10InvalidationIntent(
        event_id=item["event_id"], payload_digest=item["payload_digest"],
        correction_event_id=item["correction_event_id"],
        source_receipt_sha256=item["source_receipt_sha256"],
        affected_artifact_ids=tuple(item["affected_artifact_ids"]),
        capability_ids=tuple(item["capability_ids"]),
        namespace=item["namespace"], delivery_state=item["delivery_state"],
        schema_version=item["schema_version"],
    )


def ledger_record(ledger: RequalificationLedger) -> dict:
    if not isinstance(ledger, RequalificationLedger):
        _invalid("BAMF_C09_REQUALIFICATION_RECORD_INVALID")
    return {
        "capabilities": [_support_record(item) for item in ledger.capabilities],
        "historical": [_support_record(item) for item in ledger.historical],
        "pending_source_tasks": [
            _task_record(item) for item in ledger.pending_source_tasks],
        "pending_c10_intents": [
            _intent_record(item) for item in ledger.pending_c10_intents],
        "schema_version": ledger.schema_version,
    }


def ledger_from_record(record: dict) -> RequalificationLedger:
    try:
        return RequalificationLedger(
            capabilities=tuple(_support_from_record(item)
                               for item in record["capabilities"]),
            historical=tuple(_support_from_record(item)
                             for item in record["historical"]),
            pending_source_tasks=tuple(_task_from_record(item)
                                      for item in record["pending_source_tasks"]),
            pending_c10_intents=tuple(_intent_from_record(item)
                                     for item in record["pending_c10_intents"]),
            schema_version=record["schema_version"],
        )
    except (KeyError, TypeError, ValueError, BilqisError):
        _invalid("BAMF_C09_REQUALIFICATION_RECORD_INVALID")


def update_record(update: RequalificationUpdate) -> dict:
    if not isinstance(update, RequalificationUpdate):
        _invalid("BAMF_C09_REQUALIFICATION_RECORD_INVALID")
    return {
        "ledger": ledger_record(update.ledger),
        "affected_capability_ids": list(update.affected_capability_ids),
        "new_source_tasks": [_task_record(item) for item in update.new_source_tasks],
        "new_c10_intents": [_intent_record(item) for item in update.new_c10_intents],
        "schema_version": update.schema_version,
    }


def update_from_record(record: dict) -> RequalificationUpdate:
    try:
        return RequalificationUpdate(
            ledger=ledger_from_record(record["ledger"]),
            affected_capability_ids=tuple(record["affected_capability_ids"]),
            new_source_tasks=tuple(_task_from_record(item)
                                   for item in record["new_source_tasks"]),
            new_c10_intents=tuple(_intent_from_record(item)
                                  for item in record["new_c10_intents"]),
            schema_version=record["schema_version"],
        )
    except (KeyError, TypeError, ValueError, BilqisError):
        _invalid("BAMF_C09_REQUALIFICATION_RECORD_INVALID")


__all__ = ("ledger_from_record", "ledger_record", "update_from_record", "update_record")
