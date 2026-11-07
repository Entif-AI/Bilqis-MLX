"""Per-owner accepted C09 correction state and branch activation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
import weakref

from .atlas_correction_branches import CorrectionBranches, add_correction
from .atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from .atlas_source_authority import SourceAuthorityRegistry
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
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
    context_holds: set[str] = field(default_factory=set)

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

    def accept_context_invalidation(self, event: C09ContextInvalidation) -> None:
        """Hold retained artifacts that were built from the invalidated A13 context."""
        if not isinstance(event, C09ContextInvalidation):
            from .atlas_revalidation_common import _invalid
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_REQUIRED")
        owner = self.owner
        if owner is None:
            return
        cause = DependencyRef(
            DependencyKind.TIME, "time:asof:context:" + event.old_context_digest)
        self.context_holds.update(
            node.artifact_id for node in owner.index.direct_dependents(cause))

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
