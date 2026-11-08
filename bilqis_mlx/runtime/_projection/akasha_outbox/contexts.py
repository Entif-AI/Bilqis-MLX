"""Accepted context requalification projection into C10's local outbox."""
from pathlib import Path

from .contracts import AkashaEventKind, _invalid
from .events import AkashaEvent
from .store import append_outbox


def _accepted_context_invalidation(
    run_dir: Path, manifest_sha256: str, context_event_id: str,
) -> tuple[dict, object]:
    from bilqis_mlx.runtime.accepted_correction_ledger import (
        CONTEXT_INVALIDATION_EVENT,
        context_invalidation_from_record,
        read_records,
    )

    matches = tuple(
        record for record in read_records(Path(run_dir), manifest_sha256)
        if record["event"] == CONTEXT_INVALIDATION_EVENT
        and record["context_invalidation"]["context_event_id"] == context_event_id
    )
    if len(matches) != 1:
        _invalid("BAMF_C10_CONTEXT_RECEIPT_REQUIRED")
    record = matches[0]
    return record, context_invalidation_from_record(record)


def event_from_context_requalification(
    run_dir: Path, manifest_sha256: str, task, ledger,
) -> AkashaEvent:
    """Derive one C10 event from durable accepted C09 context custody."""
    from bilqis_mlx.runtime.atlas_requalification import (
        RequalificationLedger,
        RequalificationStatus,
        TargetedSourceTask,
    )

    if (not isinstance(task, TargetedSourceTask)
            or not isinstance(ledger, RequalificationLedger)
            or task.context_event_id is None
            or task.correction_event_id is not None
            or task not in ledger.pending_source_tasks):
        _invalid("BAMF_C10_CONTEXT_REQUALIFICATION_ARGUMENT_INVALID")
    record, invalidation = _accepted_context_invalidation(
        Path(run_dir), manifest_sha256, task.context_event_id)
    support = ledger.capability(task.capability_id)
    if (support.status is not RequalificationStatus.REQUALIFICATION_REQUIRED
            or support.retained_generation_sha256
            != task.retained_generation_sha256
            or support.source_anchor_ids != task.source_anchor_ids):
        _invalid("BAMF_C10_CONTEXT_REQUALIFICATION_SUPPORT_DRIFT")
    return AkashaEvent.from_payload(
        kind=AkashaEventKind.REQUALIFICATION,
        subject_id=task.capability_id,
        source_receipt_sha256=record["event_id"],
        payload={
            "capability_id": task.capability_id,
            "retained_generation_sha256": task.retained_generation_sha256,
            "status": "REQUALIFICATION_REQUIRED",
            "source_context_event_id": task.context_event_id,
            "source_task_id": task.task_id,
            "source_anchor_ids": list(task.source_anchor_ids),
        },
        source_time=invalidation.source_time,
        effective_time=invalidation.effective_time,
        observed_at=invalidation.observed_at,
        recorded_at=invalidation.recorded_at,
    )


def append_context_requalification(
    path: Path, run_dir: Path, manifest_sha256: str, task, ledger,
) -> int:
    """Idempotently enqueue one accepted context-driven requalification event."""
    event = event_from_context_requalification(
        run_dir, manifest_sha256, task, ledger)
    return int(append_outbox(path, event))


__all__ = (
    "append_context_requalification",
    "event_from_context_requalification",
)
