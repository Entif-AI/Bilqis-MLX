"""Disk headroom checks; callers never delete or reclaim source artifacts."""
import os
from dataclasses import dataclass
from pathlib import Path
import shutil

from bilqis_mlx.errors import ErrorBus, SCHOOL

BUNDLE_BUDGET_SCHEMA = "bilqis.c08.next-bundle-budget/v1"
RETAINED_DISK_RESERVE_BYTES = 100 * 1024**3
ADAMW_MOMENT_COPIES = 2


def _bundle_invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_RESOURCES.INVALID, reason=reason)


@dataclass(frozen=True)
class BundleBudget:
    weights_bytes: int
    optimizer_moments_bytes: int
    manifest_bytes: int
    publication_overhead_bytes: int
    schema_version: str = BUNDLE_BUDGET_SCHEMA

    def __post_init__(self):
        if (any(type(value) is not int or value < 0 for value in (
                self.weights_bytes, self.optimizer_moments_bytes,
                self.manifest_bytes, self.publication_overhead_bytes))
                or self.weights_bytes == 0
                or self.schema_version != BUNDLE_BUDGET_SCHEMA):
            _bundle_invalid("BAMF_C08_BUNDLE_BUDGET_INVALID")

    @property
    def total_bytes(self) -> int:
        return (self.weights_bytes + self.optimizer_moments_bytes
                + self.manifest_bytes + self.publication_overhead_bytes)


def estimate_next_bundle_bytes(
    census, *, manifest_bytes: int, publication_overhead_bytes: int,
    tensor_bytes: int = 4,
    optimizer_moment_copies: int = ADAMW_MOMENT_COPIES,
) -> BundleBudget:
    """Require explicit checkpoint overhead; never lower the disk reserve."""
    from .model_topology_v2 import ParameterCensus

    if (not isinstance(census, ParameterCensus)
            or type(tensor_bytes) is not int or tensor_bytes < 1
            or type(optimizer_moment_copies) is not int
            or optimizer_moment_copies < ADAMW_MOMENT_COPIES):
        _bundle_invalid("BAMF_C08_BUNDLE_CENSUS_INVALID")
    weights = census.total * tensor_bytes
    return BundleBudget(
        weights_bytes=weights,
        optimizer_moments_bytes=weights * optimizer_moment_copies,
        manifest_bytes=manifest_bytes,
        publication_overhead_bytes=publication_overhead_bytes)


def assert_bundle_headroom(path: Path, budget: BundleBudget) -> dict:
    """Report the complete next bundle and refuse writes below 100 GiB floor."""
    if not isinstance(budget, BundleBudget):
        _bundle_invalid("BAMF_C08_BUNDLE_BUDGET_INVALID")
    snapshot = assert_headroom(
        path, required_bytes=budget.total_bytes, reserve_gib=100.0)
    return {
        **snapshot,
        "sufficient": True,
        "required_next_bundle_bytes": budget.total_bytes,
        "weights_bytes": budget.weights_bytes,
        "optimizer_moments_bytes": budget.optimizer_moments_bytes,
        "manifest_bytes": budget.manifest_bytes,
        "publication_overhead_bytes": budget.publication_overhead_bytes,
    }


def headroom_snapshot(path: Path, *, required_bytes: int = 0,
                      reserve_gib: float = 100.0) -> dict:
    """Read-only budget witness usable by both operator and checkpoint guard."""
    if required_bytes < 0 or not 0 <= reserve_gib <= 100_000:
        raise ValueError("INVALID_DISK_BUDGET")
    location = Path(path)
    while not location.exists():
        if location.parent == location:
            raise ValueError("NO_EXISTING_DISK_PARENT")
        location = location.parent
    available = shutil.disk_usage(location).free
    reserve = int(reserve_gib * 1024**3)
    return {"free_bytes": available, "reserve_bytes": reserve,
            "estimated_write_bytes": required_bytes,
            "sufficient": available >= required_bytes + reserve}


def assert_headroom(path: Path, *, required_bytes: int = 0,
                    reserve_gib: float = 100.0) -> dict:
    report = headroom_snapshot(path, required_bytes=required_bytes,
                               reserve_gib=reserve_gib)
    if not report["sufficient"]:
        raise RuntimeError("DISK_BUDGET_EXHAUSTED")
    return {key: report[key] for key in
            ("free_bytes", "reserve_bytes", "estimated_write_bytes")}


def atomic_text(path: Path, content: str):
    """Create a new durable file only. Never replace a saved run receipt."""
    from uuid import uuid4
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + "." + uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        os.link(temp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temp.unlink(missing_ok=True)
