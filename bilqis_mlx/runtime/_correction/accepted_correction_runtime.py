"""Live dispatch of accepted C09 corrections and revalidation evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Callable

from .accepted_correction_ledger import (
    CORRECTION_EVENT, accepted_corrections, frontier_from_record, read_records,
)
from .atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from .atlas_revalidation_runtime import next_revalidation_task
from .atlas_source_authority import SourceAuthorityRegistry
from .atlas_revalidation_common import _invalid
from bilqis_mlx.runtime.capability_support_journal import event_from_record


@dataclass
class _Target:
    owner: object
    apply: Callable[[CorrectionEvent, SourceAuthorityRegistry], object]
    seen: set[str] = field(default_factory=set)


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

    @staticmethod
    def _advance(
        target: _Target, frontier: RevalidationFrontier,
        registry: SourceAuthorityRegistry,
    ) -> bool:
        owner = target.owner
        if (not hasattr(owner, "queue") or owner.queue is None
                or not hasattr(owner, "index") or not hasattr(owner, "advance")):
            return False
        task = next_revalidation_task(owner.index, owner.queue)
        if task is None or all(
                item.artifact_id != task.artifact_id for item in frontier.results):
            return False
        owner.advance(frontier, registry)
        return True

    def register(
        self, kind: str, owner, apply,
        registry: SourceAuthorityRegistry | None,
        seen_event_ids: tuple[str, ...] = (),
    ) -> None:
        with self.lock:
            self.bind_registry(registry)
            key = (kind, id(owner))
            target = self.targets.setdefault(key, _Target(owner, apply))
            target.seen.update(seen_event_ids)
            for record in read_records(self.run_dir, self.manifest_sha256):
                event_id = record["event_id"]
                if event_id in target.seen:
                    continue
                if record["event"] == CORRECTION_EVENT:
                    event = event_from_record(record["correction"])
                    self.registry.verify_correction(event)
                    target.apply(event, self.registry)
                else:
                    self._advance(
                        target, frontier_from_record(record), self.registry)
                target.seen.add(event_id)

    def deliver(
        self, event_id: str, event: CorrectionEvent,
        registry: SourceAuthorityRegistry,
    ) -> None:
        with self.lock:
            self.bind_registry(registry)
            for target in self.targets.values():
                if event_id in target.seen:
                    continue
                target.apply(event, self.registry)
                target.seen.add(event_id)

    def deliver_revalidation(
        self, event_id: str, frontier: RevalidationFrontier,
        registry: SourceAuthorityRegistry,
    ) -> None:
        with self.lock:
            self.bind_registry(registry)
            for target in self.targets.values():
                if event_id in target.seen:
                    continue
                self._advance(target, frontier, self.registry)
                target.seen.add(event_id)


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
    from .owners.atlas_owner_ingress import _route

    cache = bind_accepted_execution_cache(run_dir)
    owners = (
        ("ATLAS_FEATURE", batch.atlas_feature_artifact_owner),
        ("PACKED_FRAME", batch.compiled.packed_frame_artifact_owner),
    )
    for kind, owner in owners:
        register_accepted_target(
            run_dir, cache.accepted_manifest_sha256, kind, owner,
            lambda event, authority, owner=owner: _route(
                owner, event, authority),
            registry,
        )


def register_solve_context(
    run_dir: Path, context, registry: SourceAuthorityRegistry | None = None,
) -> None:
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
    from .owners.atlas_owner_ingress import _route

    cache = bind_accepted_execution_cache(run_dir)
    owner = context.operator_composition_artifact_owner
    register_accepted_target(
        run_dir, cache.accepted_manifest_sha256, "OPERATOR_COMPOSITION", owner,
        lambda event, authority: _route(owner, event, authority), registry)


__all__ = (
    "_RUNTIME_OWNER", "bind_accepted_registry", "register_accepted_target",
    "register_compiled_batch", "register_solve_context", "runtime",
)
