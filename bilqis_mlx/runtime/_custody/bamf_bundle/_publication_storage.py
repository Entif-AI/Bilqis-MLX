"""Private crash-safe filesystem primitives for BAMF generation publication."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
import uuid
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError, SHA256_HEX_LENGTH
from bilqis_mlx.learning.atlas_acceptance import AcceptedCandidateBinding

from .codec import validate_bamf_bundle_custody
from .records import (
    BAMF_POINTER_SCHEMA, LEGACY_BAMF_POINTER_SCHEMA, canonical, invalid,
)

ACCEPTANCE_DIR = "bamf-acceptance"


def _fsync_directory(path: Path) -> None:
    directory = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _require_run_root(run_dir: Path) -> None:
    if run_dir.is_symlink() or (run_dir.exists() and not run_dir.is_dir()):
        invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)
    created: list[Path] = []
    ancestor = run_dir
    while not ancestor.exists():
        created.append(ancestor)
        ancestor = ancestor.parent
    run_dir.mkdir(parents=True, exist_ok=True)
    if run_dir.is_symlink() or not run_dir.is_dir():
        invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)
    if created:
        for directory in created:
            _fsync_directory(directory)
        _fsync_directory(ancestor)


def _require_bundle_root(run_dir: Path, *, create: bool) -> Path:
    root = run_dir / "bamf-bundles"
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    existed = root.exists()
    if create:
        root.mkdir(exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    if create and not existed:
        _fsync_directory(root)
        _fsync_directory(run_dir)
    return root


@contextlib.contextmanager
def _pointer_lock(run_dir: Path):
    _require_run_root(run_dir)
    lock = run_dir / ".bamf-pointer.lock"
    if lock.is_symlink():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            invalid("BAMF_POINTER_WRITER_ACTIVE")
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read_pointer(path: Path) -> dict | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    try:
        pointer = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid()
    bundle_value = pointer.get("bundle") if isinstance(pointer, dict) else None
    bundle = Path(bundle_value) if isinstance(bundle_value, str) else Path()
    base_fields = {"schema", "run_id", "generation",
                   "parent_manifest_sha256", "bundle", "manifest_sha256"}
    schema = pointer.get("schema") if isinstance(pointer, dict) else None
    expected = (base_fields | {"acceptance_sha256"}
                if schema == BAMF_POINTER_SCHEMA else base_fields)
    if (not isinstance(pointer, dict) or set(pointer) != expected
            or schema not in {BAMF_POINTER_SCHEMA, LEGACY_BAMF_POINTER_SCHEMA}
            or (schema == BAMF_POINTER_SCHEMA
                and (not isinstance(pointer.get("acceptance_sha256"), str)
                     or len(pointer["acceptance_sha256"]) != SHA256_HEX_LENGTH
                     or any(c not in "0123456789abcdef"
                            for c in pointer["acceptance_sha256"])))
            or not isinstance(pointer.get("run_id"), str) or not pointer["run_id"]
            or type(pointer.get("generation")) is not int or bundle.is_absolute()
            or bundle_value != f"bamf-bundles/{pointer.get('manifest_sha256')}"
            or tuple(bundle.parts) != ("bamf-bundles", pointer.get("manifest_sha256"))
            or any(part in ("", ".", "..") for part in bundle.parts)):
        invalid()
    return pointer


def _live_bundle_manifest(run_dir: Path, pointer: dict) -> dict:
    root = _require_bundle_root(run_dir, create=False)
    bundle = root / pointer["manifest_sha256"]
    manifest = validate_bamf_bundle_custody(
        bundle, expected_manifest_sha256=pointer["manifest_sha256"])
    if (manifest["run_id"] != pointer["run_id"]
            or manifest["generation"] != pointer["generation"]
            or manifest["parent_manifest_sha256"] != pointer["parent_manifest_sha256"]):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return manifest


def _atomic_pointer(path: Path, pointer: dict) -> None:
    if path.is_symlink():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    raw = canonical(pointer)
    fd, temporary = tempfile.mkstemp(prefix=".bamf-pointer-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _stage(run_dir: Path) -> Path:
    _require_run_root(run_dir)
    root = run_dir / ".bamf-staging"
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    root.mkdir(exist_ok=True)
    return root / ("generation-" + uuid.uuid4().hex)


def _acceptance_path(run_dir: Path, manifest_sha256: str) -> Path:
    root = run_dir / ACCEPTANCE_DIR
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    existed = root.exists()
    root.mkdir(exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    if not existed:
        _fsync_directory(root)
        _fsync_directory(run_dir)
    return root / f"{manifest_sha256}.json"


def _write_acceptance(run_dir: Path, manifest_sha256: str,
                      acceptance: AcceptedCandidateBinding) -> None:
    path = _acceptance_path(run_dir, manifest_sha256)
    raw = canonical(acceptance.to_record())
    if path.is_symlink():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
        _fsync_directory(path.parent)
        return
    fd, temporary = tempfile.mkstemp(prefix=".bamf-acceptance-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
