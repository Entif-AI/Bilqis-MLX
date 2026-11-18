"""Scoped autonomy-state currentness for one lawful teaching frontier."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from bilqis_mlx.factory.autonomy import (
    AutonomyPlan,
    EvidenceLedger,
    is_factory_release,
)
from bilqis_mlx.factory.model import FactoryRelease
from bilqis_mlx.runtime.autonomy_state import (
    POINTER_SCHEMA,
    read_autonomy_state,
)


_ISSUER = object()


def _file_identity(path: Path) -> tuple[int, int, int, int, int]:
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError
        info = path.stat()
    except OSError as exc:
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_DRIFT") from exc
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _snapshot(run_dir: Path, release: FactoryRelease):
    if not is_factory_release(release):
        raise TypeError("AUTONOMY_STATE_INVALID_RELEASE")
    root = Path(run_dir)
    current = root / "autonomy" / "current.json"
    try:
        pointer_identity = _file_identity(current)
        pointer = json.loads(current.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_DRIFT") from exc
    if (not isinstance(pointer, dict)
            or pointer.get("schema") != POINTER_SCHEMA
            or pointer.get("factory_release_sha256") != release.release_sha256):
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_DRIFT")
    relative = pointer.get("state_file")
    if not isinstance(relative, str):
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_DRIFT")
    parts = Path(relative).parts
    if len(parts) != 3 or parts[:2] != ("autonomy", "states"):
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_DRIFT")
    state_path = (root / relative).resolve()
    return pointer_identity, state_path, _file_identity(state_path), pointer


@dataclass(frozen=True, init=False, eq=False)
class _AutonomyCurrentness:
    run_dir: Path
    release_sha256: str
    pointer_identity: tuple
    state_path: Path
    state_identity: tuple
    _issuance: object = field(repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_CALLER_CONSTRUCTION_FORBIDDEN")


def bind_autonomy_currentness(
        run_dir: Path, release: FactoryRelease, *, plan: AutonomyPlan,
        ledger: EvidenceLedger) -> _AutonomyCurrentness:
    """Deep-validate once, then bind the exact pointer and immutable state file."""
    before = _snapshot(run_dir, release)
    restored_plan, restored_ledger = read_autonomy_state(run_dir, release)
    after = _snapshot(run_dir, release)
    if before != after or restored_plan != plan or restored_ledger != ledger:
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_DRIFT")
    pointer_identity, state_path, state_identity, pointer = after
    if (pointer.get("autonomy_plan_sha256") != plan.digest()
            or pointer.get("receipt_count") != len(ledger.receipts)
            or pointer.get("intervention_count", 0) != len(ledger.interventions)
            or pointer.get("rejected_attempt_count", 0)
               != len(ledger.rejected_attempts)):
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_DRIFT")
    witness = object.__new__(_AutonomyCurrentness)
    for name, value in (
        ("run_dir", Path(run_dir).resolve()),
        ("release_sha256", release.release_sha256),
        ("pointer_identity", pointer_identity),
        ("state_path", state_path),
        ("state_identity", state_identity),
        ("_issuance", _ISSUER),
    ):
        object.__setattr__(witness, name, value)
    return witness


def require_autonomy_currentness(
        witness, release: FactoryRelease) -> _AutonomyCurrentness:
    """Reject any pointer or immutable-state movement without a full decode."""
    if (type(witness) is not _AutonomyCurrentness
            or getattr(witness, "_issuance", None) is not _ISSUER
            or not is_factory_release(release)
            or release.release_sha256 != witness.release_sha256):
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_DRIFT")
    current = witness.run_dir / "autonomy" / "current.json"
    if (_file_identity(current) != witness.pointer_identity
            or _file_identity(witness.state_path) != witness.state_identity):
        raise ValueError("AUTONOMY_STATE_CURRENTNESS_DRIFT")
    return witness


_bind_autonomy_currentness = bind_autonomy_currentness
_require_autonomy_currentness = require_autonomy_currentness
