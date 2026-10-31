"""Immutable learned-support, source-task and projection-invalidation contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .atlas_correction_branches import _identity, _canonical_names
from .atlas_revalidation import CorrectionEvent, _digest, _invalid, _name

CAPABILITY_SUPPORT_SCHEMA = "bilqis.c09.capability-support/v1"
TARGETED_SOURCE_TASK_SCHEMA = "bilqis.c09.targeted-source-task/v1"
C10_INTENT_SCHEMA = "bilqis.c09.c10-invalidation-intent/v1"
REQUALIFICATION_LEDGER_SCHEMA = "bilqis.c09.requalification-ledger/v1"
REQUALIFICATION_UPDATE_SCHEMA = "bilqis.c09.requalification-update/v1"


class RequalificationStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    REQUALIFICATION_REQUIRED = "REQUALIFICATION_REQUIRED"


@dataclass(frozen=True)
class CapabilitySupport:
    capability_id: str
    support_artifact_ids: tuple[str, ...]
    source_anchor_ids: tuple[str, ...]
    retained_generation_sha256: str
    observation_ids: tuple[str, ...]
    status: RequalificationStatus
    schema_version: str = CAPABILITY_SUPPORT_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.capability_id)
                or not _canonical_names(self.support_artifact_ids)
                or not _canonical_names(self.source_anchor_ids)
                or not _digest(self.retained_generation_sha256)
                or not _canonical_names(self.observation_ids)
                or not isinstance(self.status, RequalificationStatus)
                or self.schema_version != CAPABILITY_SUPPORT_SCHEMA):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_INVALID")


@dataclass(frozen=True)
class TargetedSourceTask:
    task_id: str
    capability_id: str
    source_anchor_ids: tuple[str, ...]
    correction_event_id: str
    retained_generation_sha256: str
    reason_code: str = "SUPPORT_REQUALIFICATION"
    schema_version: str = TARGETED_SOURCE_TASK_SCHEMA

    def __post_init__(self) -> None:
        identity = {
            "capability_id": self.capability_id,
            "source_anchor_ids": self.source_anchor_ids,
            "correction_event_id": self.correction_event_id,
            "retained_generation_sha256": self.retained_generation_sha256,
        }
        if (not _digest(self.task_id) or not _name(self.capability_id)
                or not _canonical_names(self.source_anchor_ids)
                or not _name(self.correction_event_id)
                or not _digest(self.retained_generation_sha256)
                or self.reason_code != "SUPPORT_REQUALIFICATION"
                or self.task_id != _identity(identity)
                or self.schema_version != TARGETED_SOURCE_TASK_SCHEMA):
            _invalid("BAMF_C09_SOURCE_TASK_INVALID")

    @classmethod
    def from_support(
        cls, support: CapabilitySupport, event: CorrectionEvent,
    ) -> "TargetedSourceTask":
        identity = {
            "capability_id": support.capability_id,
            "source_anchor_ids": support.source_anchor_ids,
            "correction_event_id": event.event_id,
            "retained_generation_sha256": support.retained_generation_sha256,
        }
        return cls(
            task_id=_identity(identity),
            capability_id=support.capability_id,
            source_anchor_ids=support.source_anchor_ids,
            correction_event_id=event.event_id,
            retained_generation_sha256=support.retained_generation_sha256,
        )


@dataclass(frozen=True)
class C10InvalidationIntent:
    event_id: str
    payload_digest: str
    correction_event_id: str
    source_receipt_sha256: str
    affected_artifact_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    namespace: str = "bamf.c09.requalification"
    delivery_state: str = "PENDING_C10"
    schema_version: str = C10_INTENT_SCHEMA

    def __post_init__(self) -> None:
        payload = {
            "correction_event_id": self.correction_event_id,
            "source_receipt_sha256": self.source_receipt_sha256,
            "affected_artifact_ids": self.affected_artifact_ids,
            "capability_ids": self.capability_ids,
            "namespace": self.namespace,
        }
        if (not _digest(self.event_id) or not _digest(self.payload_digest)
                or not _name(self.correction_event_id)
                or not _digest(self.source_receipt_sha256)
                or not _canonical_names(self.affected_artifact_ids)
                or not _canonical_names(self.capability_ids)
                or self.namespace != "bamf.c09.requalification"
                or self.delivery_state != "PENDING_C10"
                or self.payload_digest != _identity(payload)
                or self.event_id != _identity({
                    "kind": "C09_INVALIDATION", **payload})
                or self.schema_version != C10_INTENT_SCHEMA):
            _invalid("BAMF_C09_C10_INTENT_INVALID")

    @classmethod
    def from_correction(
        cls, event: CorrectionEvent,
        affected_artifact_ids: tuple[str, ...],
        capability_ids: tuple[str, ...],
    ) -> "C10InvalidationIntent":
        payload = {
            "correction_event_id": event.event_id,
            "source_receipt_sha256": event.source_receipt_sha256,
            "affected_artifact_ids": affected_artifact_ids,
            "capability_ids": capability_ids,
            "namespace": "bamf.c09.requalification",
        }
        return cls(
            event_id=_identity({"kind": "C09_INVALIDATION", **payload}),
            payload_digest=_identity(payload),
            correction_event_id=event.event_id,
            source_receipt_sha256=event.source_receipt_sha256,
            affected_artifact_ids=affected_artifact_ids,
            capability_ids=capability_ids,
        )


@dataclass(frozen=True)
class RequalificationLedger:
    capabilities: tuple[CapabilitySupport, ...]
    historical: tuple[CapabilitySupport, ...] = ()
    pending_source_tasks: tuple[TargetedSourceTask, ...] = ()
    pending_c10_intents: tuple[C10InvalidationIntent, ...] = ()
    schema_version: str = REQUALIFICATION_LEDGER_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.capabilities, tuple)
                or any(not isinstance(item, CapabilitySupport)
                       for item in self.capabilities)
                or self.capabilities != tuple(sorted(
                    self.capabilities, key=lambda item: item.capability_id))
                or len({item.capability_id for item in self.capabilities})
                != len(self.capabilities)
                or any(not isinstance(item, CapabilitySupport)
                       for item in self.historical)
                or any(not isinstance(item, TargetedSourceTask)
                       for item in self.pending_source_tasks)
                or any(not isinstance(item, C10InvalidationIntent)
                       for item in self.pending_c10_intents)
                or self.pending_source_tasks != tuple(sorted(
                    self.pending_source_tasks, key=lambda item: item.task_id))
                or len({item.task_id for item in self.pending_source_tasks})
                != len(self.pending_source_tasks)
                or self.pending_c10_intents != tuple(sorted(
                    self.pending_c10_intents, key=lambda item: item.event_id))
                or len({item.event_id for item in self.pending_c10_intents})
                != len(self.pending_c10_intents)
                or self.schema_version != REQUALIFICATION_LEDGER_SCHEMA):
            _invalid("BAMF_C09_REQUALIFICATION_LEDGER_INVALID")

    def capability(self, capability_id: str) -> CapabilitySupport:
        for support in self.capabilities:
            if support.capability_id == capability_id:
                return support
        _invalid("BAMF_C09_CAPABILITY_UNKNOWN")


@dataclass(frozen=True)
class RequalificationUpdate:
    ledger: RequalificationLedger
    affected_capability_ids: tuple[str, ...]
    new_source_tasks: tuple[TargetedSourceTask, ...]
    new_c10_intents: tuple[C10InvalidationIntent, ...]
    schema_version: str = REQUALIFICATION_UPDATE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.ledger, RequalificationLedger)
                or not _canonical_names(
                    self.affected_capability_ids, nonempty=False)
                or any(not isinstance(item, TargetedSourceTask)
                       for item in self.new_source_tasks)
                or any(not isinstance(item, C10InvalidationIntent)
                       for item in self.new_c10_intents)
                or self.schema_version != REQUALIFICATION_UPDATE_SCHEMA):
            _invalid("BAMF_C09_REQUALIFICATION_UPDATE_INVALID")
