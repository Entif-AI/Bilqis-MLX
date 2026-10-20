"""Disk headroom checks; callers never delete or reclaim source artifacts."""
import os
from pathlib import Path
import shutil


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
