"""Per-owner accepted C09 correction state and branch activation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
import weakref

from .atlas_correction_branches import CorrectionBranches, add_correction
from .atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from .atlas_source_authority import SourceAuthorityRegistry
from .context_revalidation import (
    ContextRevalidationFrontier, ContextRevalidationQueue,
    advance_context_revalidation, apply_context_invalidation,
    next_context_revalidation_task, revalidate_context_node,
)
from .atlas_revalidation_queue import _sort_tasks
from bilqis_mlx.semantics.context_eligibility import C09ContextInvalidation


@dataclass
class AcceptedCorrectionTarget:
    owner_ref: weakref.ReferenceType
    apply: Callable[[object, CorrectionEvent, SourceAuthorityRegistry], object]
    seen: set[str] = field(default_factory=set)
    branches: dict[object, CorrectionBranches] = field(default_factory=dict)
    pending: list[CorrectionEvent] = field(default_factory=list)
    deferred: dict[str, RevalidationFrontier] = field(default_factory=dict)
    revalidation_consumed: dict[str, set[tuple[str, str]]] = field(default_factory=dict)
    branch_reconciled_artifacts: dict[str, set[str]] = field(
        default_factory=dict)
    late_branch_pending: dict[str, set[str]] = field(default_factory=dict)
    process_fault_holds: set[str] = field(default_factory=set)
    context_queues: dict[str, ContextRevalidationQueue] = field(
        default_factory=dict)
    context_deferred: dict[str, ContextRevalidationFrontier] = field(
        default_factory=dict)
    context_invalidations: dict[
        str, tuple[str, C09ContextInvalidation]
    ] = field(default_factory=dict)

    @property
    def context_holds(self) -> set[str]:
        return {
            artifact_id
            for queue in self.context_queues.values()
            for artifact_id in queue.held_artifact_ids
        }

    @property
    def owner(self):
        return self.owner_ref()

    def _sync_owner_pending(self) -> None:
        owner = self.owner
        if owner is not None:
            setattr(owner, "_accepted_pending_corrections", self.pending)

    def _active_event_id(self) -> str | None:
        owner = self.owner
        if owner is None:
            return None
        queue = getattr(owner, "queue", None)
        if queue is None or not queue.pending:
            return None
        return queue.event.event_id

    def _has_direct_dependents(self, event: CorrectionEvent) -> bool:
        owner = self.owner
        return bool(
            owner is not None
            and owner.index.direct_dependents(event.dependency)
        )

    def _stage(self, event: CorrectionEvent) -> None:
        if all(item.event_id != event.event_id for item in self.pending):
            self.pending.append(event)
            self.pending.sort(key=lambda item: item.event_id)
        self._sync_owner_pending()

    def accept_correction(
        self, event: CorrectionEvent, registry: SourceAuthorityRegistry,
    ) -> None:
        self.record_correction_branch(event, registry)
        superseded = set(event.supersedes_event_ids)
        if superseded:
            self.pending[:] = [
                item for item in self.pending if item.event_id not in superseded]
            for event_id in superseded:
                self.late_branch_pending.pop(event_id, None)
        active_id = self._active_event_id()
        if active_id is not None and active_id not in superseded:
            self._stage(event)
            return
        if self._has_direct_dependents(event):
            owner = self.owner
            if owner is not None:
                self.apply(owner, event, registry)
        else:
            self._stage(event)
        self._sync_owner_pending()

    def accept_context_invalidation(
        self, accepted_event_id: str, event: C09ContextInvalidation,
    ) -> None:
        """Hold retained artifacts that were built from the invalidated A13 context."""
        if not isinstance(event, C09ContextInvalidation):
            from .atlas_revalidation_common import _invalid
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_REQUIRED")
        owner = self.owner
        if owner is None:
            return
        remembered = self.context_invalidations.get(event.event_id)
        accepted = (accepted_event_id, event)
        if remembered is not None and remembered != accepted:
            from .atlas_revalidation_common import _invalid
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_REPLAY_DRIFT")
        self.context_invalidations[event.event_id] = accepted
        existing = self.context_queues.get(event.event_id)
        queue = apply_context_invalidation(
            event, accepted_event_id, owner.index)
        if existing is not None:
            if existing != queue:
                from .atlas_revalidation_common import _invalid
                _invalid("BAMF_C09_CONTEXT_INVALIDATION_REPLAY_DRIFT")
            return
        follows_active_context = any(
            prior.event.new_context_digest == event.old_context_digest
            for prior in self.context_queues.values())
        if queue.pending or follows_active_context:
            self.context_queues[event.event_id] = queue

    def _reconcile_late_context_materializations(self) -> None:
        """Reapply accepted context invalidations when an owner index grows later."""
        owner = self.owner
        if owner is None:
            return
        for event_id, (accepted_event_id, event) in tuple(
                self.context_invalidations.items()):
            refreshed = apply_context_invalidation(
                event, accepted_event_id, owner.index)
            if not refreshed.pending:
                continue
            existing = self.context_queues.get(event_id)
            if existing is None:
                self.context_queues[event_id] = refreshed
                continue
            by_artifact = {
                task.artifact_id: task for task in existing.pending}
            by_artifact.update({
                task.artifact_id: task for task in refreshed.pending})
            pending = _sort_tasks(tuple(by_artifact.values()))
            self.context_queues[event_id] = ContextRevalidationQueue(
                event,
                accepted_event_id,
                pending,
                tuple(sorted(task.artifact_id for task in pending)),
                existing.history,
            )

    def _refresh_waiting_contexts(self) -> None:
        owner = self.owner
        if owner is None:
            return
        for event_id, queue in tuple(self.context_queues.items()):
            if queue.pending or queue.history:
                continue
            refreshed = apply_context_invalidation(
                queue.event, queue.accepted_event_id, owner.index)
            self.context_queues[event_id] = refreshed

    def advance_context(
        self, frontier: ContextRevalidationFrontier,
        registry: SourceAuthorityRegistry,
    ) -> bool:
        owner = self.owner
        if owner is None:
            return True
        relevant = tuple(
            item for item in frontier.results
            if any(node.artifact_id == item.artifact_id for node in owner.index.nodes)
        )
        if not relevant:
            return True
        context_event_id = relevant[0].context_event_id
        queue = self.context_queues.get(context_event_id)
        if queue is None:
            # This target was not affected by that accepted invalidation. The
            # evidence may still be globally valid for another owner; treat it as
            # harmless here so late registration/cold replay cannot be poisoned.
            return True
        if not queue.pending:
            self._refresh_waiting_contexts()
            queue = self.context_queues.get(context_event_id)
            if queue is None or not queue.pending:
                return False
        for item in relevant:
            task = next_context_revalidation_task(owner.index, queue)
            if task is None:
                from .atlas_revalidation_common import _invalid
                _invalid("BAMF_C09_CONTEXT_REVALIDATION_OUT_OF_ORDER")
            if task.artifact_id != item.artifact_id:
                if item.artifact_id in queue.held_artifact_ids:
                    return False
                # Signed evidence for an owner-known but non-held artifact is not
                # applicable to this target. It is durable source history, not a
                # state transition for this queue.
                continue
            transition = revalidate_context_node(
                owner.index.node(task.artifact_id), queue,
                ContextRevalidationFrontier((item,)), registry)
            if (transition.changed
                    and not getattr(
                        owner, "_context_revalidation_materializes_metadata", False)):
                if transition in queue.history:
                    return False
                # The evidence proves the materialized artifact changed, but the
                # C09 frontier carries no replacement physical artifact. Keep the
                # original direct artifact held and also hold its direct consumers;
                # a newly materialized owner can supersede this stale owner later.
                pending = list(queue.pending)
                known = {pending_item.artifact_id for pending_item in pending}
                changed_ref = owner.index.node(task.artifact_id).reference
                for dependent in owner.index.direct_dependents(
                        changed_ref):
                    if dependent.artifact_id not in known:
                        from .atlas_revalidation_queue import _task
                        pending.append(_task(dependent, changed_ref))
                        known.add(dependent.artifact_id)
                from .atlas_revalidation_queue import _sort_tasks
                queue = ContextRevalidationQueue(
                    queue.event,
                    queue.accepted_event_id,
                    _sort_tasks(tuple(pending)),
                    tuple(sorted(known)),
                    (*queue.history, transition),
                )
                self.context_queues[context_event_id] = queue
                return False
            progress = advance_context_revalidation(
                owner.index, queue, transition)
            install = getattr(owner, "_install_context_revalidation", None)
            if not callable(install):
                from .atlas_revalidation_common import _invalid
                _invalid("BAMF_C09_CONTEXT_REVALIDATION_OWNER_UNSUPPORTED")
            installed = install(progress.index, transition)
            if installed is False:
                return False
            queue = progress.queue
        if queue.pending:
            self.context_queues[context_event_id] = queue
        else:
            self.context_queues.pop(context_event_id, None)
        self._refresh_waiting_contexts()
        return True

    def mark_branch_reconciled(
        self, event_id: str, artifact_id: str,
    ) -> None:
        self.branch_reconciled_artifacts.setdefault(
            event_id, set()).add(artifact_id)

    def reconcile_late_materializations(
        self, registry: SourceAuthorityRegistry,
    ) -> None:
        owner = self.owner
        if owner is None:
            return
        self._reconcile_late_context_materializations()
        hold_late = getattr(owner, "hold_late_correction", None)
        if not callable(hold_late):
            return
        already_pending = {event.event_id for event in self.pending}
        queue = getattr(owner, "queue", None)
        active_queue_id = (
            queue.event.event_id if queue is not None and queue.pending else None)
        for branches in self.branches.values():
            for branch in branches.active:
                event = branch.event
                reconciled = self.branch_reconciled_artifacts.get(
                    event.event_id, set())
                late_ids = {
                    node.artifact_id
                    for node in owner.index.direct_dependents(event.dependency)
                    if node.artifact_id not in reconciled
                }
                if not late_ids:
                    continue
                if active_queue_id == event.event_id:
                    hold_late(event, tuple(sorted(late_ids)), registry)
                    continue
                self.late_branch_pending.setdefault(
                    event.event_id, set()).update(late_ids)
                if event.event_id not in already_pending:
                    self._stage(event)
                    already_pending.add(event.event_id)

    def record_correction_branch(
        self, event: CorrectionEvent, registry: SourceAuthorityRegistry,
    ) -> None:
        """Restore authenticated branch ancestry without re-actuating the owner."""
        branches = self.branches.get(event.dependency)
        if branches is None:
            branches = CorrectionBranches(event.dependency, ())
        self.branches[event.dependency] = add_correction(
            branches, event, authority_registry=registry,
            supersedes_event_ids=event.supersedes_event_ids,
        )

    def activate_pending(self, registry: SourceAuthorityRegistry) -> bool:
        if self._active_event_id() is not None:
            self._sync_owner_pending()
            return False
        for index, event in enumerate(tuple(self.pending)):
            if not self._has_direct_dependents(event):
                continue
            del self.pending[index]
            owner = self.owner
            if owner is None:
                return False
            late_ids = self.late_branch_pending.pop(event.event_id, None)
            if late_ids is not None:
                hold_late = getattr(owner, "hold_late_correction", None)
                if not callable(hold_late):
                    from .atlas_revalidation_common import _invalid
                    _invalid("BAMF_C09_LATE_BRANCH_OWNER_UNSUPPORTED")
                hold_late(event, tuple(sorted(late_ids)), registry)
            else:
                self.apply(owner, event, registry)
            self._sync_owner_pending()
            return True
        self._sync_owner_pending()
        return False


__all__ = ("AcceptedCorrectionTarget",)
