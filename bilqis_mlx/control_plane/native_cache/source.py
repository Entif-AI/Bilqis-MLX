"""Mutable-overlay cache for the native CURRENT Mission Control source."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import threading
import time

from bilqis_mlx.mission_control.contracts.trainer_parts.base import TrainerObservation
from ..observed.source import MAX_HEARTBEAT_AGE_MS

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control import MissionControlQueryCatalog
from bilqis_mlx.mission_control.query_selection import is_live_overlay
from ..observed.school import ObservedSchoolProjection
from ..projection.school import admitted_release_identity
from .rejections import LEDGER_CHANGED


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
            token.append((name, stat.st_dev, stat.st_ino, stat.st_size,
                          stat.st_mtime_ns, stat.st_ctime_ns))
        except FileNotFoundError:
            token.append((name, None, None, None, None, None))
    return tuple(token)


def _base_source_token(token):
    return token[:2] + token[3:]


class _NativeQueryCache:
    def __init__(
            self, run_dir, authenticated_history_fn, materialize_history_fn,
            run_refs_fn, observed_records_fn):
        self.root = Path(run_dir).expanduser().resolve()
        self.lock = threading.Lock()
        self.authenticated_history = authenticated_history_fn
        self.materialize_history = materialize_history_fn
        self.run_refs = run_refs_fn
        self.observed_records = observed_records_fn
        self.token = self.catalog = self.base_token = self.pointer_token = None
        self.base_records = ()
        self.base_catalog = None
        self.run_ref_values = ()
        self.accepted_health = {}
        self.history = ()
        self.material = None
        self.school_projection = None
        self.live_deadline = None
        self.release_identity = None

    def query(self, request=None):
        return self.snapshot(request)[0]

    def snapshot(self, request=None):
        """Pair the catalog with the exact authenticated history used to build it."""
        with self.lock:
            catalog = self._current()
            return catalog, self.history if catalog.available else ()

    def event_material(self):
        with self.lock:
            catalog = self._current()
            if not catalog.available or self.material is None:
                return None
            return replace(self.material, records=catalog.records)

    def _current(self):
        before = _source_token(self.root)
        if (self.history and self.pointer_token == before[0]
                and self.release_identity != admitted_release_identity(self.root, self.history)):
            self._clear_base()
        if (self.catalog is not None and self.token == before
                and (self.live_deadline is None or time.time() < self.live_deadline)):
            return self.catalog
        reused = self._reuse_base(before)
        if reused is not None:
            return reused
        return self._materialize(_source_token(self.root))

    def _remember_catalog(self, token, catalog):
        self.token, self.catalog = token, catalog
        # File identity alone cannot prove a heartbeat is still live.
        self.live_deadline = min((
            row.meta.observed_at + MAX_HEARTBEAT_AGE_MS / 1000
            for row in catalog.records
            if isinstance(row, TrainerObservation)
            and row.connection_state == "LIVE"
            and row.meta.observed_at is not None
        ), default=None)

    def _reuse_base(self, before):
        base = _base_source_token(before)
        if self.base_token != base or not self.run_ref_values:
            return None
        observed = self.observed_records(
            self.root, self.run_ref_values,
            accepted_health_by_manifest=self.accepted_health,
            school_projection=self.school_projection)
        catalog = self.base_catalog.with_records(observed)
        after = _source_token(self.root)
        if self.release_identity != admitted_release_identity(self.root, self.history):
            self._clear_base()
            return MissionControlQueryCatalog.unavailable()
        if _base_source_token(after) != base:
            return None
        if after == before:
            self._remember_catalog(after, catalog)
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
        try:
            history = self._accepted_history(before)
            if history is None:
                return MissionControlQueryCatalog.unavailable()
            release_before = admitted_release_identity(self.root, history)
            material = self.materialize_history(
                self.root, history, include_live_rejections=True)
        except BilqisError as error:
            if error.context.get("reason") in {
                "BAMF_GENERATION_POINTER_CHANGED_DURING_READ",
                "CONTROL_PLANE_NATIVE_HISTORY_POINTER_CHANGED",
                LEDGER_CHANGED,
            }:
                return MissionControlQueryCatalog.unavailable()
            raise
        base_records = tuple(
            record for record in material.records
            if not is_live_overlay(record))
        observed = tuple(
            record for record in material.records
            if is_live_overlay(record))
        refs = self.run_refs(base_records)
        health = material.accepted_learning_health_by_manifest or {}
        base_catalog = self.base_catalog
        if (base_catalog is None or self.pointer_token != before[0]
                or self.base_records != base_records):
            base_catalog = MissionControlQueryCatalog(base_records)
        catalog = base_catalog.with_records(observed)
        after = _source_token(self.root)
        if after[0] != before[0]:
            self.history, self.pointer_token = (), None
            self._clear_base()
            return MissionControlQueryCatalog.unavailable()
        self.history, self.pointer_token = history, before[0]
        if admitted_release_identity(self.root, history) != release_before:
            self._clear_base()
            return MissionControlQueryCatalog.unavailable()
        self.release_identity = release_before
        self.material = material
        if _base_source_token(after) != _base_source_token(before):
            self._clear_base()
            return catalog
        return self._cache_stable_base(
            before, after, base_records, refs, health, catalog, base_catalog)

    def _cache_stable_base(
            self, before, after, base_records, refs, health, catalog, base_catalog):
        self.base_token = _base_source_token(before)
        self.base_records = base_records
        self.base_catalog = base_catalog
        self.school_projection = ObservedSchoolProjection(base_records)
        self.run_ref_values = refs
        self.accepted_health = health
        if after == before or not refs:
            self._remember_catalog(after, catalog)
            return catalog
        observed = self.observed_records(
            self.root, refs, accepted_health_by_manifest=health,
            school_projection=self.school_projection)
        catalog = base_catalog.with_records(observed)
        final = _source_token(self.root)
        if final[0] != before[0]:
            self.history, self.pointer_token = (), None
            self._clear_base()
            return MissionControlQueryCatalog.unavailable()
        if self.release_identity != admitted_release_identity(self.root, self.history):
            self._clear_base()
            return MissionControlQueryCatalog.unavailable()
        if _base_source_token(final) == self.base_token and final == after:
            self._remember_catalog(final, catalog)
        else:
            self.token = self.catalog = None
        return catalog

    def _clear_base(self):
        self.base_token = self.token = self.catalog = None
        self.base_records = self.run_ref_values = ()
        self.base_catalog = None
        self.accepted_health = {}
        self.school_projection = None
        self.release_identity = None


def build_native_query_source(
        run_dir: Path, *, authenticated_history_fn, materialize_history_fn,
        run_refs_fn, observed_records_fn):
    cache = _NativeQueryCache(
        run_dir, authenticated_history_fn, materialize_history_fn,
        run_refs_fn, observed_records_fn)

    def source(query=None):
        return cache.query(query)

    source._bilqis_query_aware = True
    source._native_material = cache.event_material
    source._native_snapshot = cache.snapshot
    return source


__all__ = ("build_native_query_source",)
