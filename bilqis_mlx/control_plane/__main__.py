"""Run the BAMF CP01 service independently of any GUI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bilqis_mlx.paths import active_run_dir
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.control_plane.native_source import native_query_source
from bilqis_mlx.mission_control import MissionControlQueryCatalog
from bilqis_mlx.control_plane.notifications import (
    sync_akasha_notifications, sync_native_transition_notifications,
)

from .discovery import discover_learner
from .service import ControlPlaneService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local BAMF control plane.")
    parser.add_argument("--run-dir", type=Path, default=active_run_dir())
    parser.add_argument("--socket", type=Path)
    parser.add_argument("--projection-db", type=Path,
                        help="Optional disposable CP06 index for bounded queries")
    return parser


def _default_socket(run_dir: Path) -> Path:
    run_dir = Path(run_dir).expanduser().resolve()
    return run_dir.parent / f".{run_dir.name}.control-plane.sock"


def _notification_projection(run_dir: Path) -> MissionControlProjection:
    path = run_dir.parent / f".{run_dir.name}.mission-control-notifications.sqlite3"
    return (
        MissionControlProjection(path)
        if path.exists()
        else MissionControlProjection.create_empty(path)
    )


def _composed_query_source(run_dir: Path, projection: MissionControlProjection):
    native = native_query_source(run_dir)

    def source(query=None):
        sync_akasha_notifications(run_dir, projection)
        catalog = native(query)
        if not catalog.available:
            return catalog
        sync_native_transition_notifications(run_dir, projection)
        return MissionControlQueryCatalog((*catalog.records, *projection.notifications()))

    source._bilqis_query_aware = True
    source._native_material = getattr(native, "_native_material", None)
    return source


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    socket_path = args.socket or _default_socket(args.run_dir)
    notification_projection = (
        MissionControlProjection(args.projection_db)
        if args.projection_db is not None
        else _notification_projection(args.run_dir)
    )
    query_source = (
        notification_projection.catalog
        if args.projection_db is not None
        else _composed_query_source(args.run_dir, notification_projection)
    )
    service = ControlPlaneService(
        args.run_dir, socket_path, query_source=query_source,
        notification_projection=notification_projection)
    print(json.dumps({
        "schema": "bilqis.bamf.control-plane.started/v1",
        "service": service.identity.to_record(),
        "learner": discover_learner(service.run_dir).to_record(),
    }, sort_keys=True), flush=True)
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        service.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
