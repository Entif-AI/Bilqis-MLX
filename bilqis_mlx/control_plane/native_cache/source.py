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


class _NativeQueryCache:
    def __init__(
            self, run_dir, authenticated_history_fn, materialize_history_fn,
            materialize_projection_fn, run_refs_fn, observed_records_fn):
        self.root = Path(run_dir).expanduser().resolve()
        self.lock = threading.Lock()
        self.authenticated_history = authenticated_history_fn
        self.materialize_history = materialize_history_fn
        self.materialize_projection = materialize_projection_fn
        self.run_refs = run_refs_fn
        self.observed_records = observed_records_fn
        self.token = self.catalog = self.base_token = self.pointer_token = None
        self.base_records = ()
        self.run_ref_values = ()
        self.accepted_health = {}
        self.history = ()

    def query(self, request=None):
        with self.lock:
            if request is not None and request.mode is not QueryMode.CURRENT:
                material = self.materialize_projection(
                    self.root, include_live_rejections=True)
                return MissionControlQueryCatalog(material.records)
            return self._current()

    def _current(self):
        before = _source_token(self.root)
        if self.catalog is not None and self.token == before:
            return self.catalog
        reused = self._reuse_base(before)
        if reused is not None:
            return reused
        return self._materialize(_source_token(self.root))

    def _reuse_base(self, before):
        base = _base_source_token(before)
        if self.base_token != base or not self.run_ref_values:
            return None
        observed = self.observed_records(
            self.root, self.run_ref_values,
            accepted_health_by_manifest=self.accepted_health)
        catalog = MissionControlQueryCatalog((*self.base_records, *observed))
        after = _source_token(self.root)
        if _base_source_token(after) != base:
            return None
        if after == before:
            self.token, self.catalog = after, catalog
        else:
            self.token = self.catalog = None
        return catalog

    def _accepted_history(self, before):
        pointer = self.root / "bamf-state.json"
        if not pointer.exists() and not pointer.is_symlink():
            return None
        if self.history and self.pointer_token == before[0]:
            return self.history
        return self.authenticated_history(self.root)

    def _materialize(self, before):
        history = self._accepted_history(before)
        if history is None:
            return MissionControlQueryCatalog.unavailable()
        try:
            material = self.materialize_history(
                self.root, history, include_live_rejections=True)
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
        refs = self.run_refs(base_records)
        health = material.accepted_learning_health_by_manifest or {}
        catalog = MissionControlQueryCatalog((*base_records, *observed))
        after = _source_token(self.root)
        self.history, self.pointer_token = history, after[0]
        if _base_source_token(after) != _base_source_token(before):
            self._clear_base()
            return catalog
        return self._cache_stable_base(
            before, after, base_records, refs, health, catalog)

    def _cache_stable_base(
            self, before, after, base_records, refs, health, catalog):
        self.base_token = _base_source_token(before)
        self.base_records = base_records
        self.run_ref_values = refs
        self.accepted_health = health
        if after == before or not refs:
            self.token, self.catalog = after, catalog
            return catalog
        observed = self.observed_records(
            self.root, refs, accepted_health_by_manifest=health)
        catalog = MissionControlQueryCatalog((*base_records, *observed))
        final = _source_token(self.root)
        if _base_source_token(final) == self.base_token and final == after:
            self.token, self.catalog = final, catalog
        else:
            self.token = self.catalog = None
        return catalog

    def _clear_base(self):
        self.base_token = self.token = self.catalog = None
        self.base_records = self.run_ref_values = ()
        self.accepted_health = {}


def build_native_query_source(
        run_dir: Path, *, authenticated_history_fn, materialize_history_fn,
        materialize_projection_fn, run_refs_fn, observed_records_fn):
    cache = _NativeQueryCache(
        run_dir, authenticated_history_fn, materialize_history_fn,
        materialize_projection_fn, run_refs_fn, observed_records_fn)

    def source(query=None):
        return cache.query(query)

    source._bilqis_query_aware = True
    return source


__all__ = ("build_native_query_source",)
