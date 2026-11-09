"""Accepted-run C09 replay, fan-out, and revalidation dispatch."""
from __future__ import annotations

from pathlib import Path
from threading import RLock
import weakref

from bilqis_mlx.runtime.capability_support_journal import event_from_record
from bilqis_mlx.semantics.cognitive_dependencies import DependencyIndex

from .accepted_correction_ledger import (
    CONTEXT_INVALIDATION_EVENT, CONTEXT_REVALIDATION_EVENT,
    CORRECTION_EVENT, REVALIDATION_EVENT,
    context_frontier_from_record, context_invalidation_from_record,
    frontier_from_record, read_records,
)
from .accepted_correction_target import AcceptedCorrectionTarget
from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from .atlas_revalidation_runtime import next_revalidation_task
from .atlas_source_authority import SourceAuthorityRegistry


class AcceptedCorrectionRuntime:
    def __init__(self, run_dir: Path, manifest_sha256: str,
                 registry: SourceAuthorityRegistry, require_live, authorize_owner):
        if not isinstance(registry, SourceAuthorityRegistry):
            _invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
        if not callable(require_live) or not callable(authorize_owner):
            _invalid("BAMF_C09_ACCEPTED_RUNTIME_REQUIRED")
        self.run_dir = Path(run_dir)
        self.manifest_sha256 = manifest_sha256
        self.registry = registry
        self.targets: dict[tuple[str, int], AcceptedCorrectionTarget] = {}
        self.lock = RLock()
        self._accepted_support_census = None
        self._require_runtime = require_live
        self._authorize_owner = authorize_owner

    def _require_live(self) -> None:
        self._require_runtime(self)

    def _with_target(self, target: AcceptedCorrectionTarget, action):
        owner = target.owner
        if owner is None:
            return action()
        return self._authorize_owner(owner, action)

    def _advance(
        self, target: AcceptedCorrectionTarget, event_id: str,
        frontier: RevalidationFrontier, registry: SourceAuthorityRegistry,
    ) -> bool:
        owner = target.owner
        if not hasattr(owner, "index") or not hasattr(owner, "advance"):
            return False
        consumed = target.revalidation_consumed.setdefault(event_id, set())
        while True:
            target.activate_pending(registry)
            queue = getattr(owner, "queue", None)
            if queue is None or not queue.pending:
                break
            task = next_revalidation_task(owner.index, queue)
            candidate = next((
                item for item in frontier.results
                if item.artifact_id == task.artifact_id
                and item.correction_event_id == queue.event.event_id
            ), None)
            if candidate is None:
                break
            owner.advance(RevalidationFrontier((candidate,)), registry)
            consumed.add((candidate.correction_event_id, candidate.artifact_id))
            target.mark_branch_reconciled(
                candidate.correction_event_id, candidate.artifact_id)
        relevant = {
            (item.correction_event_id, item.artifact_id)
            for item in frontier.results
            if any(node.artifact_id == item.artifact_id for node in owner.index.nodes)
        }
        if frontier.results and not relevant:
            return False
        complete = relevant <= consumed
        if complete:
            target.revalidation_consumed.pop(event_id, None)
        return complete

    def register(
        self, kind: str, owner, apply,
        seen_event_ids: tuple[str, ...] = (),
    ) -> None:
        self._require_live()
        with self.lock:
            self._retire_divergent_aliases(kind, owner)
            key = (kind, id(owner))
            target = self.targets.get(key)
            if target is None:
                target = self._new_target(key, owner, apply)
                self.targets[key] = target
            elif target.owner is not owner:
                _invalid("BAMF_C09_ACCEPTED_TARGET_IDENTITY_CONFLICT")
            setattr(owner, "_accepted_correction_target", target)
            def hydrate():
                self._restore_branches(target)
                target.seen.update(seen_event_ids)
                self._replay(target)
                target.reconcile_late_materializations(self.registry)
                target.activate_pending(self.registry)
                self._retry_deferred(target)
                self._retry_context_deferred(target)
                from .accepted_stale_replay_runtime import replay_stale_evidence
                replay_stale_evidence(self)
            self._with_target(target, hydrate)

    def refresh_target(self, target: AcceptedCorrectionTarget) -> None:
        self._require_live()
        with self.lock:
            def refresh():
                self._replay(target)
                target.reconcile_late_materializations(self.registry)
                target.activate_pending(self.registry)
                self._retry_deferred(target)
                self._retry_context_deferred(target)
                from .accepted_stale_replay_runtime import replay_persisted_faults
                replay_persisted_faults(self)
            self._with_target(target, refresh)

    def _retire_divergent_aliases(self, kind: str, owner) -> None:
        index = getattr(owner, "index", None)
        nodes = tuple(index.nodes) if isinstance(index, DependencyIndex) else ()
        artifact_ids = frozenset(node.artifact_id for node in nodes)
        ledger = getattr(owner, "ledger", None)
        for key, target in tuple(self.targets.items()):
            if key[0] != kind:
                continue
            existing = target.owner
            if existing is None:
                self.targets.pop(key, None)
                continue
            existing_index = getattr(existing, "index", None)
            existing_nodes = (
                tuple(existing_index.nodes)
                if isinstance(existing_index, DependencyIndex) else ())
            existing_ids = frozenset(node.artifact_id for node in existing_nodes)
            equivalent = (
                nodes == existing_nodes
                and ledger == getattr(existing, "ledger", None)
            )
            if not artifact_ids or artifact_ids != existing_ids or equivalent:
                continue
            setattr(existing, "_accepted_owner_superseded", True)
            self.targets.pop(key, None)

    def _new_target(self, key, owner, apply) -> AcceptedCorrectionTarget:
        retained_ref = weakref.ref(self)

        def remove_dead(_owner_ref, *, target_key=key, runtime_ref=retained_ref):
            retained = runtime_ref()
            if retained is None:
                return
            with retained.lock:
                retained.targets.pop(target_key, None)

        return AcceptedCorrectionTarget(weakref.ref(owner, remove_dead), apply)

    def _restore_branches(self, target: AcceptedCorrectionTarget) -> None:
        for record in read_records(self.run_dir, self.manifest_sha256):
            if record["event"] != CORRECTION_EVENT:
                continue
            if self.registry is None:
                _invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
            event = event_from_record(record["correction"])
            self.registry.verify_correction(event)
            target.record_correction_branch(event, self.registry)

    def _replay(self, target: AcceptedCorrectionTarget) -> None:
        for record in read_records(self.run_dir, self.manifest_sha256):
            event_id = record["event_id"]
            if event_id in target.seen:
                continue
            if record["event"] == CORRECTION_EVENT:
                if self.registry is None:
                    _invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
                event = event_from_record(record["correction"])
                self.registry.verify_correction(event)
                target.accept_correction(event, self.registry)
            elif record["event"] == CONTEXT_INVALIDATION_EVENT:
                target.accept_context_invalidation(
                    event_id, context_invalidation_from_record(record))
            elif record["event"] == CONTEXT_REVALIDATION_EVENT:
                frontier = context_frontier_from_record(record)
                if self.registry is None:
                    _invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
                if not target.advance_context(frontier, self.registry):
                    target.context_deferred[event_id] = frontier
                    continue
                target.context_deferred.pop(event_id, None)
            elif record["event"] == REVALIDATION_EVENT:
                frontier = frontier_from_record(record)
                if not self._advance(target, event_id, frontier, self.registry):
                    target.deferred[event_id] = frontier
                    continue
            else:
                continue
            target.seen.add(event_id)

    def _retry_deferred(self, target: AcceptedCorrectionTarget) -> None:
        if self.registry is None:
            return
        for event_id, frontier in tuple(target.deferred.items()):
            if self._advance(target, event_id, frontier, self.registry):
                target.seen.add(event_id)
                del target.deferred[event_id]

    def _retry_context_deferred(
        self, target: AcceptedCorrectionTarget,
    ) -> None:
        if self.registry is None:
            return
        progressed = True
        while progressed:
            progressed = False
            for event_id, frontier in tuple(target.context_deferred.items()):
                if target.advance_context(frontier, self.registry):
                    target.seen.add(event_id)
                    del target.context_deferred[event_id]
                    progressed = True

    def deliver(
        self, event_id: str, event: CorrectionEvent,
    ) -> None:
        self._require_live()
        with self.lock:
            for target in tuple(self.targets.values()):
                if target.owner is None or event_id in target.seen:
                    continue
                def apply_event():
                    target.accept_correction(event, self.registry)
                    target.seen.add(event_id)
                    self._retry_deferred(target)
                self._with_target(target, apply_event)

    def deliver_revalidation(
        self, event_id: str, frontier: RevalidationFrontier,
    ) -> None:
        self._require_live()
        with self.lock:
            for target in tuple(self.targets.values()):
                if target.owner is None or event_id in target.seen:
                    continue
                def apply_frontier():
                    if self._advance(target, event_id, frontier, self.registry):
                        target.seen.add(event_id)
                    else:
                        target.deferred[event_id] = frontier
                    self._retry_deferred(target)
                self._with_target(target, apply_frontier)
            from .accepted_stale_replay_runtime import replay_stale_evidence
            replay_stale_evidence(self)

    def deliver_context_invalidation(self, event_id: str, event) -> None:
        self._require_live()
        with self.lock:
            for target in tuple(self.targets.values()):
                if target.owner is None or event_id in target.seen:
                    continue
                def apply_context():
                    target.accept_context_invalidation(event_id, event)
                    target.seen.add(event_id)
                    self._retry_context_deferred(target)
                self._with_target(target, apply_context)

    def deliver_context_revalidation(
        self, event_id: str, frontier,
    ) -> None:
        self._require_live()
        with self.lock:
            for target in tuple(self.targets.values()):
                if target.owner is None or event_id in target.seen:
                    continue
                def apply_context_frontier():
                    if target.advance_context(frontier, self.registry):
                        target.seen.add(event_id)
                        self._retry_context_deferred(target)
                    else:
                        target.context_deferred[event_id] = frontier
                self._with_target(target, apply_context_frontier)
            from .accepted_stale_replay_runtime import replay_stale_evidence
            replay_stale_evidence(self)


__all__ = ("AcceptedCorrectionRuntime",)
