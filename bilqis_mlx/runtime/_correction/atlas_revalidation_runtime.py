"""Correction hold, read, revalidation, and propagation operations."""
from __future__ import annotations

from dataclasses import replace

from ..semantics.cognitive_dependencies import (
    ArtifactNode,
    DependencyIndex,
    DependencyKind,
)
from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import (
    CorrectionEvent,
    RevalidatedArtifact,
    RevalidationFrontier,
    StateTransition,
)
from .atlas_revalidation_queue import (
    RevalidationProgress,
    RevalidationQueue,
    RevalidationTask,
    _sort_tasks,
    _task,
)
from .atlas_source_authority import SourceAuthorityRegistry


def apply_correction(
    event: CorrectionEvent, dependency_index: DependencyIndex,
    authority_registry: SourceAuthorityRegistry | None = None,
) -> RevalidationQueue:
    """Hold only direct consumers of a qualified correction, before readout."""
    if (not isinstance(event, CorrectionEvent)
            or not isinstance(dependency_index, DependencyIndex)):
        _invalid("BAMF_C09_CORRECTION_ARGUMENT_INVALID")
    if not isinstance(authority_registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
    authority_registry.verify_correction(event)
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
        unseen = [
            ref.key for ref in node.immediate_dependencies
            if ref.kind is DependencyKind.ARTIFACT
        ]
        visited: set[str] = set()
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
        _invalid("BAMF_C09_REVALIDATION_DEPENDENCY_BLOCKED")
    return None


def revalidate_node(
    node: ArtifactNode, frontier: RevalidationFrontier,
    authority_registry: SourceAuthorityRegistry | None = None,
) -> StateTransition:
    """Compare source-owner recomputation to retained immutable materialization."""
    if (not isinstance(node, ArtifactNode)
            or not isinstance(frontier, RevalidationFrontier)):
        _invalid("BAMF_C09_REVALIDATION_ARGUMENT_INVALID")
    if not isinstance(authority_registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
    candidate = next(
        (item for item in frontier.results
         if item.artifact_id == node.artifact_id), None)
    if candidate is None:
        _invalid("BAMF_C09_REVALIDATION_EVIDENCE_MISSING")
    if candidate.immediate_dependencies != node.immediate_dependencies:
        _invalid("BAMF_C09_REVALIDATION_DEPENDENCY_DRIFT")
    authority_registry.verify_revalidation(candidate)
    return StateTransition(
        artifact_id=node.artifact_id,
        previous_content_digest=node.content_digest,
        new_content_digest=candidate.content_digest,
        previous_eligible=node.eligible,
        new_eligible=candidate.eligible,
        source_receipt_sha256=candidate.source_receipt_sha256,
        correction_event_id=candidate.correction_event_id,
        correction_receipt_sha256=candidate.correction_receipt_sha256,
        source_owner=candidate.source_owner,
        source_signature_hex=candidate.source_signature_hex,
        immediate_dependencies=candidate.immediate_dependencies,
        changed=(candidate.content_digest != node.content_digest
                 or candidate.eligible != node.eligible),
    )


def advance_revalidation(
    dependency_index: DependencyIndex,
    queue: RevalidationQueue,
    transition: StateTransition,
    authority_registry: SourceAuthorityRegistry | None = None,
) -> RevalidationProgress:
    """Advance one lazy task; propagate only changed content or eligibility."""
    if (not isinstance(dependency_index, DependencyIndex)
            or not isinstance(queue, RevalidationQueue)
            or not isinstance(transition, StateTransition)):
        _invalid("BAMF_C09_REVALIDATION_ARGUMENT_INVALID")
    if not isinstance(authority_registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
    authority_registry.verify_correction(queue.event)
    authority_registry.verify_transition(transition)
    if (transition.correction_event_id != queue.event.event_id
            or transition.correction_receipt_sha256
            != queue.event.source_receipt_sha256):
        _invalid("BAMF_C09_REVALIDATION_CORRECTION_MISMATCH")
    selected = next_revalidation_task(dependency_index, queue)
    if selected is None or selected.artifact_id != transition.artifact_id:
        _invalid("BAMF_C09_REVALIDATION_OUT_OF_ORDER")
    node = dependency_index.node(transition.artifact_id)
    if (node.content_digest != transition.previous_content_digest
            or node.eligible != transition.previous_eligible
            or node.immediate_dependencies != transition.immediate_dependencies):
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
