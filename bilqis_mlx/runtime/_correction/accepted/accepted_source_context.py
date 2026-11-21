"""Depth-invariant accepted source-context reuse for the BAMF hot path."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from threading import RLock


_CACHE_LOCK = RLock()
_CACHE = {}


def _cache_key(run_dir: Path, student, factory_release_sha256: str, source_root):
    return (
        str(Path(run_dir).resolve()),
        factory_release_sha256,
        student.compiler_features.get("factory_semantic_graph_sha256"),
        student.compiler_features.get("factory_semantic_catalog_sha256"),
        student.correction_frontier.get("source_authority_registry_sha256"),
        None if source_root is None else str(Path(source_root).resolve()),
    )


def _reuse(key, host):
    from bilqis_mlx.runtime.source_execution import SourcePreparationMetrics

    with _CACHE_LOCK:
        retained = _CACHE.get(key)
    if retained is None:
        return None
    object.__setattr__(retained, "_accepted_runtime_host", host)
    object.__setattr__(retained, "_source_preparation_metrics", SourcePreparationMetrics())
    object.__setattr__(retained, "_accepted_feature_context", None)
    return retained


def _retain(key, context):
    run_key = key[0]
    with _CACHE_LOCK:
        for existing in tuple(_CACHE):
            if existing[0] == run_key and existing != key:
                _CACHE.pop(existing, None)
        _CACHE[key] = context
    return context


def accepted_source_context(host, student, *, graph=None, source_root=None):
    from bilqis_mlx.factory.live_answers import live_answer_registry
    from bilqis_mlx.runtime import admission as factory_admission
    from bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_checkpoint import (
        require_accepted_authority_checkpoint,
    )
    from bilqis_mlx.runtime.source_execution import SourceExecutionContext
    from bilqis_mlx.source_adapters.school import live_source_registry

    checkpoint = require_accepted_authority_checkpoint(
        student.run_id, host._accepted_cache.accepted_manifest_sha256)
    cache_key = None
    if graph is None:
        cache_key = _cache_key(
            host.run_dir, student, checkpoint.factory_release_sha256, source_root)
        cached = _reuse(cache_key, host)
        if cached is not None:
            return cached
    release_sha256 = checkpoint.factory_release_sha256
    release = factory_admission._read_executable_factory_release_artifact(
        host.run_dir, {
            "factory_release_sha256": release_sha256,
            "factory_release_file": f"factory-releases/{release_sha256}.json",
        })
    if graph is None:
        recorded = student.compiler_features.get("factory_semantic_catalog")
        graph_sha256 = student.compiler_features.get("factory_semantic_graph_sha256")
        catalog_sha256 = student.compiler_features.get("factory_semantic_catalog_sha256")
        if not isinstance(recorded, dict) or catalog_sha256 != release.semantic_catalog_sha256:
            from .atlas_revalidation_common import _invalid
            _invalid("BAMF_ACCEPTED_SEMANTIC_CATALOG_REQUIRED")
        from bilqis_mlx.runtime.state import _fingerprint
        graph = deepcopy(recorded)
        if _fingerprint(graph) != graph_sha256:
            from .atlas_revalidation_common import _invalid
            _invalid("BAMF_ACCEPTED_SEMANTIC_CATALOG_DRIFT")
        try:
            release.verify_semantic_catalog(graph)
        except (TypeError, ValueError):
            from .atlas_revalidation_common import _invalid
            _invalid("BAMF_ACCEPTED_SEMANTIC_CATALOG_DRIFT")
    context = SourceExecutionContext.from_admitted_release(
        host.run_dir, {
            "factory_release_sha256": release_sha256,
            "factory_release_file": f"factory-releases/{release_sha256}.json",
        }, graph=graph, source_root=source_root,
        source_registry=live_source_registry(), answer_registry=live_answer_registry(),
        accepted_runtime_host=host)
    return _retain(cache_key, context) if cache_key is not None else context


__all__ = ("accepted_source_context",)
