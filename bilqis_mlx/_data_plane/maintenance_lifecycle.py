"""Crash-recovery markers for automatic workstation data-plane maintenance."""
from __future__ import annotations

import hashlib
from pathlib import Path
import uuid

from .maintenance import register_maintenance_root

_MAINTENANCE_PENDING_PREFIX = "maintenance_pending_v1:"


def _pending_key(root: Path) -> str:
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    return _MAINTENANCE_PENDING_PREFIX + digest


def mark_maintenance_pending(plane, run_dir: Path) -> str:
    """Mark an operator epoch dirty until post-lock maintenance succeeds."""
    root = register_maintenance_root(plane, run_dir)
    token = uuid.uuid4().hex
    with plane.transaction():
        plane._db.execute(
            "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
            (_pending_key(root), token),
        )
    return token


def maintenance_pending_token(plane, run_dir: Path) -> str | None:
    root = Path(run_dir).expanduser().resolve(strict=True)
    row = plane._db.execute(
        "SELECT value FROM meta WHERE key=?",
        (_pending_key(root),),
    ).fetchone()
    return row[0] if row is not None else None


def clear_maintenance_pending(plane, run_dir: Path, token: str) -> None:
    """Clear only the operator epoch this cleanup actually serviced."""
    root = Path(run_dir).expanduser().resolve(strict=True)
    with plane.transaction():
        plane._db.execute(
            "DELETE FROM meta WHERE key=? AND value=?",
            (_pending_key(root), token),
        )
