"""C09 lazy-revalidation task, transition, queue and progress records."""
from __future__ import annotations
from dataclasses import dataclass
from ..semantics.cognitive_dependencies import ArtifactNode, DependencyIndex, DependencyRef
from ._revalidation_base import (
    MAX_REVALIDATION_PRIORITY, REVALIDATED_ARTIFACT_SCHEMA,
    REVALIDATION_PROGRESS_SCHEMA, REVALIDATION_QUEUE_SCHEMA,
    REVALIDATION_TASK_SCHEMA, STATE_TRANSITION_SCHEMA,
    _ED25519_SIGNATURE, _canonical_bytes, _digest, _invalid, _name,
    _refs_payload,
)
from ._revalidation_events import CorrectionEvent, RevalidatedArtifact

@dataclass(frozen=True)
class RevalidationTask:
    artifact_id: str
    exigency: int
    impact: int
    cause: DependencyRef
    schema_version: str = REVALIDATION_TASK_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.artifact_id)
                or any(type(value) is not int
                       or not 0 <= value <= MAX_REVALIDATION_PRIORITY
                       for value in (self.exigency, self.impact))
                or not isinstance(self.cause, DependencyRef)
                or self.schema_version != REVALIDATION_TASK_SCHEMA):
            _invalid("BAMF_C09_REVALIDATION_TASK_INVALID")


@dataclass(frozen=True)
class StateTransition:
    artifact_id: str
    previous_content_digest: str
    new_content_digest: str
    previous_eligible: bool
    new_eligible: bool
    source_receipt_sha256: str
    correction_event_id: str
    correction_receipt_sha256: str
    source_owner: str
    source_signature_hex: str
    immediate_dependencies: tuple[DependencyRef, ...]
    changed: bool
    schema_version: str = STATE_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        actual_change = (
            self.previous_content_digest != self.new_content_digest
            or self.previous_eligible != self.new_eligible)
        if (not _name(self.artifact_id)
                or not all(_digest(value) for value in (
                    self.previous_content_digest, self.new_content_digest,
                    self.source_receipt_sha256))
                or type(self.previous_eligible) is not bool
                or type(self.new_eligible) is not bool
                or type(self.changed) is not bool
                or self.changed != actual_change
                or not _name(self.source_owner)
                or not _name(self.correction_event_id)
                or not _digest(self.correction_receipt_sha256)
                or not isinstance(self.source_signature_hex, str)
                or not _ED25519_SIGNATURE.fullmatch(self.source_signature_hex)
                or not isinstance(self.immediate_dependencies, tuple)
                or self.immediate_dependencies != tuple(
                    sorted(set(self.immediate_dependencies)))
                or self.schema_version != STATE_TRANSITION_SCHEMA):
            _invalid("BAMF_C09_STATE_TRANSITION_INVALID")

    def revalidated_signing_bytes(self) -> bytes:
        return _canonical_bytes({
            "schema_version": REVALIDATED_ARTIFACT_SCHEMA,
            "artifact_id": self.artifact_id,
            "immediate_dependencies": _refs_payload(
                self.immediate_dependencies),
            "content_digest": self.new_content_digest,
            "eligible": self.new_eligible,
            "source_receipt_sha256": self.source_receipt_sha256,
            "correction_event_id": self.correction_event_id,
            "correction_receipt_sha256": self.correction_receipt_sha256,
            "source_owner": self.source_owner,
        })


def _sort_tasks(tasks: tuple[RevalidationTask, ...]) -> tuple[RevalidationTask, ...]:
    return tuple(sorted(
        tasks,
        key=lambda task: (-task.exigency, -task.impact, task.artifact_id),
    ))


@dataclass(frozen=True)
class RevalidationQueue:
    event: CorrectionEvent
    pending: tuple[RevalidationTask, ...]
    held_artifact_ids: tuple[str, ...]
    history: tuple[StateTransition, ...] = ()
    schema_version: str = REVALIDATION_QUEUE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.event, CorrectionEvent)
                or not isinstance(self.pending, tuple)
                or any(not isinstance(task, RevalidationTask)
                       for task in self.pending)
                or self.pending != _sort_tasks(self.pending)
                or len({task.artifact_id for task in self.pending})
                != len(self.pending)
                or self.held_artifact_ids != tuple(
                    sorted(task.artifact_id for task in self.pending))
                or not isinstance(self.history, tuple)
                or any(not isinstance(item, StateTransition)
                       for item in self.history)
                or self.schema_version != REVALIDATION_QUEUE_SCHEMA):
            _invalid("BAMF_C09_REVALIDATION_QUEUE_INVALID")


@dataclass(frozen=True)
class RevalidationProgress:
    index: DependencyIndex
    queue: RevalidationQueue
    schema_version: str = REVALIDATION_PROGRESS_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.index, DependencyIndex)
                or not isinstance(self.queue, RevalidationQueue)
                or self.schema_version != REVALIDATION_PROGRESS_SCHEMA):
            _invalid("BAMF_C09_REVALIDATION_PROGRESS_INVALID")


def _task(node: ArtifactNode, cause: DependencyRef) -> RevalidationTask:
    return RevalidationTask(
        node.artifact_id, node.exigency, node.impact, cause)
