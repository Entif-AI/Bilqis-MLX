"""Mutable-overlay cache for the native CURRENT Mission Control source."""
from __future__ import annotations

from pathlib import Path
import threading

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control import MissionControlQueryCatalog, QueryMode
from bilqis_mlx.mission_control.contracts.trainer import TrainerObservation


def _source_token(run_dir: Path):
    root = Path(run_dir)
    token = []
    for name in (
        "bamf-state.json", "events.jsonl", "trainer-observed.json",
        "akasha-outbox.sqlite3", "akasha-outbox.sqlite3-wal",
    ):
        path = root / name
        try:
            stat = path.stat()
            token.append((name, stat.st_ino, stat.st_size, stat.st_mtime_ns))
        except FileNotFoundError:
            token.append((name, None, None, None))
    return tuple(token)


def _base_source_token(token):
    return token[:2] + token[3:]


def build_native_query_source(
        run_dir: Path, *, authenticated_history_fn, materialize_history_fn,
        materialize_projection_fn, run_refs_fn, observed_records_fn):
    root = Path(run_dir).expanduser().resolve()
    lock = threading.Lock()
    cached_token = cached_catalog = cached_base_token = cached_pointer_token = None
    cached_base_records = ()
    cached_run_refs = ()
    cached_accepted_health = {}
    cached_history = ()

    def source(query=None):
        nonlocal cached_token, cached_catalog, cached_base_token
        nonlocal cached_pointer_token, cached_base_records, cached_run_refs
        nonlocal cached_accepted_health, cached_history
        with lock:
            if query is not None and query.mode is not QueryMode.CURRENT:
                material = materialize_projection_fn(
                    root, include_live_rejections=True)
                return MissionControlQueryCatalog(material.records)

            before = _source_token(root)
            if cached_catalog is not None and cached_token == before:
                return cached_catalog

            before_base = _base_source_token(before)
            if cached_base_token == before_base and cached_run_refs:
                observed = observed_records_fn(
                    root, cached_run_refs,
                    accepted_health_by_manifest=cached_accepted_health)
                catalog = MissionControlQueryCatalog(
                    (*cached_base_records, *observed))
                after_observed = _source_token(root)
                if _base_source_token(after_observed) == before_base:
                    if after_observed == before:
                        cached_token, cached_catalog = after_observed, catalog
                    else:
                        cached_token = cached_catalog = None
                    return catalog
                before, before_base = after_observed, _base_source_token(after_observed)

            pointer = root / "bamf-state.json"
            if not pointer.exists() and not pointer.is_symlink():
                return MissionControlQueryCatalog.unavailable()

            accepted_unchanged = (
                bool(cached_history) and cached_pointer_token == before[0])
            try:
                history = (
                    cached_history if accepted_unchanged
                    else authenticated_history_fn(root))
                material = materialize_history_fn(
                    root, history, include_live_rejections=True)
            except BilqisError as error:
                if error.context.get("reason") in {
                    "BAMF_GENERATION_POINTER_CHANGED_DURING_READ",
                    "CONTROL_PLANE_NATIVE_HISTORY_POINTER_CHANGED",
                }:
                    return MissionControlQueryCatalog.unavailable()
                raise

            base_records = tuple(
                record for record in material.records
                if not isinstance(record, TrainerObservation))
            observed = tuple(
                record for record in material.records
                if isinstance(record, TrainerObservation))
            run_refs = run_refs_fn(base_records)
            accepted_health = material.accepted_learning_health_by_manifest or {}
            catalog = MissionControlQueryCatalog((*base_records, *observed))
            after = _source_token(root)

            cached_history = history
            cached_pointer_token = after[0]
            if _base_source_token(after) != before_base:
                cached_base_token = cached_token = cached_catalog = None
                cached_base_records = cached_run_refs = ()
                cached_accepted_health = {}
                return catalog

            cached_base_token = before_base
            cached_base_records = base_records
            cached_run_refs = run_refs
            cached_accepted_health = accepted_health
            if after != before and run_refs:
                observed = observed_records_fn(
                    root, run_refs,
                    accepted_health_by_manifest=accepted_health)
                catalog = MissionControlQueryCatalog((*base_records, *observed))
                final = _source_token(root)
                if _base_source_token(final) == before_base and final == after:
                    cached_token, cached_catalog = final, catalog
                else:
                    cached_token = cached_catalog = None
            else:
                cached_token, cached_catalog = after, catalog
            return catalog

    source._bilqis_query_aware = True
    return source


__all__ = ("build_native_query_source",)
