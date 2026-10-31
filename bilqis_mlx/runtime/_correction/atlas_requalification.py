"""C09.2 immutable correction alternatives and learned support requalification."""
from __future__ import annotations

from dataclasses import replace

from ..semantics.cognitive_dependencies import DependencyIndex, DependencyKind
from .atlas_revalidation import RevalidationQueue, _invalid
from .atlas_correction_branches import (
    CorrectionBranch, CorrectionBranches, add_correction, _identity, _canonical_names,
    CORRECTION_BRANCH_SCHEMA, CORRECTION_BRANCHES_SCHEMA,
)
from .atlas_requalification_contracts import (
    CapabilitySupport, TargetedSourceTask, C10InvalidationIntent, RequalificationStatus,
    RequalificationLedger, RequalificationUpdate, CAPABILITY_SUPPORT_SCHEMA,
    TARGETED_SOURCE_TASK_SCHEMA, C10_INTENT_SCHEMA, REQUALIFICATION_LEDGER_SCHEMA,
    REQUALIFICATION_UPDATE_SCHEMA,
)


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
