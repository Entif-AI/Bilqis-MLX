"""Persistent derived operator notifications over immutable source events."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib
from types import MappingProxyType

from ..envelopes import EventEnvelope
from ..model import (
    AuthorityClass, RecordMeta, WireRecord, is_name, is_time, require,
)


class NotificationKind(StrEnum):
    GRADUATION = "GRADUATION"
    PROMOTION = "PROMOTION"
    SEMANTIC_RELEASE = "SEMANTIC_RELEASE"
    FACTORY_RELEASE = "FACTORY_RELEASE"
    GRAPH_MATERIALIZATION = "GRAPH_MATERIALIZATION"
    GATE_TRANSITION = "GATE_TRANSITION"
    BLOCKER = "BLOCKER"
    DRIFT = "DRIFT"
    FAILURE = "FAILURE"


class NotificationSeverity(StrEnum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    BLOCKER = "BLOCKER"


class NotificationState(StrEnum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class Notification(WireRecord):
    """A rebuildable operator-facing projection; it never owns source truth."""

    SCHEMA = "bilqis.bamf.mission-control.notification/v1"
    RUN_BOUND = False

    meta: RecordMeta
    notification_id: str
    source_event_id: str
    subject_ref: str
    kind: NotificationKind
    severity: NotificationSeverity
    state: NotificationState
    created_at: int
    evidence_ref: str
    acknowledged_at: int | None
    supersedes_notification_id: str | None

    def __post_init__(self) -> None:
        super().__post_init__()
        require(all(is_name(value) for value in (
            self.notification_id, self.source_event_id, self.subject_ref,
            self.evidence_ref,
        )), "NOTIFICATION_IDENTITY")
        require(type(self.kind) is NotificationKind, "NOTIFICATION_KIND")
        require(type(self.severity) is NotificationSeverity, "NOTIFICATION_SEVERITY")
        require(type(self.state) is NotificationState, "NOTIFICATION_STATE")
        require(is_time(self.created_at), "NOTIFICATION_CREATED_AT")
        require(self.created_at <= self.meta.materialized_at, "NOTIFICATION_CREATED_FUTURE")
        require(self.acknowledged_at is None or (
            is_time(self.acknowledged_at)
            and self.acknowledged_at >= self.created_at
            and self.acknowledged_at <= self.meta.materialized_at
        ), "NOTIFICATION_ACKNOWLEDGED_AT")
        require(
            (self.state is NotificationState.ACKNOWLEDGED) ==
            (self.acknowledged_at is not None),
            "NOTIFICATION_ACK_STATE",
        )
        require(
            self.supersedes_notification_id is None
            or (is_name(self.supersedes_notification_id)
                and self.supersedes_notification_id != self.notification_id),
            "NOTIFICATION_SUPERSEDES",
        )


_EVENT_RULES = MappingProxyType({
    "capability.graduated": (NotificationKind.GRADUATION, NotificationSeverity.SUCCESS),
    "grade.promoted": (NotificationKind.PROMOTION, NotificationSeverity.SUCCESS),
    "semantic.release.changed": (NotificationKind.SEMANTIC_RELEASE, NotificationSeverity.SUCCESS),
    "graph.materialized": (NotificationKind.GRAPH_MATERIALIZATION, NotificationSeverity.INFO),
    "qualification.gate.changed": (NotificationKind.GATE_TRANSITION, NotificationSeverity.INFO),
    "blocker.changed": (NotificationKind.BLOCKER, NotificationSeverity.BLOCKER),
    "drift.detected": (NotificationKind.DRIFT, NotificationSeverity.WARNING),
    "warning.failure": (NotificationKind.FAILURE, NotificationSeverity.WARNING),
})
_EVIDENCE_REQUIRED = frozenset({
    NotificationKind.GRADUATION,
    NotificationKind.PROMOTION,
    NotificationKind.SEMANTIC_RELEASE,
    NotificationKind.GRAPH_MATERIALIZATION,
    NotificationKind.GATE_TRANSITION,
})


def notification_from_event(
    event: EventEnvelope, *, supersedes_notification_id: str | None = None,
) -> Notification | None:
    """Project one noteworthy immutable event without upgrading its authority."""
    require(type(event) is EventEnvelope, "NOTIFICATION_EVENT_REQUIRED")
    rule = _EVENT_RULES.get(event.event_family)
    if rule is None:
        return None
    kind, severity = rule
    explicit_evidence = (*event.meta.evidence_refs, *event.meta.receipt_refs)
    if kind in _EVIDENCE_REQUIRED and not explicit_evidence:
        return None
    evidence_ref = explicit_evidence[0] if explicit_evidence else event.payload_ref
    notification_id = notification_id_for_source(event.event_id)
    created_at = (
        event.meta.observed_at
        if event.meta.observed_at is not None
        else event.meta.materialized_at
    )
    return Notification(
        meta=RecordMeta(
            record_id=notification_id,
            run=event.meta.run,
            materialized_at=event.meta.materialized_at,
            observed_at=event.meta.observed_at,
            as_of=event.meta.as_of,
            coverage=event.meta.coverage,
            authority=AuthorityClass.DERIVED,
            source_refs=(event.meta.record_id,),
            evidence_refs=(evidence_ref,),
            receipt_refs=event.meta.receipt_refs,
        ),
        notification_id=notification_id,
        source_event_id=event.event_id,
        subject_ref=event.payload_record_id,
        kind=kind,
        severity=severity,
        state=NotificationState.ACTIVE,
        created_at=created_at,
        evidence_ref=evidence_ref,
        acknowledged_at=None,
        supersedes_notification_id=supersedes_notification_id,
    )


def notification_id_for_source(source_event_id: str) -> str:
    require(is_name(source_event_id), "NOTIFICATION_SOURCE_EVENT_ID")
    return "notification:" + hashlib.sha256(
        source_event_id.encode("utf-8")).hexdigest()


def acknowledge_notification(notification: Notification, acknowledged_at: int) -> Notification:
    require(type(notification) is Notification, "NOTIFICATION_REQUIRED")
    require(notification.state is NotificationState.ACTIVE, "NOTIFICATION_NOT_ACTIVE")
    require(
        is_time(acknowledged_at)
        and acknowledged_at >= notification.created_at
        and acknowledged_at > notification.meta.materialized_at,
        "NOTIFICATION_ACK_TIME",
    )
    return replace(
        notification,
        meta=replace(notification.meta, materialized_at=acknowledged_at),
        state=NotificationState.ACKNOWLEDGED,
        acknowledged_at=acknowledged_at,
    )


def supersede_notification(notification: Notification, materialized_at: int) -> Notification:
    require(type(notification) is Notification, "NOTIFICATION_REQUIRED")
    require(notification.state is NotificationState.ACTIVE, "NOTIFICATION_NOT_ACTIVE")
    require(
        is_time(materialized_at) and materialized_at > notification.meta.materialized_at,
        "NOTIFICATION_SUPERSEDE_TIME",
    )
    return replace(
        notification,
        meta=replace(notification.meta, materialized_at=materialized_at),
        state=NotificationState.SUPERSEDED,
    )
