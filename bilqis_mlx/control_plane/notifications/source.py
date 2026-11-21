"""Project durable C10/Akasha events into the Mission Control notification feed."""
from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType

from bilqis_mlx.mission_control.contracts.model import (
    AuthorityClass, CoverageState, RecordMeta,
)
from bilqis_mlx.mission_control.contracts.notifications import (
    Notification, NotificationKind, NotificationSeverity, NotificationState,
    notification_id_for_source,
)
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.runtime.akasha_outbox import AkashaEvent, AkashaEventKind, read_outbox


_RULES = MappingProxyType({
    AkashaEventKind.CAPABILITY_GRADUATION: (
        NotificationKind.GRADUATION, NotificationSeverity.SUCCESS,
        "assessment_receipt_sha256",
    ),
    AkashaEventKind.MATERIALIZATION: (
        NotificationKind.GRAPH_MATERIALIZATION, NotificationSeverity.INFO,
        "materialization_receipt_sha256",
    ),
    AkashaEventKind.FACTORY_RELEASE: (
        NotificationKind.FACTORY_RELEASE, NotificationSeverity.SUCCESS,
        "admission_receipt_sha256",
    ),
    AkashaEventKind.REQUALIFICATION: (
        NotificationKind.BLOCKER, NotificationSeverity.BLOCKER,
        None,
    ),
    AkashaEventKind.PROCESS_FAULT: (
        NotificationKind.FAILURE, NotificationSeverity.WARNING,
        None,
    ),
})


def _event_time(event: AkashaEvent) -> int | None:
    return next((
        value for value in (
            event.recorded_at, event.observed_at,
            event.effective_time, event.source_time,
        )
        if type(value) is int
    ), None)


def notification_from_akasha_event(event: AkashaEvent) -> Notification | None:
    """Derive a bounded notice from one validated durable event."""
    if not isinstance(event, AkashaEvent):
        raise TypeError("AKASHA_EVENT_REQUIRED")
    event.validate()
    rule = _RULES.get(event.kind)
    created_at = _event_time(event)
    payload = json.loads(event.payload_json)
    if event.kind is AkashaEventKind.REVALIDATION:
        rule = (
            (NotificationKind.GATE_TRANSITION, NotificationSeverity.INFO, None)
            if payload.get("eligible") is True
            else (NotificationKind.DRIFT, NotificationSeverity.WARNING, None)
        )
    if rule is None or created_at is None:
        return None
    kind, severity, evidence_field = rule
    evidence_ref = (
        payload.get(evidence_field) if evidence_field is not None else None
    ) or event.source_receipt_sha256
    if not isinstance(evidence_ref, str) or not evidence_ref:
        return None
    source_event_id = f"akasha:{event.event_id}"
    notification_id = notification_id_for_source(source_event_id)
    return Notification(
        meta=RecordMeta(
            record_id=notification_id,
            run=None,
            materialized_at=created_at,
            observed_at=event.observed_at,
            as_of=event.effective_time,
            coverage=CoverageState.COMPLETE,
            authority=AuthorityClass.DERIVED,
            source_refs=(f"akasha-event:{event.event_id}",),
            evidence_refs=(evidence_ref,),
            receipt_refs=(event.source_receipt_sha256,),
        ),
        notification_id=notification_id,
        source_event_id=source_event_id,
        subject_ref=event.subject_id,
        kind=kind,
        severity=severity,
        state=NotificationState.ACTIVE,
        created_at=created_at,
        evidence_ref=evidence_ref,
        acknowledged_at=None,
        supersedes_notification_id=None,
    )


def sync_akasha_notifications(
    run_dir: Path, projection: MissionControlProjection,
) -> int:
    """Idempotently import noteworthy durable events from the governed C10 outbox."""
    outbox = Path(run_dir) / "akasha-outbox.sqlite3"
    imported = 0
    for event in read_outbox(outbox):
        notification = notification_from_akasha_event(event)
        if notification is None:
            continue
        projection.ingest_notification(notification)
        imported += 1
    return imported


__all__ = ("notification_from_akasha_event", "sync_akasha_notifications")
