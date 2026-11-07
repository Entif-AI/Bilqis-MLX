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
    process_fault_holds: set[str] = field(default_factory=set)
    context_queues: dict[str, ContextRevalidationQueue] = field(
        default_factory=dict)
    context_deferred: dict[str, ContextRevalidationFrontier] = field(
        default_factory=dict)

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
            return False
        if not queue.pending:
            self._refresh_waiting_contexts()
            queue = self.context_queues.get(context_event_id)
            if queue is None or not queue.pending:
                return False
        for item in relevant:
            task = next_context_revalidation_task(owner.index, queue)
            if task is None or task.artifact_id != item.artifact_id:
                from .atlas_revalidation_common import _invalid
                _invalid("BAMF_C09_CONTEXT_REVALIDATION_OUT_OF_ORDER")
            transition = revalidate_context_node(
                owner.index.node(task.artifact_id), queue,
                ContextRevalidationFrontier((item,)), registry)
            progress = advance_context_revalidation(
                owner.index, queue, transition)
            install = getattr(owner, "_install_context_revalidation", None)
            if not callable(install):
                from .atlas_revalidation_common import _invalid
                _invalid("BAMF_C09_CONTEXT_REVALIDATION_OWNER_UNSUPPORTED")
            install(progress.index, transition)
            queue = progress.queue
        if queue.pending:
            self.context_queues[context_event_id] = queue
        else:
            self.context_queues.pop(context_event_id, None)
        self._refresh_waiting_contexts()
        return True

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
            self.apply(owner, event, registry)
            self._sync_owner_pending()
            return True
        self._sync_owner_pending()
        return False


__all__ = ("AcceptedCorrectionTarget",)
