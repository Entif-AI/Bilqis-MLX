"""Facade joining authenticated BAMF custody to CP04 and CP06."""
from __future__ import annotations

from pathlib import Path
from functools import partial
import threading
import weakref

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control import MissionControlQueryCatalog

from .native_contracts import AuthenticatedGeneration, NativeProjectionMaterial
from .native_custody import accepted_pointer, authenticated_history
from .native_mapping import accepted_records
from .native_cache.source import _source_token
from .native_cache.rejections import RejectionLedgerCache, LEDGER_CHANGED
from .native_factory import accepted_factory_records
from .native_rejections import rejection_material
from .native_contracts import run_ref
from .observed import observed_records, publish_observed_events
from .projection.memory import accepted_memory_records
from .projection.capability_dossier import (
    accepted_capability_dossiers as _accepted_capability_dossiers,
)
from .projection.semantic_release import (
    AcceptedSemanticProjection, accepted_semantic_release_records,
)
from bilqis_mlx.mission_control.contracts.trainer import TrainerObservation


_SEEN_ATTR = "_cp07_native_event_ids"
_SOURCE_TOKEN_ATTR = "_cp07_native_source_token"
_RUN_REFS_ATTR = "_cp07_native_run_refs"
_ACCEPTED_HEALTH_ATTR = "_cp07_native_accepted_health"
_SERVICE_LOCKS = weakref.WeakKeyDictionary()
_SERVICE_LOCKS_GUARD = threading.Lock()



def _run_refs(records):
    """Recover one stable RunRef per accepted generation from projected records."""
    refs = {}
    for record in records:
        run = record.meta.run
        if run is not None:
            refs[(run.run_id, run.generation_manifest_sha256)] = run
    return tuple(sorted(refs.values(), key=lambda item: (item.run_id, item.generation)))


def _accepted_learning_health(history):
    values = {}
    for generation in history:
        state = generation.learning_health_state
        by_capability = state.get("by_capability") if isinstance(state, dict) else None
        if isinstance(by_capability, dict):
            values[generation.manifest_sha256] = dict(by_capability)
    return values


def _service_lock(service):
    with _SERVICE_LOCKS_GUARD:
        lock = _SERVICE_LOCKS.get(service)
        if lock is None:
            lock = threading.Lock()
            _SERVICE_LOCKS[service] = lock
        return lock


def _project_accepted_base(run_dir, history, *,
                           semantic_projection=accepted_semantic_release_records):
    records, events = [], []
    parent = None
    for generation in history:
        generated, emitted = accepted_records(generation, parent)
        records.extend(generated)
        records.extend(accepted_memory_records(run_dir, generation))
        events.extend(emitted)
        parent = generation
    records.extend(accepted_factory_records(history))
    if history:
        records.extend(semantic_projection(run_dir, history[-1]))
    return NativeProjectionMaterial(
        tuple(records), tuple(events),
        tuple(generation.manifest_sha256 for generation in history),
        _accepted_learning_health(history))


class _AcceptedBaseCache:
    """Retain the expensive accepted/semantic projection across event appends."""

    def __init__(self):
        self.history = self.outbox_token = self.material = None
        self.semantic_projection = AcceptedSemanticProjection()

    def __call__(self, run_dir, history):
        outbox_token = _source_token(run_dir)[3:]
        if self.history is not history or self.outbox_token != outbox_token:
            material = _project_accepted_base(
                run_dir, history, semantic_projection=self.semantic_projection)
            self.history, self.outbox_token, self.material = (
                history, outbox_token, material)
        return self.material


def _materialize_authenticated_history(
        run_dir: Path, history: tuple[AuthenticatedGeneration, ...], *,
        include_live_rejections: bool, accepted_base=_project_accepted_base,
        rejection_source=None,
) -> NativeProjectionMaterial:
    """Project accepted custody, rejection evidence, and the live overlay."""
    run_dir = Path(run_dir)
    base = accepted_base(run_dir, history)
    records, events = list(base.records), list(base.events)
    rejected_records, rejected_events = (
        (rejection_source or rejection_material)(run_dir, history)
        if include_live_rejections
        else rejection_material(run_dir, history, portable_only=True))
    records.extend(_accepted_capability_dossiers(history, rejected_records))
    after = accepted_pointer(run_dir)
    if (not history
            or after["manifest_sha256"] != history[-1].manifest_sha256
            or after["acceptance_sha256"] != history[-1].acceptance_sha256):
        from .native_contracts import invalid
        invalid("CONTROL_PLANE_NATIVE_HISTORY_POINTER_CHANGED")
    accepted_health = base.accepted_learning_health_by_manifest
    if include_live_rejections:
        records.extend(observed_records(
            run_dir, tuple(run_ref(item) for item in history),
            accepted_health_by_manifest=accepted_health))
    records.extend(rejected_records)
    events.extend(rejected_events)
    return NativeProjectionMaterial(
        tuple(records), tuple(events), base.generation_manifests, accepted_health)


def materialize_native_projection(
        run_dir: Path, *, include_live_rejections: bool = False) -> NativeProjectionMaterial:
    """Materialize portable history; optionally add legacy live-only rejection facts."""
    root = Path(run_dir)
    return _materialize_authenticated_history(
        root, authenticated_history(root),
        include_live_rejections=include_live_rejections)


def materialize_current_native_projection(run_dir: Path) -> NativeProjectionMaterial:
    """Materialize cumulative accepted current context plus bounded live observations.

    ``CURRENT`` is a read-model context, not a claim that all useful evidence was
    physically minted in the accepted tip generation.  Build the portable,
    tensor-thin accepted history once, then overlay disposable live observation.
    ``native_query_source`` keeps that accepted base cached so heartbeat-only
    refreshes never replay accepted lineage.
    """
    root = Path(run_dir)
    return _materialize_authenticated_history(
        root, authenticated_history(root), include_live_rejections=True)


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
            LEDGER_CHANGED,
        }:
            return MissionControlQueryCatalog.unavailable()
        raise
    return MissionControlQueryCatalog(material.records)


def native_query_source(run_dir: Path):
    """Reuse accepted CP03 custody while refreshing live observation independently."""
    from .native_cache.source import build_native_query_source

    return build_native_query_source(
        run_dir,
        authenticated_history_fn=authenticated_history,
        materialize_history_fn=partial(
            _materialize_authenticated_history, accepted_base=_AcceptedBaseCache(),
            rejection_source=RejectionLedgerCache()),
        run_refs_fn=_run_refs,
        observed_records_fn=observed_records,
    )


def publish_native_events(service, *, seen_event_ids: set[str] | None = None,
                          material=None):
    """Publish authenticated BAMF deltas exactly once per caller-owned frontier."""
    seen = set() if seen_event_ids is None else seen_event_ids
    if material is None:
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
            previous = getattr(service, _SOURCE_TOKEN_ATTR, None)
            if previous == before:
                return ()
            run_refs = getattr(service, _RUN_REFS_ATTR, ())
            accepted_health = getattr(service, _ACCEPTED_HEALTH_ATTR, {})
            observation_only = (
                previous is not None and previous[:2] == before[:2]
                and previous[3:] == before[3:]
                and run_refs
            )
            seen = getattr(service, _SEEN_ATTR, None)
            material = None
            if observation_only:
                published = publish_observed_events(
                    service, observed_records(
                        service.run_dir, run_refs,
                        accepted_health_by_manifest=accepted_health))
            else:
                source = getattr(service, "_query_source", None)
                shared_material = getattr(source, "_native_material", None)
                if shared_material is not None:
                    material = shared_material()
                    if material is None:
                        return ()
                if seen is None:
                    if material is None:
                        material = materialize_native_projection(
                            service.run_dir, include_live_rejections=True)
                    setattr(service, _SEEN_ATTR, {
                        event_id for _family, _record, event_id in material.events})
                    published = publish_observed_events(service, tuple(
                        record for record in material.records
                        if isinstance(record, TrainerObservation)))
                elif material is None:
                    material, published = publish_native_events(service, seen_event_ids=seen)
                else:
                    material, published = publish_native_events(
                        service, seen_event_ids=seen, material=material)
            after = _source_token(service.run_dir)
            if after == before:
                setattr(service, _SOURCE_TOKEN_ATTR, after)
                if material is not None:
                    setattr(service, _RUN_REFS_ATTR, _run_refs(material.records))
                    setattr(
                        service, _ACCEPTED_HEALTH_ATTR,
                        material.accepted_learning_health_by_manifest or {})
            return published
        except BilqisError as error:
            if error.context.get("reason") in {
                "BAMF_GENERATION_POINTER_CHANGED_DURING_READ",
                "CONTROL_PLANE_NATIVE_HISTORY_POINTER_CHANGED",
                LEDGER_CHANGED,
            }:
                return ()
            raise


__all__ = (
    "AuthenticatedGeneration", "NativeProjectionMaterial", "authenticated_history",
    "materialize_current_native_projection", "materialize_native_projection",
    "native_query_catalog", "native_query_source",
    "publish_native_events", "refresh_native_events",
)
