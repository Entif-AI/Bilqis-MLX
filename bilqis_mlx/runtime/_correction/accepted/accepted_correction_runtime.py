"""Process-owned accepted C09 runtimes and production registration gates."""
from __future__ import annotations

from pathlib import Path
from threading import RLock

from .accepted_correction_dispatch import AcceptedCorrectionRuntime
from .atlas_revalidation_common import _invalid
from .atlas_source_authority import SourceAuthorityRegistry


def refresh_owner_corrections(owner) -> None:
    """Reconcile durable accepted evidence before this physical owner is used."""
    target = getattr(owner, "_accepted_correction_target", None)
    if target is None:
        return
    retained_runtime = next((
        runtime for runtime in _RUNTIME_OWNER.entries.values()
        if any(candidate is target for candidate in runtime.targets.values())
    ), None)
    if retained_runtime is not None and retained_runtime.registry is not None:
        with retained_runtime.lock:
            retained_runtime._replay(target)
            target.activate_pending(retained_runtime.registry)
            retained_runtime._retry_deferred(target)
            from .accepted_stale_replay_runtime import replay_persisted_faults
            replay_persisted_faults(retained_runtime)


def require_pending_corrections(owner, artifact_id: str) -> None:
    """Fail closed when accepted correction state blocks this physical owner."""
    if getattr(owner, "_accepted_owner_superseded", False):
        _invalid("BAMF_C09_ARTIFACT_OWNER_SUPERSEDED")
    refresh_owner_corrections(owner)
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

    def set(self, key, retained) -> None:
        self.entries[key] = retained

    def clear(self) -> None:
        self.entries.clear()


_RUNTIME_OWNER = _CorrectionRuntimeOwner()
_RUNTIME_LOCK = RLock()


def runtime(run_dir: Path, manifest_sha256: str) -> AcceptedCorrectionRuntime:
    key = (str(Path(run_dir).resolve()), manifest_sha256)
    with _RUNTIME_LOCK:
        retained = _RUNTIME_OWNER.get(key)
        if retained is None:
            retained = AcceptedCorrectionRuntime(Path(run_dir), manifest_sha256)
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
            lambda current, event, authority: _route(current, event, authority),
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
