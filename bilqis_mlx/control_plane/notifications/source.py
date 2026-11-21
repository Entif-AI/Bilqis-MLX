"""Project durable C10/Akasha events into the Mission Control notification feed."""
from __future__ import annotations

import json
from pathlib import Path
import time
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

from ..native_contracts import AuthenticatedGeneration, run_ref
from ..native_custody import authenticated_history


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


def _event_time(event: AkashaEvent, projected_at: int) -> int:
    return next((
        value for value in (
            event.recorded_at, event.observed_at,
            event.effective_time, event.source_time,
        )
        if type(value) is int
    ), projected_at)


def notification_from_akasha_event(
    event: AkashaEvent, *, projected_at: int | None = None,
) -> Notification | None:
    """Derive a bounded notice from one validated durable event."""
    if not isinstance(event, AkashaEvent):
        raise TypeError("AKASHA_EVENT_REQUIRED")
    event.validate()
    rule = _RULES.get(event.kind)
    projection_time = int(time.time()) if projected_at is None else projected_at
    if type(projection_time) is not int or projection_time < 0:
        raise ValueError("NOTIFICATION_PROJECTION_TIME_INVALID")
    created_at = _event_time(event, projection_time)
    payload = json.loads(event.payload_json)
    if event.kind is AkashaEventKind.REVALIDATION:
        rule = (
            (NotificationKind.GATE_TRANSITION, NotificationSeverity.INFO, None)
            if payload.get("eligible") is True
            else (NotificationKind.DRIFT, NotificationSeverity.WARNING, None)
        )
    if rule is None:
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


def notification_from_native_event(
    generation: AuthenticatedGeneration, event: dict, *, projected_at: int,
) -> Notification | None:
    """Derive a promotion notice from an accepted immutable grade-adoption event."""
    if (not isinstance(generation, AuthenticatedGeneration)
            or not isinstance(event, dict)
            or event.get("event") != "SCHOOL_EXECUTION_PROFILE_ADOPTED"
            or event.get("transition_kind") != "APPEND_GRADE"):
        return None
    event_id = event.get("event_id")
    grade = event.get("grade")
    factory_release = event.get("factory_release_sha256")
    if not all(isinstance(value, str) and value for value in (
        event_id, grade, factory_release,
    )):
        return None
    created_at = next((
        event.get(key) for key in (
            "recorded_at", "observed_at", "effective_time", "source_time")
        if type(event.get(key)) is int
    ), projected_at)
    source_event_id = f"native:{event_id}"
    notification_id = notification_id_for_source(source_event_id)
    evidence_ref = f"factory-release:{factory_release}"
    return Notification(
        meta=RecordMeta(
            record_id=notification_id,
            run=run_ref(generation),
            materialized_at=created_at,
            observed_at=event.get("observed_at") if type(event.get("observed_at")) is int else None,
            as_of=event.get("effective_time") if type(event.get("effective_time")) is int else None,
            coverage=CoverageState.COMPLETE,
            authority=AuthorityClass.DERIVED,
            source_refs=(
                f"bamf-manifest:{generation.manifest_sha256}",
                f"native-event:{event_id}",
            ),
            evidence_refs=(evidence_ref,),
            receipt_refs=(generation.acceptance_sha256,),
        ),
        notification_id=notification_id,
        source_event_id=source_event_id,
        subject_ref=f"grade:{grade}",
        kind=NotificationKind.PROMOTION,
        severity=NotificationSeverity.SUCCESS,
        state=NotificationState.ACTIVE,
        created_at=created_at,
        evidence_ref=evidence_ref,
        acknowledged_at=None,
        supersedes_notification_id=None,
    )


def notification_from_semantic_release_change(
    generation: AuthenticatedGeneration,
    parent: AuthenticatedGeneration | None,
    *, projected_at: int,
) -> Notification | None:
    """Project a semantic release only when accepted lineage proves a release change."""
    current = run_ref(generation)
    previous = run_ref(parent) if parent is not None else None
    if previous is not None and previous.semantic_release_sha256 == current.semantic_release_sha256:
        return None
    source_event_id = f"native-semantic-release:{generation.manifest_sha256}"
    notification_id = notification_id_for_source(source_event_id)
    evidence_ref = f"semantic-release:{current.semantic_release_sha256}"
    return Notification(
        meta=RecordMeta(
            record_id=notification_id,
            run=current,
            materialized_at=projected_at,
            observed_at=None,
            as_of=None,
            coverage=CoverageState.COMPLETE,
            authority=AuthorityClass.DERIVED,
            source_refs=(f"bamf-manifest:{generation.manifest_sha256}",),
            evidence_refs=(evidence_ref,),
            receipt_refs=(generation.acceptance_sha256,),
        ),
        notification_id=notification_id,
        source_event_id=source_event_id,
        subject_ref=evidence_ref,
        kind=NotificationKind.SEMANTIC_RELEASE,
        severity=NotificationSeverity.SUCCESS,
        state=NotificationState.ACTIVE,
        created_at=projected_at,
        evidence_ref=evidence_ref,
        acknowledged_at=None,
        supersedes_notification_id=None,
    )


def sync_akasha_notifications(
    run_dir: Path, projection: MissionControlProjection, *, projected_at: int | None = None,
) -> int:
    """Idempotently import noteworthy durable events from the governed C10 outbox."""
    outbox = Path(run_dir) / "akasha-outbox.sqlite3"
    imported = 0
    now = int(time.time()) if projected_at is None else projected_at
    for event in read_outbox(outbox):
        notification = notification_from_akasha_event(event, projected_at=now)
        if notification is None:
            continue
        projection.ingest_notification(notification)
        imported += 1
    return imported


def sync_native_transition_notifications(
    run_dir: Path, projection: MissionControlProjection, *, projected_at: int | None = None,
) -> int:
    """Import accepted native grade-promotion transitions without mutating source custody."""
    now = int(time.time()) if projected_at is None else projected_at
    imported = 0
    parent = None
    for generation in authenticated_history(Path(run_dir)):
        release_notice = notification_from_semantic_release_change(
            generation, parent, projected_at=now)
        if release_notice is not None:
            projection.ingest_notification(release_notice)
            imported += 1
        for event in generation.outbox:
            notification = notification_from_native_event(
                generation, event, projected_at=now)
            if notification is None:
                continue
            projection.ingest_notification(notification)
            imported += 1
        parent = generation
    return imported


__all__ = (
    "notification_from_akasha_event", "notification_from_native_event",
    "notification_from_semantic_release_change",
    "sync_akasha_notifications", "sync_native_transition_notifications",
)
