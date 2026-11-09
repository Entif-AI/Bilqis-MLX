"""Context-specific lazy revalidation without fabricating correction authority."""
from __future__ import annotations

from dataclasses import dataclass, replace

from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.context_eligibility import C09ContextInvalidation

from .atlas_revalidation_common import (
    _ED25519_SIGNATURE, _canonical_bytes, _digest, _invalid, _name,
    _refs_payload,
)
from .atlas_revalidation_queue import RevalidationTask, _sort_tasks, _task
from .atlas_source_authority import SourceAuthorityRegistry


CONTEXT_REVALIDATED_ARTIFACT_SCHEMA = (
    "bilqis.c09.context-revalidated-artifact/v1")
CONTEXT_REVALIDATION_FRONTIER_SCHEMA = (
    "bilqis.c09.context-revalidation-frontier/v1")
CONTEXT_STATE_TRANSITION_SCHEMA = "bilqis.c09.context-state-transition/v1"
CONTEXT_REVALIDATION_QUEUE_SCHEMA = "bilqis.c09.context-revalidation-queue/v1"
CONTEXT_REVALIDATION_PROGRESS_SCHEMA = (
    "bilqis.c09.context-revalidation-progress/v1")


@dataclass(frozen=True)
class ContextRevalidatedArtifact:
    artifact_id: str
    immediate_dependencies: tuple[DependencyRef, ...]
    content_digest: str
    eligible: bool
    source_receipt_sha256: str
    context_event_id: str
    context_invalidation_receipt_sha256: str
    source_owner: str
    source_signature_hex: str
    schema_version: str = CONTEXT_REVALIDATED_ARTIFACT_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.artifact_id)
                or not isinstance(self.immediate_dependencies, tuple)
                or self.immediate_dependencies != tuple(
                    sorted(set(self.immediate_dependencies)))
                or any(not isinstance(ref, DependencyRef)
                       for ref in self.immediate_dependencies)
                or not _digest(self.content_digest)
                or type(self.eligible) is not bool
                or not _digest(self.source_receipt_sha256)
                or not _name(self.context_event_id)
                or not _digest(self.context_invalidation_receipt_sha256)
                or not _name(self.source_owner)
                or not isinstance(self.source_signature_hex, str)
                or not _ED25519_SIGNATURE.fullmatch(self.source_signature_hex)
                or self.schema_version != CONTEXT_REVALIDATED_ARTIFACT_SCHEMA):
            _invalid("BAMF_C09_CONTEXT_REVALIDATED_ARTIFACT_INVALID")

    def signing_bytes(self) -> bytes:
        return _canonical_bytes({
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "immediate_dependencies": _refs_payload(
                self.immediate_dependencies),
            "content_digest": self.content_digest,
            "eligible": self.eligible,
            "source_receipt_sha256": self.source_receipt_sha256,
            "context_event_id": self.context_event_id,
            "context_invalidation_receipt_sha256":
                self.context_invalidation_receipt_sha256,
            "source_owner": self.source_owner,
        })


@dataclass(frozen=True)
class ContextRevalidationFrontier:
    results: tuple[ContextRevalidatedArtifact, ...]
    schema_version: str = CONTEXT_REVALIDATION_FRONTIER_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.results, tuple)
                or not self.results
                or len(self.results) != 1
                or any(not isinstance(item, ContextRevalidatedArtifact)
                       for item in self.results)
                or self.results != tuple(
                    sorted(self.results, key=lambda item: item.artifact_id))
                or len({item.artifact_id for item in self.results})
                != len(self.results)
                or len({item.context_event_id for item in self.results}) != 1
                or len({
                    item.context_invalidation_receipt_sha256
                    for item in self.results
                }) != 1
                or self.schema_version != CONTEXT_REVALIDATION_FRONTIER_SCHEMA):
            _invalid("BAMF_C09_CONTEXT_REVALIDATION_FRONTIER_INVALID")


@dataclass(frozen=True)
class ContextStateTransition:
    artifact_id: str
    previous_content_digest: str
    new_content_digest: str
    previous_eligible: bool
    new_eligible: bool
    previous_dependencies: tuple[DependencyRef, ...]
    new_dependencies: tuple[DependencyRef, ...]
    source_receipt_sha256: str
    context_event_id: str
    context_invalidation_receipt_sha256: str
    source_owner: str
    source_signature_hex: str
    changed: bool
    schema_version: str = CONTEXT_STATE_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        actual_change = (
            self.previous_content_digest != self.new_content_digest
            or self.previous_eligible != self.new_eligible)
        if (not _name(self.artifact_id)
                or not _digest(self.previous_content_digest)
                or not _digest(self.new_content_digest)
                or type(self.previous_eligible) is not bool
                or type(self.new_eligible) is not bool
                or type(self.changed) is not bool
                or self.changed != actual_change
                or any(not isinstance(value, tuple) for value in (
                    self.previous_dependencies, self.new_dependencies))
                or any(
                    deps != tuple(sorted(set(deps)))
                    or any(not isinstance(ref, DependencyRef) for ref in deps)
                    for deps in (
                        self.previous_dependencies, self.new_dependencies))
                or not _digest(self.source_receipt_sha256)
                or not _name(self.context_event_id)
                or not _digest(self.context_invalidation_receipt_sha256)
                or not _name(self.source_owner)
                or not isinstance(self.source_signature_hex, str)
                or not _ED25519_SIGNATURE.fullmatch(self.source_signature_hex)
                or self.schema_version != CONTEXT_STATE_TRANSITION_SCHEMA):
            _invalid("BAMF_C09_CONTEXT_STATE_TRANSITION_INVALID")


@dataclass(frozen=True)
class ContextRevalidationQueue:
    event: C09ContextInvalidation
    accepted_event_id: str
    pending: tuple[RevalidationTask, ...]
    held_artifact_ids: tuple[str, ...]
    history: tuple[ContextStateTransition, ...] = ()
    schema_version: str = CONTEXT_REVALIDATION_QUEUE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.event, C09ContextInvalidation)
                or not _digest(self.accepted_event_id)
                or not isinstance(self.pending, tuple)
                or any(not isinstance(task, RevalidationTask)
                       for task in self.pending)
                or self.pending != _sort_tasks(self.pending)
                or len({task.artifact_id for task in self.pending})
                != len(self.pending)
                or self.held_artifact_ids != tuple(
                    sorted(task.artifact_id for task in self.pending))
                or not isinstance(self.history, tuple)
                or any(not isinstance(item, ContextStateTransition)
                       for item in self.history)
                or self.schema_version != CONTEXT_REVALIDATION_QUEUE_SCHEMA):
            _invalid("BAMF_C09_CONTEXT_REVALIDATION_QUEUE_INVALID")


@dataclass(frozen=True)
class ContextRevalidationProgress:
    index: DependencyIndex
    queue: ContextRevalidationQueue
    schema_version: str = CONTEXT_REVALIDATION_PROGRESS_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.index, DependencyIndex)
                or not isinstance(self.queue, ContextRevalidationQueue)
                or self.schema_version != CONTEXT_REVALIDATION_PROGRESS_SCHEMA):
            _invalid("BAMF_C09_CONTEXT_REVALIDATION_PROGRESS_INVALID")


def apply_context_invalidation(
    event: C09ContextInvalidation,
    accepted_event_id: str,
    dependency_index: DependencyIndex,
) -> ContextRevalidationQueue:
    if (not isinstance(event, C09ContextInvalidation)
            or not _digest(accepted_event_id)
            or not isinstance(dependency_index, DependencyIndex)):
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_ARGUMENT_INVALID")
    cause = DependencyRef(
        DependencyKind.TIME, "time:asof:context:" + event.old_context_digest)
    tasks = _sort_tasks(tuple(
        _task(node, cause)
        for node in dependency_index.direct_dependents(cause)))
    return ContextRevalidationQueue(
        event, accepted_event_id, tasks,
        tuple(sorted(task.artifact_id for task in tasks)))


def next_context_revalidation_task(
    dependency_index: DependencyIndex,
    queue: ContextRevalidationQueue,
) -> RevalidationTask | None:
    if (not isinstance(dependency_index, DependencyIndex)
            or not isinstance(queue, ContextRevalidationQueue)):
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_ARGUMENT_INVALID")
    held = set(queue.held_artifact_ids)
    for task in queue.pending:
        node = dependency_index.node(task.artifact_id)
        unseen = [
            ref.key for ref in node.immediate_dependencies
            if ref.kind is DependencyKind.ARTIFACT
        ]
        visited = set()
        blocked = False
        while unseen:
            ancestor_id = unseen.pop()
            if ancestor_id in visited:
                continue
            visited.add(ancestor_id)
            if ancestor_id in held:
                blocked = True
                break
            ancestor = dependency_index.node(ancestor_id)
            unseen.extend(
                ref.key for ref in ancestor.immediate_dependencies
                if ref.kind is DependencyKind.ARTIFACT)
        if not blocked:
            return task
    if queue.pending:
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_DEPENDENCY_BLOCKED")
    return None


def _expected_context_dependencies(
    node: ArtifactNode, event: C09ContextInvalidation,
) -> tuple[DependencyRef, ...]:
    old_ref = DependencyRef(
        DependencyKind.TIME, "time:asof:context:" + event.old_context_digest)
    if old_ref not in node.immediate_dependencies:
        return node.immediate_dependencies
    values = set(node.immediate_dependencies)
    values.remove(old_ref)
    if event.new_context_digest is not None:
        values.add(DependencyRef(
            DependencyKind.TIME,
            "time:asof:context:" + event.new_context_digest))
    return tuple(sorted(values))


def revalidate_context_node(
    node: ArtifactNode,
    queue: ContextRevalidationQueue,
    frontier: ContextRevalidationFrontier,
    authority_registry: SourceAuthorityRegistry,
) -> ContextStateTransition:
    if (not isinstance(node, ArtifactNode)
            or not isinstance(queue, ContextRevalidationQueue)
            or not isinstance(frontier, ContextRevalidationFrontier)
            or not isinstance(authority_registry, SourceAuthorityRegistry)):
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_ARGUMENT_INVALID")
    candidate = next(
        (item for item in frontier.results
         if item.artifact_id == node.artifact_id), None)
    if candidate is None:
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_EVIDENCE_MISSING")
    if (candidate.context_event_id != queue.event.event_id
            or candidate.context_invalidation_receipt_sha256
            != queue.accepted_event_id):
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_EVENT_MISMATCH")
    expected_dependencies = _expected_context_dependencies(node, queue.event)
    if candidate.immediate_dependencies != expected_dependencies:
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_DEPENDENCY_DRIFT")
    if queue.event.new_context_digest is None and candidate.eligible:
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_ELIGIBILITY_DRIFT")
    authority_registry.verify_detached(
        candidate.source_owner,
        DependencyRef(DependencyKind.ARTIFACT, candidate.artifact_id),
        candidate.source_signature_hex,
        candidate.signing_bytes(),
    )
    return ContextStateTransition(
        artifact_id=node.artifact_id,
        previous_content_digest=node.content_digest,
        new_content_digest=candidate.content_digest,
        previous_eligible=node.eligible,
        new_eligible=candidate.eligible,
        previous_dependencies=node.immediate_dependencies,
        new_dependencies=candidate.immediate_dependencies,
        source_receipt_sha256=candidate.source_receipt_sha256,
        context_event_id=candidate.context_event_id,
        context_invalidation_receipt_sha256=
            candidate.context_invalidation_receipt_sha256,
        source_owner=candidate.source_owner,
        source_signature_hex=candidate.source_signature_hex,
        changed=(candidate.content_digest != node.content_digest
                 or candidate.eligible != node.eligible),
    )


def advance_context_revalidation(
    dependency_index: DependencyIndex,
    queue: ContextRevalidationQueue,
    transition: ContextStateTransition,
) -> ContextRevalidationProgress:
    if (not isinstance(dependency_index, DependencyIndex)
            or not isinstance(queue, ContextRevalidationQueue)
            or not isinstance(transition, ContextStateTransition)):
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_ARGUMENT_INVALID")
    selected = next_context_revalidation_task(dependency_index, queue)
    if selected is None or selected.artifact_id != transition.artifact_id:
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_OUT_OF_ORDER")
    node = dependency_index.node(transition.artifact_id)
    if (node.content_digest != transition.previous_content_digest
            or node.eligible != transition.previous_eligible
            or node.immediate_dependencies != transition.previous_dependencies):
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_STALE_TRANSITION")
    updated = replace(
        node,
        content_digest=transition.new_content_digest,
        eligible=transition.new_eligible,
        immediate_dependencies=transition.new_dependencies,
    )
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
    return ContextRevalidationProgress(
        new_index,
        ContextRevalidationQueue(
            queue.event,
            queue.accepted_event_id,
            ordered,
            tuple(sorted(task.artifact_id for task in ordered)),
            (*queue.history, transition),
        ),
    )


__all__ = (
    "ContextRevalidatedArtifact", "ContextRevalidationFrontier",
    "ContextStateTransition", "ContextRevalidationQueue",
    "ContextRevalidationProgress", "apply_context_invalidation",
    "next_context_revalidation_task", "revalidate_context_node",
    "advance_context_revalidation",
)
