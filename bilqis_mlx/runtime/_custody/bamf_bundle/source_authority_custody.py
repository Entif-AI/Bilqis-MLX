"""Independent host custody for the C09 source-authority trust root."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
from pathlib import Path
import stat

from .records import invalid


SOURCE_AUTHORITY_REGISTRY_FILE = "source-authority-registry.json"
SOURCE_AUTHORITY_REGISTRY_LOCK = ".source-authority-registry.lock"
_MAX_REGISTRY_BYTES = 256 * 1024


@contextlib.contextmanager
def source_authority_registry_lock(run_dir: Path):
    """Serialize the project-owned trust-root provisioner with authority leases."""
    from .publication.storage import _require_run_root

    root = Path(run_dir)
    _require_run_root(root)
    path = root / SOURCE_AUTHORITY_REGISTRY_LOCK
    if path.is_symlink():
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    fd = os.open(
        path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            invalid("BAMF_C09_SOURCE_AUTHORITY_WRITER_ACTIVE")
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read_provisioned_source_authority_registry_unlocked(run_dir: Path):
    path = Path(run_dir) / SOURCE_AUTHORITY_REGISTRY_FILE
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode)
                or info.st_size <= 0 or info.st_size > _MAX_REGISTRY_BYTES):
            invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
        raw = os.read(fd, info.st_size + 1)
        if len(raw) != info.st_size:
            invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    except OSError:
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    finally:
        os.close(fd)
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
    return SourceAuthorityRegistry.from_record(record)


def read_provisioned_source_authority_registry(run_dir: Path):
    """Read trusted registry material provisioned outside generation publication."""
    with source_authority_registry_lock(run_dir):
        return _read_provisioned_source_authority_registry_unlocked(run_dir)


def _bind_host_source_authority_registry(run_dir: Path, correction_frontier):
    """Project an already-provisioned host trust root into accepted custody material.

    This never writes or selects registry material.  The only authority source is the
    host-owned file already present under ``run_dir``; callers can supply only the run
    root and the owner-derived correction frontier that will be bound to it.
    """
    if not isinstance(correction_frontier, dict):
        invalid("BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID")
    if (correction_frontier.get("source_authority_registry") is not None
            or correction_frontier.get("source_authority_registry_sha256") is not None):
        invalid("BAMF_C09_SOURCE_AUTHORITY_BINDING_INVALID")
    registry_path = Path(run_dir) / SOURCE_AUTHORITY_REGISTRY_FILE
    if not registry_path.exists() and not registry_path.is_symlink():
        return dict(correction_frontier)
    trusted = read_provisioned_source_authority_registry(run_dir)
    if trusted is None:
        return dict(correction_frontier)
    return {
        **correction_frontier,
        "source_authority_registry_sha256": trusted.digest,
        "source_authority_registry": trusted.to_record(),
    }


def require_provisioned_source_authority_registry(
        run_dir: Path, correction_frontier):
    """Bind candidate/live C09 material to an independent host-provisioned root."""
    with source_authority_registry_lock(run_dir):
        return _require_provisioned_source_authority_registry_unlocked(
            run_dir, correction_frontier)


def _require_provisioned_source_authority_registry_unlocked(
        run_dir: Path, correction_frontier):
    trusted = _read_provisioned_source_authority_registry_unlocked(run_dir)
    record = correction_frontier.get("source_authority_registry")
    digest = correction_frontier.get("source_authority_registry_sha256")
    if trusted is None:
        if record is not None or digest is not None:
            invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED")
        return None
    if record is None or digest is None:
        invalid("BAMF_C09_SOURCE_AUTHORITY_BINDING_REQUIRED")
    from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
    candidate = SourceAuthorityRegistry.from_record(record)
    if candidate.digest != digest or candidate != trusted:
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH")
    return trusted


__all__ = (
    "SOURCE_AUTHORITY_REGISTRY_FILE",
    "SOURCE_AUTHORITY_REGISTRY_LOCK",
    "_require_provisioned_source_authority_registry_unlocked",
    "read_provisioned_source_authority_registry",
    "require_provisioned_source_authority_registry",
    "source_authority_registry_lock",
)
