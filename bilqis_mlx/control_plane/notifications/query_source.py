"""Compose native query custody and the rebuildable notification projection."""
from pathlib import Path
from threading import Lock

from bilqis_mlx.mission_control import MissionControlQueryCatalog
from bilqis_mlx.mission_control.projection import MissionControlProjection

from ..native_cache.source import _source_token
from ..native_source import native_query_source
from .source import sync_akasha_notifications, sync_native_transition_notifications


def notification_projection(run_dir: Path) -> MissionControlProjection:
    path = run_dir.parent / f".{run_dir.name}.mission-control-notifications.sqlite3"
    return (
        MissionControlProjection(path)
        if path.exists()
        else MissionControlProjection.create_empty(path)
    )


def _projection_identity(projection):
    stat = projection.path.stat()
    return stat.st_dev, stat.st_ino


def composed_query_source(run_dir: Path, projection: MissionControlProjection):
    """Reuse native custody and refresh each notice source at its own frontier."""
    native = native_query_source(run_dir)
    lock = Lock()
    previous_history = outbox_token = projection_identity = None
    previous_catalog = previous_notices = composed = None

    def source(query=None):
        nonlocal previous_history, outbox_token, projection_identity
        nonlocal previous_catalog, previous_notices, composed
        with lock:
            catalog, history = native._native_snapshot(query)
            if not catalog.available:
                return catalog
            identity = _projection_identity(projection)
            if identity != projection_identity:
                previous_history = outbox_token = None
                projection_identity = identity
            before = _source_token(run_dir)[3:]
            if before != outbox_token:
                sync_akasha_notifications(run_dir, projection)
                after = _source_token(run_dir)[3:]
                outbox_token = after if before == after else None
            if history is not previous_history:
                sync_native_transition_notifications(
                    run_dir, projection, history=history)
                previous_history = history
            # Acknowledgments and event-derived notices may change independently
            # of the learner. Read them even when both source frontiers are stable.
            notices = projection.notifications()
            if catalog is not previous_catalog or notices != previous_notices:
                composed = MissionControlQueryCatalog((*catalog.records, *notices))
                previous_catalog, previous_notices = catalog, notices
            return composed

    source._bilqis_query_aware = True
    source._native_material = native._native_material
    return source
