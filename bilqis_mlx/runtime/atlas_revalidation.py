"""Pure C09.1 correction holds and lazy, direct-edge revalidation.

Source owners supply qualified immutable corrections and re-evaluation
receipts. No source right, neural generation or checkpoint is mutated here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from ..errors import ErrorBus, SCHOOL
from ..semantics.cognitive_dependencies import (
    ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)


CORRECTION_EVENT_SCHEMA = "bilqis.c09.correction-event/v1"
REVALIDATED_ARTIFACT_SCHEMA = "bilqis.c09.revalidated-artifact/v1"
REVALIDATION_FRONTIER_SCHEMA = "bilqis.c09.revalidation-frontier/v1"
REVALIDATION_TASK_SCHEMA = "bilqis.c09.revalidation-task/v1"
REVALIDATION_QUEUE_SCHEMA = "bilqis.c09.revalidation-queue/v1"
STATE_TRANSITION_SCHEMA = "bilqis.c09.state-transition/v1"
REVALIDATION_PROGRESS_SCHEMA = "bilqis.c09.revalidation-progress/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_REVALIDATION.INVALID, reason=reason)


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _digest(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _time(value: object) -> bool:
    return type(value) is int and value >= 0


@dataclass(frozen=True)
class CorrectionEvent:
    event_id: str
    dependency: DependencyRef
    source_owner: str
    source_receipt_sha256: str
    old_evidence_sha256: str
    new_evidence_sha256: str
    source_time: int
    effective_time: int
    observed_at: int
    recorded_at: int
    reason_code: str
    schema_version: str = CORRECTION_EVENT_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.event_id)
                or not isinstance(self.dependency, DependencyRef)
                or not _name(self.source_owner)
                or not all(_digest(value) for value in (
                    self.source_receipt_sha256, self.old_evidence_sha256,
                    self.new_evidence_sha256))
                or not all(_time(value) for value in (
                    self.source_time, self.effective_time,
                    self.observed_at, self.recorded_at))
                or not _name(self.reason_code)
                or self.schema_version != CORRECTION_EVENT_SCHEMA):
            _invalid("BAMF_C09_CORRECTION_EVENT_INVALID")


@dataclass(frozen=True)
class RevalidatedArtifact:
    artifact_id: str
    immediate_dependencies: tuple[DependencyRef, ...]
    content_digest: str
    eligible: bool
    source_receipt_sha256: str
    schema_version: str = REVALIDATED_ARTIFACT_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.artifact_id)
                or not isinstance(self.immediate_dependencies, tuple)
                or any(not isinstance(ref, DependencyRef)
                       for ref in self.immediate_dependencies)
                or self.immediate_dependencies != tuple(
                    sorted(set(self.immediate_dependencies)))
                or not _digest(self.content_digest)
                or type(self.eligible) is not bool
                or not _digest(self.source_receipt_sha256)
                or self.schema_version != REVALIDATED_ARTIFACT_SCHEMA):
            _invalid("BAMF_C09_REVALIDATED_ARTIFACT_INVALID")


@dataclass(frozen=True)
class RevalidationFrontier:
    results: tuple[RevalidatedArtifact, ...]
    schema_version: str = REVALIDATION_FRONTIER_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.results, tuple)
                or any(not isinstance(item, RevalidatedArtifact)
                       for item in self.results)
                or self.results != tuple(
                    sorted(self.results, key=lambda item: item.artifact_id))
                or len({item.artifact_id for item in self.results})
                != len(self.results)
                or self.schema_version != REVALIDATION_FRONTIER_SCHEMA):
            _invalid("BAMF_C09_REVALIDATION_FRONTIER_INVALID")


@dataclass(frozen=True)
class RevalidationTask:
    artifact_id: str
    exigency: int
    impact: int
    cause: DependencyRef
    schema_version: str = REVALIDATION_TASK_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.artifact_id)
                or any(type(value) is not int or not 0 <= value <= 4
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
                or self.schema_version != STATE_TRANSITION_SCHEMA):
            _invalid("BAMF_C09_STATE_TRANSITION_INVALID")


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


def apply_correction(
    event: CorrectionEvent, dependency_index: DependencyIndex,
) -> RevalidationQueue:
    """Hold only direct consumers of a qualified correction, before readout."""
    if (not isinstance(event, CorrectionEvent)
            or not isinstance(dependency_index, DependencyIndex)):
        _invalid("BAMF_C09_CORRECTION_ARGUMENT_INVALID")
    tasks = _sort_tasks(tuple(
        _task(node, event.dependency)
        for node in dependency_index.direct_dependents(event.dependency)))
    return RevalidationQueue(
        event, tasks, tuple(sorted(task.artifact_id for task in tasks)))


def read_artifact(
    dependency_index: DependencyIndex,
    queue: RevalidationQueue,
    artifact_id: str,
) -> ArtifactNode:
    """Fail closed on pending or source-ineligible materialized state."""
    if (not isinstance(dependency_index, DependencyIndex)
            or not isinstance(queue, RevalidationQueue)):
        _invalid("BAMF_C09_READ_ARGUMENT_INVALID")
    node = dependency_index.node(artifact_id)
    if artifact_id in queue.held_artifact_ids:
        _invalid("BAMF_C09_ARTIFACT_HELD")
    if not node.eligible:
        _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
    # A downstream cache need not be rebuilt until an upstream output
    # changes, but it cannot be *used* while its source chain is held.
    unseen = [node]
    visited: set[str] = set()
    while unseen:
        current = unseen.pop()
        if current.artifact_id in visited:
            continue
        visited.add(current.artifact_id)
        for dependency in current.immediate_dependencies:
            if dependency.kind is not DependencyKind.ARTIFACT:
                continue
            if dependency.key in queue.held_artifact_ids:
                _invalid("BAMF_C09_ARTIFACT_DEPENDENCY_HELD")
            upstream = dependency_index.node(dependency.key)
            if not upstream.eligible:
                _invalid("BAMF_C09_ARTIFACT_DEPENDENCY_INELIGIBLE")
            unseen.append(upstream)
    return node


def next_revalidation_task(
    dependency_index: DependencyIndex, queue: RevalidationQueue,
) -> RevalidationTask | None:
    """Choose the highest-priority task whose upstream holds have cleared."""
    if (not isinstance(dependency_index, DependencyIndex)
            or not isinstance(queue, RevalidationQueue)):
        _invalid("BAMF_C09_REVALIDATION_ARGUMENT_INVALID")
    held = set(queue.held_artifact_ids)
    for task in queue.pending:
        node = dependency_index.node(task.artifact_id)
        if not any(
            ref.kind is DependencyKind.ARTIFACT and ref.key in held
            for ref in node.immediate_dependencies
        ):
            return task
    if queue.pending:
        _invalid("BAMF_C09_REVALIDATION_DEPENDENCY_BLOCKED")
    return None


def revalidate_node(
    node: ArtifactNode, frontier: RevalidationFrontier,
) -> StateTransition:
    """Compare source-owner recomputation to retained immutable materialization."""
    if (not isinstance(node, ArtifactNode)
            or not isinstance(frontier, RevalidationFrontier)):
        _invalid("BAMF_C09_REVALIDATION_ARGUMENT_INVALID")
    candidate = next(
        (item for item in frontier.results
         if item.artifact_id == node.artifact_id), None)
    if candidate is None:
        _invalid("BAMF_C09_REVALIDATION_EVIDENCE_MISSING")
    if candidate.immediate_dependencies != node.immediate_dependencies:
        _invalid("BAMF_C09_REVALIDATION_DEPENDENCY_DRIFT")
    return StateTransition(
        artifact_id=node.artifact_id,
        previous_content_digest=node.content_digest,
        new_content_digest=candidate.content_digest,
        previous_eligible=node.eligible,
        new_eligible=candidate.eligible,
        source_receipt_sha256=candidate.source_receipt_sha256,
        changed=(candidate.content_digest != node.content_digest
                 or candidate.eligible != node.eligible),
    )


def advance_revalidation(
    dependency_index: DependencyIndex,
    queue: RevalidationQueue,
    transition: StateTransition,
) -> RevalidationProgress:
    """Advance one lazy task; propagate only changed content or eligibility."""
    if (not isinstance(dependency_index, DependencyIndex)
            or not isinstance(queue, RevalidationQueue)
            or not isinstance(transition, StateTransition)):
        _invalid("BAMF_C09_REVALIDATION_ARGUMENT_INVALID")
    selected = next_revalidation_task(dependency_index, queue)
    if selected is None or selected.artifact_id != transition.artifact_id:
        _invalid("BAMF_C09_REVALIDATION_OUT_OF_ORDER")
    node = dependency_index.node(transition.artifact_id)
    if (node.content_digest != transition.previous_content_digest
            or node.eligible != transition.previous_eligible):
        _invalid("BAMF_C09_REVALIDATION_STALE_TRANSITION")
    updated = replace(
        node, content_digest=transition.new_content_digest,
        eligible=transition.new_eligible)
    new_index = dependency_index.replace_node(updated)
    pending = [
        task for task in queue.pending
        if task.artifact_id != transition.artifact_id
    ]
    if transition.changed:
        already = {task.artifact_id for task in pending}
        for dependent in new_index.direct_dependents(updated.reference):
            if dependent.artifact_id not in already:
                pending.append(_task(dependent, updated.reference))
                already.add(dependent.artifact_id)
    ordered = _sort_tasks(tuple(pending))
    return RevalidationProgress(
        new_index,
        RevalidationQueue(
            queue.event, ordered,
            tuple(sorted(task.artifact_id for task in ordered)),
            (*queue.history, transition),
        ),
    )
