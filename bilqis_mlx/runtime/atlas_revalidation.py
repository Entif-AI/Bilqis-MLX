"""Pure C09.1 correction holds and lazy, direct-edge revalidation.

Source owners supply qualified immutable corrections and re-evaluation
receipts. No source right, neural generation or checkpoint is mutated here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from graphlib import CycleError, TopologicalSorter
import hashlib
import json
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


# C09.2 preserves incompatible corrections as alternative source branches.
CORRECTION_BRANCH_SCHEMA = "bilqis.c09.correction-branch/v1"
CORRECTION_BRANCHES_SCHEMA = "bilqis.c09.correction-branches/v1"
CAPABILITY_SUPPORT_SCHEMA = "bilqis.c09.capability-support/v1"
TARGETED_SOURCE_TASK_SCHEMA = "bilqis.c09.targeted-source-task/v1"
C10_INTENT_SCHEMA = "bilqis.c09.c10-invalidation-intent/v1"
REQUALIFICATION_LEDGER_SCHEMA = "bilqis.c09.requalification-ledger/v1"
REQUALIFICATION_UPDATE_SCHEMA = "bilqis.c09.requalification-update/v1"


def _identity(value: object) -> str:
    return hashlib.sha256(
        (json.dumps(value, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ).hexdigest()


def _canonical_names(names: object, *, nonempty: bool = True) -> bool:
    return (isinstance(names, tuple)
            and (bool(names) or not nonempty)
            and all(_name(item) for item in names)
            and names == tuple(sorted(set(names))))


@dataclass(frozen=True)
class CorrectionBranch:
    event: CorrectionEvent
    supersedes_event_ids: tuple[str, ...] = ()
    schema_version: str = CORRECTION_BRANCH_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.event, CorrectionEvent)
                or not _canonical_names(
                    self.supersedes_event_ids, nonempty=False)
                or self.event.event_id in self.supersedes_event_ids
                or self.schema_version != CORRECTION_BRANCH_SCHEMA):
            _invalid("BAMF_C09_CORRECTION_BRANCH_INVALID")


@dataclass(frozen=True)
class CorrectionBranches:
    dependency: DependencyRef
    branches: tuple[CorrectionBranch, ...]
    schema_version: str = CORRECTION_BRANCHES_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.dependency, DependencyRef)
                or not isinstance(self.branches, tuple)
                or any(not isinstance(branch, CorrectionBranch)
                       or branch.event.dependency != self.dependency
                       for branch in self.branches)
                or self.branches != tuple(sorted(
                    self.branches, key=lambda branch: branch.event.event_id))
                or len({branch.event.event_id for branch in self.branches})
                != len(self.branches)
                or self.schema_version != CORRECTION_BRANCHES_SCHEMA):
            _invalid("BAMF_C09_CORRECTION_BRANCHES_INVALID")
        identifiers = {branch.event.event_id for branch in self.branches}
        if any(not set(branch.supersedes_event_ids).issubset(identifiers)
               for branch in self.branches):
            _invalid("BAMF_C09_CORRECTION_SUPERSESSION_UNKNOWN")
        try:
            tuple(TopologicalSorter({
                branch.event.event_id: branch.supersedes_event_ids
                for branch in self.branches
            }).static_order())
        except CycleError:
            _invalid("BAMF_C09_CORRECTION_SUPERSESSION_CYCLE")

    @property
    def active(self) -> tuple[CorrectionBranch, ...]:
        superseded = {
            event_id for branch in self.branches
            for event_id in branch.supersedes_event_ids
        }
        return tuple(branch for branch in self.branches
                     if branch.event.event_id not in superseded)


def add_correction(
    branches: CorrectionBranches,
    event: CorrectionEvent,
    *,
    supersedes_event_ids: tuple[str, ...] = (),
) -> CorrectionBranches:
    if (not isinstance(branches, CorrectionBranches)
            or not isinstance(event, CorrectionEvent)
            or event.dependency != branches.dependency):
        _invalid("BAMF_C09_CORRECTION_BRANCH_ARGUMENT_INVALID")
    proposed = CorrectionBranch(event, supersedes_event_ids)
    prior = next((branch for branch in branches.branches
                  if branch.event.event_id == event.event_id), None)
    if prior is not None:
        if prior != proposed:
            _invalid("BAMF_C09_CORRECTION_EVENT_ID_CONFLICT")
        return branches
    return CorrectionBranches(
        branches.dependency,
        tuple(sorted((*branches.branches, proposed),
                     key=lambda branch: branch.event.event_id)),
    )


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


def _support_impacted_artifacts(
    support: CapabilitySupport,
    index: DependencyIndex,
    impacted_ids: set[str],
) -> tuple[str, ...]:
    unseen = list(support.support_artifact_ids)
    visited: set[str] = set()
    found: set[str] = set()
    while unseen:
        artifact_id = unseen.pop()
        if artifact_id in visited:
            continue
        visited.add(artifact_id)
        node = index.node(artifact_id)
        if artifact_id in impacted_ids:
            found.add(artifact_id)
        unseen.extend(ref.key for ref in node.immediate_dependencies
                      if ref.kind is DependencyKind.ARTIFACT)
    return tuple(sorted(found))


def mark_affected_capabilities(
    ledger: RequalificationLedger,
    index: DependencyIndex,
    queue: RevalidationQueue,
) -> RequalificationUpdate:
    """Keep retained neural history intact; request fresh source requalification."""
    if (not isinstance(ledger, RequalificationLedger)
            or not isinstance(index, DependencyIndex)
            or not isinstance(queue, RevalidationQueue)):
        _invalid("BAMF_C09_REQUALIFICATION_ARGUMENT_INVALID")
    impacted_ids = set(queue.held_artifact_ids)
    impacted_ids.update(
        transition.artifact_id for transition in queue.history
        if transition.changed)
    support_paths = {
        support.capability_id: _support_impacted_artifacts(
            support, index, impacted_ids)
        for support in ledger.capabilities
    }
    affected = tuple(
        support for support in ledger.capabilities
        if support_paths[support.capability_id])
    affected_ids = tuple(item.capability_id for item in affected)
    affected_artifacts = tuple(sorted({
        artifact_id for support in affected
        for artifact_id in support_paths[support.capability_id]
    }))
    updated = tuple(
        replace(support, status=RequalificationStatus.REQUALIFICATION_REQUIRED)
        if support in affected else support
        for support in ledger.capabilities
    )
    prior_history = tuple(
        support for support in affected
        if support.status is RequalificationStatus.QUALIFIED)
    existing_tasks = {item.task_id for item in ledger.pending_source_tasks}
    proposed_tasks = tuple(
        TargetedSourceTask.from_support(support, queue.event)
        for support in affected)
    new_tasks = tuple(item for item in proposed_tasks
                      if item.task_id not in existing_tasks)
    new_intents: tuple[C10InvalidationIntent, ...] = ()
    if affected:
        intent = C10InvalidationIntent.from_correction(
            queue.event, affected_artifacts, affected_ids)
        if all(item.event_id != intent.event_id
               for item in ledger.pending_c10_intents):
            new_intents = (intent,)
    next_ledger = RequalificationLedger(
        capabilities=updated,
        historical=(*ledger.historical, *prior_history),
        pending_source_tasks=tuple(sorted(
            (*ledger.pending_source_tasks, *new_tasks),
            key=lambda item: item.task_id)),
        pending_c10_intents=tuple(sorted(
            (*ledger.pending_c10_intents, *new_intents),
            key=lambda item: item.event_id)),
    )
    return RequalificationUpdate(
        next_ledger, affected_ids, new_tasks, new_intents)
