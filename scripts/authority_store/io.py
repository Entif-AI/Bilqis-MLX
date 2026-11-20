"""Low-level ordinary-user authority-store custody primitives."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat

from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin
from bilqis_mlx.runtime.bamf_bundle.records import invalid


SCHEMA = "bilqis.mlx.authority-store-lifecycle/v1"
APPROVAL_SCHEMA = "bilqis.mlx.authority-store-approval/v1"
ROLE_AUTHORITY_HOST = "authority-host"
ROLE_WORKER = "worker"
ROLES = frozenset({ROLE_AUTHORITY_HOST, ROLE_WORKER})
INVALID = "BAMF_C09_SOURCE_AUTHORITY_LIFECYCLE_INVALID"
APPROVAL_REQUIRED = "BAMF_C09_SOURCE_AUTHORITY_APPROVAL_REQUIRED"
APPROVAL_INVALID = "BAMF_C09_SOURCE_AUTHORITY_APPROVAL_INVALID"
APPROVAL_FILE = "bilqis-authority-approval.json"
BACKUP_DIR = "bilqis-authority-backups"
_DIGEST = re.compile(r"[0-9a-f]{64}")
_OPERATIONS = frozenset({"install", "restore", "rotate", "migrate"})


@dataclass(frozen=True)
class AuthorityStoreStatus:
    role: str
    registry_sha256: str
    signer_present: bool
    lifecycle_managed: bool
    signer_owner_id: str | None = None
    signer_public_key_hex: str | None = None

    def to_record(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "role": self.role,
            "registry_sha256": self.registry_sha256,
            "signer_present": self.signer_present,
            "lifecycle_managed": self.lifecycle_managed,
            "signer_owner_id": self.signer_owner_id,
            "signer_public_key_hex": self.signer_public_key_hex,
        }


@dataclass(frozen=True)
class AuthorityStoreApproval:
    operation: str
    role: str
    registry_sha256: str
    current_registry_sha256: str | None = None
    signer_owner_id: str | None = None
    signer_public_key_hex: str | None = None

    def __post_init__(self) -> None:
        if (self.operation not in _OPERATIONS
                or self.role not in ROLES
                or _DIGEST.fullmatch(self.registry_sha256) is None
                or (self.current_registry_sha256 is not None
                    and _DIGEST.fullmatch(self.current_registry_sha256) is None)
                or (self.operation in {"rotate", "migrate"})
                    != (self.current_registry_sha256 is not None)
                or (self.role == ROLE_WORKER and self.operation in {"rotate", "migrate"})
                or (self.role == ROLE_AUTHORITY_HOST)
                    != (isinstance(self.signer_owner_id, str)
                        and bool(self.signer_owner_id)
                        and isinstance(self.signer_public_key_hex, str)
                        and _DIGEST.fullmatch(self.signer_public_key_hex) is not None)
                or (self.role == ROLE_WORKER
                    and (self.signer_owner_id is not None
                         or self.signer_public_key_hex is not None))):
            fail(APPROVAL_INVALID)


def fail(reason: str = INVALID):
    invalid(reason)


def ensure_root() -> tuple[int, Path]:
    euid, home = darwin._effective_account_home()
    parent = Path(home) / darwin._AUTHORITY_DIR[0]
    root = parent / darwin._AUTHORITY_DIR[1]
    for path in (parent, root):
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if (path.is_symlink() or not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != euid or info.st_mode & 0o022):
                fail()
        else:
            path.mkdir(mode=0o700)
    return euid, root


def ensure_backup_root() -> tuple[int, Path]:
    euid, home = darwin._effective_account_home()
    parent = Path(home) / darwin._AUTHORITY_DIR[0]
    backup = parent / BACKUP_DIR
    for path in (parent, backup):
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if (path.is_symlink() or not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != euid or info.st_mode & 0o077):
                fail()
        else:
            path.mkdir(mode=0o700)
    return euid, backup


def fixed_backup_path(registry_sha256: str) -> Path:
    if _DIGEST.fullmatch(registry_sha256) is None:
        fail()
    _euid, root = ensure_backup_root()
    return root / registry_sha256


def require_private_directory(path: Path, *, expected_uid: int) -> None:
    try:
        info = path.lstat()
    except OSError:
        fail()
    if (path.is_symlink() or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != expected_uid or info.st_mode & 0o077):
        fail()


def fixed_approval_path() -> tuple[int, Path]:
    """Resolve the non-caller-selectable operator approval record."""
    euid, home = darwin._effective_account_home()
    return euid, Path(home) / darwin._AUTHORITY_DIR[0] / APPROVAL_FILE


def read_fixed_approval() -> AuthorityStoreApproval:
    euid, path = fixed_approval_path()
    if not path.exists() and not path.is_symlink():
        fail(APPROVAL_REQUIRED)
    raw = read_file(
        path,
        max_bytes=16 * 1024,
        expected_uid=euid,
        require_private=True,
    )
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail(APPROVAL_INVALID)
    if (not isinstance(record, dict)
            or set(record) != {
                "schema", "operation", "role", "registry_sha256",
                "current_registry_sha256", "signer_owner_id",
                "signer_public_key_hex",
            }
            or record.get("schema") != APPROVAL_SCHEMA):
        fail(APPROVAL_INVALID)
    return AuthorityStoreApproval(
        record["operation"],
        record["role"],
        record["registry_sha256"],
        record["current_registry_sha256"],
        record["signer_owner_id"],
        record["signer_public_key_hex"],
    )


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


def validate_signer(
    raw: bytes,
    registry,
    *,
    expected_owner_id: str | None = None,
    expected_public_key_hex: str | None = None,
) -> tuple[str, str]:
    try:
        record = json.loads(raw.decode("utf-8"))
        if (not isinstance(record, dict)
                or set(record) != {"schema", "owner_id", "private_key_hex"}
                or record.get("schema") != "bilqis.mlx.source-authority-signer/v1"):
            fail()
        from bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer import (
            HostSourceAuthoritySigner,
        )
        signer = HostSourceAuthoritySigner(
            record["owner_id"], record["private_key_hex"], registry)
        if not any(
            key.owner_id == signer.owner_id
            and key.public_key_hex == signer.public_key_hex
            for key in registry.keys
        ):
            fail()
    except Exception:
        fail()
    if (expected_owner_id is not None and signer.owner_id != expected_owner_id
            or expected_public_key_hex is not None
            and signer.public_key_hex != expected_public_key_hex):
        fail(APPROVAL_INVALID)
    return signer.owner_id, signer.public_key_hex


def read_file(
    path: Path,
    *,
    max_bytes: int,
    expected_uid: int | None = None,
    require_private: bool = True,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        fail()
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode)
                or expected_uid is not None and info.st_uid != expected_uid
                or require_private and info.st_mode & 0o077
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
    "APPROVAL_FILE", "APPROVAL_INVALID", "APPROVAL_REQUIRED", "APPROVAL_SCHEMA",
    "BACKUP_DIR",
    "AuthorityStoreApproval", "AuthorityStoreStatus", "INVALID",
    "ROLE_AUTHORITY_HOST", "ROLE_WORKER", "ROLES", "SCHEMA",
    "ensure_backup_root", "ensure_root", "fail", "fixed_approval_path",
    "fixed_backup_path", "fsync_dir", "parse_registry", "read_file",
    "read_fixed_approval", "replace_json", "require_private_directory",
    "validate_signer", "write_exact",
)
