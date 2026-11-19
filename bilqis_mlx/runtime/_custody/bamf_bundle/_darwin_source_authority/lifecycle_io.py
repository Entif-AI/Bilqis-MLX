"""Low-level ordinary-user authority-store custody primitives."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat

from . import _AUTHORITY_DIR, _effective_account_home
from ..records import invalid


SCHEMA = "bilqis.mlx.authority-store-lifecycle/v1"
ROLE_AUTHORITY_HOST = "authority-host"
ROLE_WORKER = "worker"
ROLES = frozenset({ROLE_AUTHORITY_HOST, ROLE_WORKER})
INVALID = "BAMF_C09_SOURCE_AUTHORITY_LIFECYCLE_INVALID"


@dataclass(frozen=True)
class AuthorityStoreStatus:
    role: str
    registry_sha256: str
    signer_present: bool
    lifecycle_managed: bool

    def to_record(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "role": self.role,
            "registry_sha256": self.registry_sha256,
            "signer_present": self.signer_present,
            "lifecycle_managed": self.lifecycle_managed,
        }


def fail(reason: str = INVALID):
    invalid(reason)


def ensure_root() -> tuple[int, Path]:
    euid, home = _effective_account_home()
    parent = Path(home) / _AUTHORITY_DIR[0]
    root = parent / _AUTHORITY_DIR[1]
    for path in (parent, root):
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if (path.is_symlink() or not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != euid or info.st_mode & 0o022):
                fail()
        else:
            path.mkdir(mode=0o700)
    return euid, root


def write_exact(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, mode)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                fail()
            view = view[written:]
        os.fsync(fd)
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def replace_json(path: Path, record: dict[str, object]) -> None:
    temp = path.with_name(path.name + ".new")
    if temp.exists() or temp.is_symlink():
        temp.unlink()
    write_exact(
        temp,
        (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )
    os.replace(temp, path)


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def parse_registry(raw: bytes):
    try:
        record = json.loads(raw.decode("utf-8"))
        from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
        return SourceAuthorityRegistry.from_record(record)
    except Exception:
        fail()


def validate_signer(raw: bytes, registry) -> None:
    try:
        record = json.loads(raw.decode("utf-8"))
        from .._darwin_salience_signer import HostSourceAuthoritySigner
        HostSourceAuthoritySigner(
            record["owner_id"], record["private_key_hex"], registry)
    except Exception:
        fail()


def read_file(path: Path, *, max_bytes: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        fail()
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                or not 1 <= info.st_size <= max_bytes):
            fail()
        chunks = []
        remaining = info.st_size + 1
        while remaining:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) != info.st_size:
            fail()
        return payload
    except OSError:
        fail()
    finally:
        os.close(fd)


__all__ = (
    "AuthorityStoreStatus", "INVALID", "ROLE_AUTHORITY_HOST", "ROLE_WORKER",
    "ROLES", "SCHEMA", "ensure_root", "fail", "fsync_dir", "parse_registry",
    "read_file", "replace_json", "validate_signer", "write_exact",
)
