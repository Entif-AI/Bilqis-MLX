"""Independent host custody for the C09 source-authority trust root."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile

from .records import canonical, invalid


SOURCE_AUTHORITY_REGISTRY_FILE = "source-authority-registry.json"
SOURCE_AUTHORITY_REGISTRY_LOCK = ".source-authority-registry.lock"
_MAX_REGISTRY_BYTES = 256 * 1024


@contextlib.contextmanager
def source_authority_registry_lock(run_dir: Path):
    """Serialize the project-owned trust-root provisioner with authority leases."""
    from ._publication_storage import _require_run_root

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


def provision_source_authority_registry(run_dir: Path, registry) -> Path:
    """Install the host root once; later provisioning may only be idempotent."""
    from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
    if type(registry) is not SourceAuthorityRegistry:
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    root = Path(run_dir)
    with source_authority_registry_lock(root):
        current = _read_provisioned_source_authority_registry_unlocked(root)
        if current is not None:
            if current != registry:
                invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_IMMUTABLE")
            return root / SOURCE_AUTHORITY_REGISTRY_FILE
        raw = canonical(registry.to_record())
        fd, temporary = tempfile.mkstemp(
            prefix=".source-authority-registry.", suffix=".tmp", dir=root)
        temporary_path = Path(temporary)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            target = root / SOURCE_AUTHORITY_REGISTRY_FILE
            os.replace(temporary_path, target)
            directory = os.open(root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return target
        finally:
            if temporary_path.exists():
                temporary_path.unlink()


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
    "provision_source_authority_registry",
    "read_provisioned_source_authority_registry",
    "require_provisioned_source_authority_registry",
    "source_authority_registry_lock",
)
