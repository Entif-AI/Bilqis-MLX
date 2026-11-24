"""Process-local hydration and execution-cache owner for accepted BAMF state."""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from .accepted_runtime import _accepted_source_authority_registry
from .accepted_hydration import (
    AcceptedHydration, AcceptedPublicationParent, current_hydration_locked,
    new_publication_parent, require_current_hydration,
    require_publication_parent_locked,
)
from .execution_cache import _new_execution_cache
from .publication import _pointer_read_lock, _read_pointer
from .records import invalid


class _AcceptedExecutionEntry:
    __slots__ = ("hydration", "cache", "registry", "registry_sha256",
                 "generation_binding", "motif_manifest_sha256")

    def __init__(self, hydration, cache, registry, registry_sha256,
                 generation_binding, motif_manifest_sha256):
        self.hydration = hydration
        self.cache = cache
        self.registry = registry
        self.registry_sha256 = registry_sha256
        self.generation_binding = generation_binding
        self.motif_manifest_sha256 = motif_manifest_sha256


def _current_registry(run_dir: Path, hydration):
    try:
        frontier = json.loads(hydration.correction_frontier_canonical)
    except (json.JSONDecodeError, UnicodeDecodeError):
        invalid("B13_EXECUTION_CACHE_REQUIRED")
    from .source_authority_custody import resolve_source_authority_registry
    return resolve_source_authority_registry(run_dir, frontier)


def _require_execution_entry(entry, registry) -> None:
    if entry is None:
        invalid("B13_EXECUTION_CACHE_REQUIRED")
    cache = entry.cache
    hydration = entry.hydration
    if (cache.accepted_manifest_sha256 != hydration.manifest_sha256
            or cache.run_id != hydration.student.run_id
            or cache.generation != hydration.student.generation
            or cache._candidate_identity_sha256
            != hydration.candidate_identity_sha256
            or registry != entry.registry
            or cache._correction_registry is not entry.registry
            or cache.source_authority_registry_sha256 != entry.registry_sha256
            or cache.generation_binding != entry.generation_binding
            or cache.motif_manifest.digest != entry.motif_manifest_sha256):
        invalid("B13_EXECUTION_CACHE_REQUIRED")


def _new_execution_entry(run_dir: Path, hydration, registry):
    from bilqis_mlx.runtime.backbone_identity import (
        execution_generation_object_key,
        issue_execution_generation_binding,
    )

    student = hydration.student
    parameters = student.retained_state.optimizer.parameters
    binding = issue_execution_generation_binding(
        parameters, spec=student.topology, extents=student.extents)
    cache = _new_execution_cache(
        run_id=student.run_id, generation=student.generation,
        accepted_manifest_sha256=hydration.manifest_sha256,
        generation_binding=binding.generation_digest,
        motif_manifest=student.retained_state.allocations.manifest,
        source_authority_registry_sha256=student.correction_frontier.get(
            "source_authority_registry_sha256"))
    object.__setattr__(cache, "_run_dir", run_dir)
    object.__setattr__(
        cache, "_candidate_identity_sha256", hydration.candidate_identity_sha256)
    if registry is not None:
        object.__setattr__(cache, "_correction_registry", registry)
    object.__setattr__(cache, "_bundle_currentness", hydration.currentness)
    cache._execution_bindings[execution_generation_object_key(
        parameters, spec=student.topology, extents=student.extents)] = binding
    return _AcceptedExecutionEntry(
        hydration, cache, registry,
        student.correction_frontier.get("source_authority_registry_sha256"),
        binding.generation_digest, student.retained_state.allocations.manifest.digest)


class _ExecutionCacheRuntime:
    def __init__(self):
        self.lock = RLock()
        self.hydrations = {}
        self.executions = {}

    def current_hydration(self, run_dir: Path, *, metrics=None):
        run_dir = Path(run_dir).resolve()
        key = str(run_dir)
        from .publication.accepted_authority_recovery import recover_accepted_authority_pointer
        recover_accepted_authority_pointer(run_dir)
        with _pointer_read_lock(run_dir):
            pointer = _read_pointer(run_dir / "bamf-state.json")
            hydration, changed = current_hydration_locked(
                self.lock, self.hydrations, run_dir, key, pointer, metrics=metrics)
            if changed:
                with self.lock:
                    self.executions.pop(key, None)
            return hydration

    def bind(self, run_dir: Path, *, metrics=None):
        run_dir = Path(run_dir).resolve()
        key = str(run_dir)
        from .publication.accepted_authority_recovery import recover_accepted_authority_pointer
        recover_accepted_authority_pointer(run_dir)
        with _pointer_read_lock(run_dir):
            pointer = _read_pointer(run_dir / "bamf-state.json")
            hydration, changed = current_hydration_locked(
                self.lock, self.hydrations, run_dir, key, pointer, metrics=metrics)
            if changed:
                with self.lock:
                    self.executions.pop(key, None)
            registry = _accepted_source_authority_registry(
                run_dir, hydration.student)
            with self.lock:
                retained = self.executions.get(key)
                if (retained is not None
                        and retained.hydration is hydration):
                    _require_execution_entry(retained, registry)
                    return retained.cache
                retained = _new_execution_entry(run_dir, hydration, registry)
                self.executions[key] = retained
                return retained.cache

    def bind_feature_context(self, run_dir: Path, parent, artifact_path=None):
        """Authenticate current accepted feature state from durable B13 authority."""
        run_dir = Path(run_dir).resolve()
        hydration = self.current_hydration(run_dir)
        from .accepted_feature import bind_checkpoint_feature_context
        context = bind_checkpoint_feature_context(
            run_dir, parent, hydration, artifact_path)
        if self.current_hydration(run_dir) is not hydration:
            invalid("BAMF_ACCEPTED_FEATURE_CONTEXT_STALE")
        return context

    def load_feature_context(self, run_dir: Path, artifact_path=None):
        """Return the owned current student and checkpoint feature context together."""
        run_dir = Path(run_dir).resolve()
        hydration = self.current_hydration(run_dir)
        from .accepted_feature import bind_checkpoint_feature_context
        context = bind_checkpoint_feature_context(
            run_dir, hydration.student, hydration, artifact_path)
        if self.current_hydration(run_dir) is not hydration:
            invalid("BAMF_ACCEPTED_FEATURE_CONTEXT_STALE")
        return hydration.student, context

    def require(self, cache):
        key = getattr(cache, "_run_dir", None)
        if key is None:
            invalid("B13_EXECUTION_CACHE_REQUIRED")
        run_dir = Path(key).resolve()
        hydration = self.current_hydration(run_dir)
        if (getattr(cache, "accepted_manifest_sha256", None)
                != hydration.manifest_sha256
                or getattr(cache, "run_id", None) != hydration.student.run_id
                or getattr(cache, "generation", None) != hydration.student.generation):
            invalid("B13_EXECUTION_CACHE_STALE")
        registry = _current_registry(run_dir, hydration)
        with self.lock:
            retained = self.executions.get(str(run_dir))
            if retained is None or retained.cache is not cache:
                invalid("B13_EXECUTION_CACHE_REQUIRED")
            _require_execution_entry(retained, registry)
        return cache

    def load(self, run_dir: Path):
        return self.current_hydration(run_dir).student

    def load_with_pointer_if_cached(self, run_dir: Path):
        """Reuse current accepted hydration only when this process already owns one."""
        run_dir = Path(run_dir).resolve()
        key = str(run_dir)
        with self.lock:
            retained = self.hydrations.get(key)
        if retained is None:
            return None
        with _pointer_read_lock(run_dir):
            pointer = _read_pointer(run_dir / "bamf-state.json")
            if (pointer is None
                    or pointer.get("manifest_sha256") != retained.manifest_sha256):
                return None
            hydration = require_current_hydration(run_dir, pointer, retained)
            return pointer, hydration.student

    def bind_publication_parent_locked(self, run_dir: Path, pointer):
        run_dir = Path(run_dir).resolve()
        key = str(run_dir)
        from .publication.instrumentation import publication_bundle_load
        with publication_bundle_load("parent"):
            hydration, changed = current_hydration_locked(
                self.lock, self.hydrations, run_dir, key, pointer)
            if changed:
                with self.lock:
                    self.executions.pop(key, None)
        return new_publication_parent(run_dir, hydration)

    def bind_publication_parent(self, run_dir: Path):
        run_dir = Path(run_dir).resolve()
        from .publication.accepted_authority_recovery import recover_accepted_authority_pointer
        recover_accepted_authority_pointer(run_dir)
        with _pointer_read_lock(run_dir):
            pointer = _read_pointer(run_dir / "bamf-state.json")
            return self.bind_publication_parent_locked(run_dir, pointer)

    def require_publication_parent_locked(self, run_dir: Path, pointer, witness):
        return require_publication_parent_locked(
            self.lock, self.hydrations, run_dir, pointer, witness)

    def reset_for_tests(self):
        with self.lock:
            self.hydrations.clear()
            self.executions.clear()


def _make_execution_cache_runtime():
    runtime = _ExecutionCacheRuntime()

    return (
        runtime.bind, runtime.require, runtime.load,
        runtime.load_with_pointer_if_cached, runtime.reset_for_tests,
        runtime.bind_publication_parent, runtime.bind_publication_parent_locked,
        runtime.require_publication_parent_locked, runtime.bind_feature_context,
        runtime.load_feature_context,
    )


(
    bind_accepted_execution_cache,
    _require_owned_execution_cache,
    load_accepted_generation,
    load_accepted_generation_with_pointer_if_cached,
    _reset_execution_cache_owner_for_tests,
    bind_accepted_publication_parent,
    _bind_accepted_publication_parent_locked,
    _require_accepted_publication_parent_locked,
    bind_accepted_execution_feature_context,
    load_accepted_generation_with_feature_context,
) = _make_execution_cache_runtime()


__all__ = (
    "AcceptedPublicationParent", "bind_accepted_execution_cache",
    "bind_accepted_execution_feature_context",
    "bind_accepted_publication_parent", "load_accepted_generation",
    "load_accepted_generation_with_feature_context",
    "load_accepted_generation_with_pointer_if_cached",
)
