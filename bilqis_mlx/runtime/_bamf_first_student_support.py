"""Private path and model-authority helpers for first-student launch."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY, MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.runtime.bamf_bundle.genesis.foundation import initial_foundation_sidecars
from bilqis_mlx.runtime.model_topology_v2 import (
    b01_generation_authority, b01_generation_extents,
)
from ._bamf_first_student_contracts import (
    BamfFoundationDashboardProjection, DashboardMetrics, _invalid,
)

def _canonical_run_dir_shape(new_run_dir) -> Path:
    try:
        path = Path(new_run_dir).expanduser()
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            _invalid("BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED")
        return path.resolve()
    except (TypeError, OSError, PermissionError, RuntimeError):
        _invalid("BAMF_FIRST_STUDENT_TARGET_PATH_INVALID")


def _fresh_run_dir(new_run_dir) -> Path:
    path = _canonical_run_dir_shape(new_run_dir)
    try:
        if path.is_dir() and any(path.iterdir()):
            _invalid("BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED")
        return path
    except (OSError, PermissionError, RuntimeError):
        _invalid("BAMF_FIRST_STUDENT_TARGET_PATH_INVALID")


def _resolved_run_path(value, *, reason: str) -> Path:
    try:
        return Path(value).expanduser().resolve()
    except (TypeError, OSError, PermissionError, RuntimeError):
        _invalid(reason)


def _physical_directory_chain(path: Path, *, reason: str) -> tuple[Path, tuple[tuple[int, int], ...]]:
    """Return the deepest existing physical directory and its ancestor identities."""
    try:
        current = Path(path).expanduser()
        while not current.exists():
            if current.parent == current:
                _invalid(reason)
            current = current.parent
        physical = current.resolve(strict=True)
        if not physical.is_dir():
            _invalid(reason)
        identities = []
        cursor = physical
        while True:
            stat = cursor.stat()
            identities.append((stat.st_dev, stat.st_ino))
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
        return physical, tuple(identities)
    except (TypeError, OSError, PermissionError, RuntimeError):
        _invalid(reason)


def _canonical_disjoint_run_paths(source_run_dir: str, new_run_dir) -> tuple[Path, Path]:
    try:
        source_input = Path(source_run_dir).expanduser()
    except (TypeError, OSError, RuntimeError):
        _invalid("BAMF_FIRST_STUDENT_SOURCE_PATH_INVALID")
    try:
        target_input = Path(new_run_dir).expanduser()
    except (TypeError, OSError, RuntimeError):
        _invalid("BAMF_FIRST_STUDENT_TARGET_PATH_INVALID")
    if target_input.is_symlink():
        _invalid("BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED")
    source, source_chain = _physical_directory_chain(
        source_input, reason="BAMF_FIRST_STUDENT_SOURCE_PATH_INVALID")
    if not source_input.exists():
        _invalid("BAMF_FIRST_STUDENT_SOURCE_PATH_INVALID")
    source_identity = source.stat().st_dev, source.stat().st_ino
    target_probe = (
        target_input.parent
        if target_input.exists() and not target_input.is_dir() else target_input)
    target_existing, target_chain = _physical_directory_chain(
        target_probe, reason="BAMF_FIRST_STUDENT_TARGET_PATH_INVALID")
    target = _resolved_run_path(
        target_input, reason="BAMF_FIRST_STUDENT_TARGET_PATH_INVALID")
    if (source_identity in target_chain
            or (target_input.exists() and target_input.is_dir()
                and (target_existing.stat().st_dev, target_existing.stat().st_ino)
                in source_chain)):
        _invalid("BAMF_FIRST_STUDENT_TARGET_OVERLAPS_SOURCE")
    return source, target


def _dashboard_metrics_from_projection(
        projection: BamfFoundationDashboardProjection) -> DashboardMetrics:
    return DashboardMetrics(
        optimizer_step=projection.optimizer_step,
        grade_visits=projection.grade_visits,
        stage=projection.stage,
        active_grades=projection.active_grades,
        current_grade=projection.current_grade,
        last_run_status=projection.last_run_status,
    )


def _model_authority(release, admission, graph, run_seed, foundation_features,
                     provenance):
    semantic_abi, compiler_features, *_ = initial_foundation_sidecars(
        release, admission, graph, run_seed=run_seed,
        feature_authority=foundation_features)
    allocations = MotifAllocationSnapshot(MotifManifest(provenance.release_digest))
    extents = b01_generation_extents(
        semantic_abi=semantic_abi,
        compiler_features=compiler_features,
        motif_page_count=allocations.manifest.capacity // INITIAL_MOTIF_CAPACITY,
        motif_key_map_digest=allocations.manifest.digest,
    )
    return b01_generation_authority(extents)
