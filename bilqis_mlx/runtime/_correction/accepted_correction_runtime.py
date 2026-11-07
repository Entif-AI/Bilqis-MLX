"""Live dispatch of accepted C09 corrections and revalidation evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Callable
import weakref

from .accepted_correction_ledger import (
    CORRECTION_EVENT, REVALIDATION_EVENT, accepted_corrections,
    frontier_from_record, read_records,
)
from .atlas_correction_branches import CorrectionBranches, add_correction
from .atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from .atlas_revalidation_runtime import next_revalidation_task
from .atlas_source_authority import SourceAuthorityRegistry
from .atlas_revalidation_common import _invalid
from bilqis_mlx.runtime.capability_support_journal import event_from_record
from bilqis_mlx.semantics.cognitive_dependencies import DependencyIndex


@dataclass
class _Target:
    owner_ref: weakref.ReferenceType
    apply: Callable[[object, CorrectionEvent, SourceAuthorityRegistry], object]
    seen: set[str] = field(default_factory=set)
    branches: dict[object, CorrectionBranches] = field(default_factory=dict)
    pending: list[CorrectionEvent] = field(default_factory=list)
    deferred: dict[str, RevalidationFrontier] = field(default_factory=dict)
    revalidation_consumed: dict[str, set[tuple[str, str]]] = field(default_factory=dict)
    process_fault_holds: set[str] = field(default_factory=set)

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
        branches = self.branches.get(event.dependency)
        if branches is None:
            branches = CorrectionBranches(event.dependency, ())
        self.branches[event.dependency] = add_correction(
            branches, event, authority_registry=registry,
            supersedes_event_ids=event.supersedes_event_ids,
        )
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


class _AcceptedCorrectionRuntime:
    def __init__(self, run_dir: Path, manifest_sha256: str):
        self.run_dir = Path(run_dir)
        self.manifest_sha256 = manifest_sha256
        self.registry: SourceAuthorityRegistry | None = None
        self.targets: dict[tuple[str, int], _Target] = {}
        self.lock = RLock()

    def bind_registry(self, registry: SourceAuthorityRegistry | None) -> None:
        if registry is None:
            return
        if not isinstance(registry, SourceAuthorityRegistry):
            _invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
        if self.registry is not None and self.registry != registry:
            _invalid("BAMF_C09_CORRECTION_AUTHORITY_DRIFT")
        self.registry = registry

    def _advance(
        self, target: _Target, event_id: str, frontier: RevalidationFrontier,
        registry: SourceAuthorityRegistry,
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
        registry: SourceAuthorityRegistry | None,
        seen_event_ids: tuple[str, ...] = (),
    ) -> None:
        with self.lock:
            self.bind_registry(registry)
            owner_index = getattr(owner, "index", None)
            owner_nodes = (
                tuple(owner_index.nodes)
                if isinstance(owner_index, DependencyIndex) else ()
            )
            owner_artifact_ids = frozenset(
                node.artifact_id for node in owner_nodes)
            owner_ledger = getattr(owner, "ledger", None)
            for existing_key, existing in tuple(self.targets.items()):
                if existing_key[0] != kind:
                    continue
                existing_owner = existing.owner
                if existing_owner is None:
                    self.targets.pop(existing_key, None)
                    continue
                existing_index = getattr(existing_owner, "index", None)
                existing_nodes = (
                    tuple(existing_index.nodes)
                    if isinstance(existing_index, DependencyIndex) else ()
                )
                existing_artifact_ids = frozenset(
                    node.artifact_id for node in existing_nodes)
                existing_ledger = getattr(existing_owner, "ledger", None)
                if (not owner_artifact_ids
                        or owner_artifact_ids != existing_artifact_ids
                        or (owner_nodes == existing_nodes
                            and owner_ledger == existing_ledger)):
                    continue
                setattr(existing_owner, "_accepted_owner_superseded", True)
                self.targets.pop(existing_key, None)
            key = (kind, id(owner))
            target = self.targets.get(key)
            if target is None:
                runtime_ref = weakref.ref(self)

                def remove_dead(_owner_ref, *, target_key=key, retained_ref=runtime_ref):
                    retained = retained_ref()
                    if retained is None:
                        return
                    with retained.lock:
                        retained.targets.pop(target_key, None)

                target = _Target(weakref.ref(owner, remove_dead), apply)
                self.targets[key] = target
            elif target.owner is not owner:
                _invalid("BAMF_C09_ACCEPTED_TARGET_IDENTITY_CONFLICT")
            setattr(owner, "_accepted_correction_target", target)
            target.seen.update(seen_event_ids)
            for record in read_records(self.run_dir, self.manifest_sha256):
                event_id = record["event_id"]
                if event_id in target.seen:
                    continue
                if record["event"] == CORRECTION_EVENT:
                    event = event_from_record(record["correction"])
                    self.registry.verify_correction(event)
                    target.accept_correction(event, self.registry)
                elif record["event"] == REVALIDATION_EVENT:
                    frontier = frontier_from_record(record)
                    if not self._advance(target, event_id, frontier, self.registry):
                        target.deferred[event_id] = frontier
                        continue
                else:
                    continue
                target.seen.add(event_id)
            self._retry_deferred(target)
            from .accepted_stale_replay_runtime import replay_stale_evidence
            replay_stale_evidence(self)

    def _retry_deferred(self, target: _Target) -> None:
        if self.registry is None:
            return
        for event_id, frontier in tuple(target.deferred.items()):
            if self._advance(target, event_id, frontier, self.registry):
                target.seen.add(event_id)
                del target.deferred[event_id]

    def deliver(
        self, event_id: str, event: CorrectionEvent,
        registry: SourceAuthorityRegistry,
    ) -> None:
        with self.lock:
            self.bind_registry(registry)
            for target in tuple(self.targets.values()):
                if target.owner is None:
                    continue
                if event_id in target.seen:
                    continue
                target.accept_correction(event, self.registry)
                target.seen.add(event_id)
                self._retry_deferred(target)

    def deliver_revalidation(
        self, event_id: str, frontier: RevalidationFrontier,
        registry: SourceAuthorityRegistry,
    ) -> None:
        with self.lock:
            self.bind_registry(registry)
            for target in tuple(self.targets.values()):
                if target.owner is None:
                    continue
                if event_id in target.seen:
                    continue
                if self._advance(target, event_id, frontier, self.registry):
                    target.seen.add(event_id)
                else:
                    target.deferred[event_id] = frontier
                self._retry_deferred(target)


def refresh_owner_corrections(owner) -> None:
    """Activate a previously observed correction after an owner gains dependencies."""
    target = getattr(owner, "_accepted_correction_target", None)
    if target is None:
        return
    retained_runtime = next((
        runtime for runtime in _RUNTIME_OWNER.entries.values()
        if any(candidate is target for candidate in runtime.targets.values())
    ), None)
    if retained_runtime is not None and retained_runtime.registry is not None:
        target.activate_pending(retained_runtime.registry)
        retained_runtime._retry_deferred(target)


def require_pending_corrections(owner, artifact_id: str) -> None:
    """Fail closed when a staged correction already directly affects this artifact."""
    if getattr(owner, "_accepted_owner_superseded", False):
        _invalid("BAMF_C09_ARTIFACT_OWNER_SUPERSEDED")
    target = getattr(owner, "_accepted_correction_target", None)
    if target is None:
        return
    if artifact_id in target.process_fault_holds:
        _invalid("BAMF_C09_PROPAGATION_REPAIR_FAILED")
    node = owner.index.node(artifact_id)
    for event in target.pending:
        if event.dependency in node.immediate_dependencies:
            _invalid("BAMF_C09_ARTIFACT_HELD")


class _CorrectionRuntimeOwner:
    """Process-lifetime registry for accepted correction runtimes."""

    def __init__(self):
        self.entries = {}

    def get(self, key):
        return self.entries.get(key)

    def set(self, key, runtime) -> None:
        self.entries[key] = runtime

    def clear(self) -> None:
        self.entries.clear()


_RUNTIME_OWNER = _CorrectionRuntimeOwner()
_RUNTIME_LOCK = RLock()


def runtime(run_dir: Path, manifest_sha256: str) -> _AcceptedCorrectionRuntime:
    key = (str(Path(run_dir).resolve()), manifest_sha256)
    with _RUNTIME_LOCK:
        retained = _RUNTIME_OWNER.get(key)
        if retained is None:
            retained = _AcceptedCorrectionRuntime(Path(run_dir), manifest_sha256)
            _RUNTIME_OWNER.set(key, retained)
        return retained


def register_accepted_target(
    run_dir: Path, manifest_sha256: str, kind: str, owner, apply,
    registry: SourceAuthorityRegistry | None = None,
    seen_event_ids: tuple[str, ...] = (),
) -> None:
    runtime(run_dir, manifest_sha256).register(
        kind, owner, apply, registry, seen_event_ids)


def bind_accepted_registry(
    run_dir: Path, manifest_sha256: str, registry: SourceAuthorityRegistry,
) -> None:
    retained = runtime(run_dir, manifest_sha256)
    with retained.lock:
        retained.bind_registry(registry)


def register_compiled_batch(
    run_dir: Path, batch, registry: SourceAuthorityRegistry | None = None,
) -> None:
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
    from bilqis_mlx.runtime.atlas_owner_ingress import _route

    cache = bind_accepted_execution_cache(run_dir)
    owners = (
        ("ATLAS_FEATURE", batch.atlas_feature_artifact_owner),
        ("PACKED_FRAME", batch.compiled.packed_frame_artifact_owner),
    )
    for kind, owner in owners:
        register_accepted_target(
            run_dir, cache.accepted_manifest_sha256, kind, owner,
            lambda current, event, authority: _route(
                current, event, authority),
            registry,
        )


def register_solve_context(
    run_dir: Path, context, registry: SourceAuthorityRegistry | None = None,
) -> None:
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
    from bilqis_mlx.runtime.atlas_owner_ingress import _route

    cache = bind_accepted_execution_cache(run_dir)
    owner = context.operator_composition_artifact_owner
    register_accepted_target(
        run_dir, cache.accepted_manifest_sha256, "OPERATOR_COMPOSITION", owner,
        lambda current, event, authority: _route(current, event, authority), registry)


__all__ = (
    "_RUNTIME_OWNER", "bind_accepted_registry", "register_accepted_target",
    "refresh_owner_corrections", "register_compiled_batch",
    "register_solve_context", "require_pending_corrections", "runtime",
)
