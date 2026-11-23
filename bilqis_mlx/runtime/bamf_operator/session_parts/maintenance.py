"""Bounded data-plane maintenance around an operator session."""
from pathlib import Path


def _emit_progress(progress, message):
    if progress is not None:
        progress(message)


def training_memory_context():
    import mlx.core as mx
    from bilqis_mlx.runtime.mlx_memory import training_memory_policy
    return training_memory_policy(mx)


def run_post_operator_maintenance(
        run_dir: Path, *, progress=None, expected_token: str | None = None):
    """Best-effort bounded storage maintenance after the trainer lock is released."""
    try:
        from types import SimpleNamespace
        from bilqis_mlx._data_plane.cli import _maintenance
        from bilqis_mlx._data_plane.maintenance import maintenance_roots
        from bilqis_mlx._data_plane.maintenance_lifecycle import (
            clear_maintenance_pending,
        )
        from bilqis_mlx.data_plane import data_plane

        run_dir = Path(run_dir)
        if not ((run_dir / "bamf-state.json").is_file()
                or (run_dir / "state.json").is_file()):
            return None
        plane = data_plane()
        roots = maintenance_roots(plane, run_dir)
        result = _maintenance(SimpleNamespace(
            scan_root=list(roots),
            apply=True,
            scope="all",
            max_records=0,
            vacuum=False,
        ))
        if expected_token is not None:
            clear_maintenance_pending(plane, run_dir, expected_token)
    except Exception as error:
        _emit_progress(
            progress,
            f"post-operator data-plane maintenance deferred: {error}",
        )
        return None
    _emit_progress(
        progress,
        "post-operator data-plane maintenance completed: "
        f"{result.get('gc', {}).get('reclaimable_object_bytes', 0)} object bytes, "
        f"{result.get('gc', {}).get('reclaimable_node_bytes', 0)} node bytes, "
        f"{result.get('file_gc', {}).get('reclaimable_file_bytes', 0)} file bytes",
    )
    return result


def run_pending_operator_maintenance(
        run_dir: Path, *, progress=None, post_maintenance=run_post_operator_maintenance):
    """Recover cleanup left pending by a prior hard process death."""
    run_dir = Path(run_dir)
    if not ((run_dir / "bamf-state.json").is_file()
            or (run_dir / "state.json").is_file()):
        return None
    try:
        from bilqis_mlx._data_plane.maintenance_lifecycle import (
            maintenance_pending_token,
        )
        from bilqis_mlx.data_plane import data_plane
        token = maintenance_pending_token(data_plane(), run_dir)
    except Exception as error:
        _emit_progress(
            progress,
            f"pending data-plane maintenance deferred: {error}",
        )
        return None
    if token is None:
        return None
    return post_maintenance(
        run_dir, progress=progress, expected_token=token)
