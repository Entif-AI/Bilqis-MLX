"""Facade joining authenticated BAMF custody to CP04 and CP06."""
from __future__ import annotations

from pathlib import Path
import threading
import weakref

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control import MissionControlQueryCatalog

from .native_contracts import AuthenticatedGeneration, NativeProjectionMaterial
from .native_custody import accepted_pointer, authenticated_history
from .native_mapping import accepted_records
from .native_rejections import rejection_material
from .native_contracts import run_ref
from .observed import observed_records, publish_observed_events
from bilqis_mlx.mission_control.contracts.trainer import TrainerObservation


_SEEN_ATTR = "_cp07_native_event_ids"
_SOURCE_TOKEN_ATTR = "_cp07_native_source_token"
_SERVICE_LOCKS = weakref.WeakKeyDictionary()
_SERVICE_LOCKS_GUARD = threading.Lock()



def _source_token(run_dir: Path):
    """Cheap change detector for mutable CP07 observation inputs."""
    root = Path(run_dir)
    token = []
    for name in ("bamf-state.json", "events.jsonl", "trainer-observed.json"):
        path = root / name
        try:
            stat = path.stat()
            token.append((name, stat.st_ino, stat.st_size, stat.st_mtime_ns))
        except FileNotFoundError:
            token.append((name, None, None, None))
    return tuple(token)

def _service_lock(service):
    with _SERVICE_LOCKS_GUARD:
        lock = _SERVICE_LOCKS.get(service)
        if lock is None:
            lock = threading.Lock()
            _SERVICE_LOCKS[service] = lock
        return lock


def materialize_native_projection(
        run_dir: Path, *, include_live_rejections: bool = False) -> NativeProjectionMaterial:
    """Materialize portable accepted history; optionally add live rejection facts."""
    history = authenticated_history(run_dir)
    records, events, manifests = [], [], []
    parent = None
    for generation in history:
        generated, emitted = accepted_records(generation, parent)
        records.extend(generated)
        events.extend(emitted)
        manifests.append(generation.manifest_sha256)
        parent = generation
    rejected_records, rejected_events = (
        rejection_material(Path(run_dir), history)
        if include_live_rejections else ((), ()))
    after = accepted_pointer(Path(run_dir))
    if (not history
            or after["manifest_sha256"] != history[-1].manifest_sha256
            or after["acceptance_sha256"] != history[-1].acceptance_sha256):
        from .native_contracts import invalid
        invalid("CONTROL_PLANE_NATIVE_HISTORY_POINTER_CHANGED")
    if include_live_rejections:
        records.extend(observed_records(run_dir, tuple(run_ref(item) for item in history)))
    records.extend(rejected_records)
    events.extend(rejected_events)
    return NativeProjectionMaterial(tuple(records), tuple(events), tuple(manifests))


def native_query_catalog(run_dir: Path) -> MissionControlQueryCatalog:
    """Build the current CP03 catalog directly from authenticated BAMF custody."""
    root = Path(run_dir).expanduser().resolve()
    pointer = root / "bamf-state.json"
    if not pointer.exists() and not pointer.is_symlink():
        return MissionControlQueryCatalog.unavailable()
    try:
        material = materialize_native_projection(root, include_live_rejections=True)
    except BilqisError as error:
        if error.context.get("reason") in {
            "BAMF_GENERATION_POINTER_CHANGED_DURING_READ",
            "CONTROL_PLANE_NATIVE_HISTORY_POINTER_CHANGED",
        }:
            return MissionControlQueryCatalog.unavailable()
        raise
    return MissionControlQueryCatalog(material.records)


def native_query_source(run_dir: Path):
    """Reuse one authenticated CP03 catalog until mutable source custody changes."""
    root = Path(run_dir).expanduser().resolve()
    lock = threading.Lock()
    cached_token = None
    cached_catalog = None

    def source():
        nonlocal cached_token, cached_catalog
        with lock:
            before = _source_token(root)
            if cached_catalog is not None and cached_token == before:
                return cached_catalog
            catalog = native_query_catalog(root)
            after = _source_token(root)
            if after == before:
                cached_token = after
                cached_catalog = catalog
            return catalog

    return source


def publish_native_events(service, *, seen_event_ids: set[str] | None = None):
    """Publish authenticated BAMF deltas exactly once per caller-owned frontier."""
    seen = set() if seen_event_ids is None else seen_event_ids
    material = materialize_native_projection(
        service.run_dir, include_live_rejections=True)
    published = list(publish_observed_events(service, tuple(
        record for record in material.records if isinstance(record, TrainerObservation))))
    resource_pending = False
    for family, record, event_id in material.events:
        if event_id in seen:
            continue
        emitted = service.publish_event(family, record, event_id=event_id)
        if emitted is not None:
            published.append(emitted)
        elif family.value == "resource.health.sample":
            resource_pending = True
        seen.add(event_id)
    if resource_pending:
        emitted = service.flush_event_telemetry()
        if emitted is not None:
            published.append(emitted)
    return material, tuple(published)


def refresh_native_events(service):
    """Refresh one service's delivery frontier without making CP04 authoritative."""
    pointer = service.run_dir / "bamf-state.json"
    if not pointer.exists() and not pointer.is_symlink():
        return ()
    with _service_lock(service):
        try:
            before = _source_token(service.run_dir)
            if getattr(service, _SOURCE_TOKEN_ATTR, None) == before:
                return ()
            seen = getattr(service, _SEEN_ATTR, None)
            if seen is None:
                material = materialize_native_projection(
                    service.run_dir, include_live_rejections=True)
                setattr(service, _SEEN_ATTR, {
                    event_id for _family, _record, event_id in material.events})
                published = publish_observed_events(service, tuple(
                    record for record in material.records
                    if isinstance(record, TrainerObservation)))
            else:
                _material, published = publish_native_events(service, seen_event_ids=seen)
            after = _source_token(service.run_dir)
            if after == before:
                setattr(service, _SOURCE_TOKEN_ATTR, after)
            return published
        except BilqisError as error:
            if error.context.get("reason") in {
                "BAMF_GENERATION_POINTER_CHANGED_DURING_READ",
                "CONTROL_PLANE_NATIVE_HISTORY_POINTER_CHANGED",
            }:
                return ()
            raise


__all__ = (
    "AuthenticatedGeneration", "NativeProjectionMaterial", "authenticated_history",
    "materialize_native_projection", "native_query_catalog", "native_query_source",
    "publish_native_events", "refresh_native_events",
)
