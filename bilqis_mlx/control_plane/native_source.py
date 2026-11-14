"""Facade joining authenticated BAMF custody to CP04 and CP06."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.errors import BilqisError

from .native_contracts import AuthenticatedGeneration, NativeProjectionMaterial
from .native_custody import authenticated_history
from .native_mapping import accepted_records
from .native_rejections import rejection_material


_SEEN_ATTR = "_cp07_native_event_ids"


def materialize_native_projection(run_dir: Path) -> NativeProjectionMaterial:
    history = authenticated_history(run_dir)
    records, events, manifests = [], [], []
    for generation in history:
        generated, emitted = accepted_records(generation)
        records.extend(generated)
        events.extend(emitted)
        manifests.append(generation.manifest_sha256)
    rejected_records, rejected_events = rejection_material(Path(run_dir), history)
    records.extend(rejected_records)
    events.extend(rejected_events)
    return NativeProjectionMaterial(tuple(records), tuple(events), tuple(manifests))


def publish_native_events(service, *, seen_event_ids: set[str] | None = None):
    """Publish authenticated BAMF deltas exactly once per caller-owned frontier."""
    seen = set() if seen_event_ids is None else seen_event_ids
    material = materialize_native_projection(service.run_dir)
    published = []
    for family, record, event_id in material.events:
        if event_id in seen:
            continue
        emitted = service.publish_event(family, record, event_id=event_id)
        if emitted is not None:
            published.append(emitted)
        seen.add(event_id)
    return material, tuple(published)


def refresh_native_events(service):
    """Refresh one service's delivery frontier without making CP04 authoritative."""
    pointer = service.run_dir / "bamf-state.json"
    if not pointer.exists() and not pointer.is_symlink():
        return ()
    try:
        seen = getattr(service, _SEEN_ATTR, None)
        if seen is None:
            material = materialize_native_projection(service.run_dir)
            setattr(service, _SEEN_ATTR, {
                event_id for _family, _record, event_id in material.events})
            return ()
        _material, published = publish_native_events(service, seen_event_ids=seen)
        return published
    except BilqisError as error:
        if error.context.get("reason") == "BAMF_GENERATION_POINTER_CHANGED_DURING_READ":
            return ()
        raise


__all__ = (
    "AuthenticatedGeneration", "NativeProjectionMaterial", "authenticated_history",
    "materialize_native_projection", "publish_native_events", "refresh_native_events",
)
