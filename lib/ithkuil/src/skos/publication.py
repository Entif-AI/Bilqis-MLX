"""Publish one immutable compiler generation, then atomically select it (#43)."""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .errors import ProfileError


BUNDLE_SCHEMA = "bilqis.skos.build-bundle/v1"
POINTER_SCHEMA = "bilqis.skos.build-pointer/v1"
REQUIRED_FILES = frozenset({"canonical.nt", "held.json", "digest.json", "input.json"})
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]*\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


@dataclass(frozen=True)
class ArtifactBundle:
    manifest: bytes
    files: tuple[tuple[str, bytes], ...]

    @property
    def bundle_id(self) -> str:
        return hashlib.sha256(self.manifest).hexdigest()

    def metadata(self) -> dict:
        return json.loads(self.manifest)


def make_bundle(files: dict[str, bytes], metadata: dict) -> ArtifactBundle:
    if not isinstance(files, dict) or not isinstance(metadata, dict):
        raise ProfileError("INVALID_COMPILER_ARTIFACT_SET")
    if set(files) != REQUIRED_FILES or any(
        not SAFE_NAME.fullmatch(name) or name == "manifest.json" for name in files
    ):
        raise ProfileError("INVALID_COMPILER_ARTIFACT_SET")
    if any(not isinstance(value, bytes) for value in files.values()):
        raise ProfileError("COMPILER_ARTIFACT_BYTES_REQUIRED")
    manifest = {**metadata, "schema": BUNDLE_SCHEMA, "files": {
        name: {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
        for name, payload in sorted(files.items())
    }}
    return ArtifactBundle(json_bytes(manifest), tuple(sorted(files.items())))


def _write_synced(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _manifest(payload: bytes, bundle_id: str) -> dict:
    try:
        metadata = json.loads(payload)
    except (ValueError, TypeError, UnicodeError) as error:
        raise ProfileError("COMPILER_MANIFEST_MISMATCH") from error
    if (not isinstance(metadata, dict) or hashlib.sha256(payload).hexdigest() != bundle_id
            or metadata.get("schema") != BUNDLE_SCHEMA):
        raise ProfileError("COMPILER_MANIFEST_MISMATCH")
    files = metadata.get("files")
    if not isinstance(files, dict) or set(files) != REQUIRED_FILES:
        raise ProfileError("INVALID_COMPILER_ARTIFACT_SET")
    for name, receipt in files.items():
        if (not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or name == "manifest.json"
                or not isinstance(receipt, dict) or type(receipt.get("bytes")) is not int
                or receipt["bytes"] < 0 or not isinstance(receipt.get("sha256"), str)
                or not HEX64.fullmatch(receipt["sha256"])):
            raise ProfileError("INVALID_COMPILER_ARTIFACT_RECEIPT")
    return metadata


def _verify_generation(directory: Path, bundle_id: str) -> dict:
    if not HEX64.fullmatch(bundle_id) or directory.is_symlink() or not directory.is_dir():
        raise ProfileError("INVALID_COMPILER_GENERATION")
    try:
        manifest_path = directory / "manifest.json"
        if manifest_path.is_symlink():
            raise ProfileError("INVALID_COMPILER_GENERATION")
        payload = manifest_path.read_bytes()
        metadata = _manifest(payload, bundle_id)
        files = metadata["files"]
        expected_names = {*files, "manifest.json"}
        if {path.name for path in directory.iterdir()} != expected_names:
            raise ProfileError("COMPILER_GENERATION_CONTENT_DRIFT")
        for name, receipt in sorted(files.items()):
            if not SAFE_NAME.fullmatch(name) or name == "manifest.json":
                raise ProfileError("INVALID_COMPILER_ARTIFACT_SET")
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise ProfileError("COMPILER_ARTIFACT_NOT_REGULAR", name)
            content = path.read_bytes()
            if len(content) != receipt["bytes"] or hashlib.sha256(content).hexdigest() != receipt["sha256"]:
                raise ProfileError("COMPILER_ARTIFACT_DIGEST_MISMATCH", name)
        return metadata
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, ProfileError):
            raise
        raise ProfileError("COMPILER_GENERATION_READBACK_FAILED", type(error).__name__) from error


def verify_publication(output_root: str | Path) -> dict:
    root = Path(output_root)
    try:
        current = root / "CURRENT.json"
        generations = root / "generations"
        if root.is_symlink() or current.is_symlink() or generations.is_symlink():
            raise ProfileError("COMPILER_OUTPUT_SYMLINK_FORBIDDEN")
        pointer_payload = current.read_bytes()
        pointer = json.loads(pointer_payload)
        if not isinstance(pointer, dict):
            raise ProfileError("INVALID_COMPILER_POINTER")
        bundle_id = pointer["bundle_id"]
        if (pointer.get("schema") != POINTER_SCHEMA or not isinstance(bundle_id, str)
                or not HEX64.fullmatch(bundle_id) or pointer.get("path") != "generations/" + bundle_id):
            raise ProfileError("INVALID_COMPILER_POINTER")
        expected_pointer = json_bytes({"schema": POINTER_SCHEMA, "bundle_id": bundle_id,
                                       "path": "generations/" + bundle_id})
        if pointer_payload != expected_pointer:
            raise ProfileError("INVALID_COMPILER_POINTER")
        metadata = _verify_generation(generations / bundle_id, bundle_id)
        return {"bundle_id": bundle_id, "path": pointer["path"], "metadata": metadata}
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, ProfileError):
            raise
        raise ProfileError("COMPILER_POINTER_READBACK_FAILED", type(error).__name__) from error


def _verify_committed(root: Path, expected_bundle_id: str, *, sync_failed: bool) -> dict:
    try:
        receipt = verify_publication(root)
    except Exception as error:
        raise ProfileError(
            "COMPILER_PUBLICATION_COMMITTED_READBACK_REQUIRED", expected_bundle_id
        ) from error
    if receipt.get("bundle_id") != expected_bundle_id:
        raise ProfileError("COMPILER_PUBLICATION_COMMITTED_READBACK_REQUIRED", expected_bundle_id)
    if sync_failed:
        return {**receipt, "durability_warning": {"code": "DIRSYNC_UNCONFIRMED"}}
    return receipt


def publish_bundle(bundle: ArtifactBundle, output_root: str | Path) -> dict:
    if not isinstance(bundle, ArtifactBundle) or not isinstance(bundle.manifest, bytes):
        raise ProfileError("INVALID_COMPILER_BUNDLE")
    metadata = _manifest(bundle.manifest, bundle.bundle_id)
    files = dict(bundle.files)
    if len(files) != len(bundle.files) or set(files) != set(metadata["files"]):
        raise ProfileError("INVALID_COMPILER_ARTIFACT_SET")
    for name, payload in files.items():
        receipt = metadata["files"][name]
        if (not isinstance(payload, bytes) or len(payload) != receipt["bytes"]
                or hashlib.sha256(payload).hexdigest() != receipt["sha256"]):
            raise ProfileError("COMPILER_ARTIFACT_DIGEST_MISMATCH", name)
    root = Path(output_root)
    if root.is_symlink():
        raise ProfileError("COMPILER_OUTPUT_SYMLINK_FORBIDDEN")
    if root.exists() and not root.is_dir():
        raise ProfileError("OUTPUT_ROOT_NOT_DIRECTORY")
    root.mkdir(parents=True, exist_ok=True)
    staging: Path | None = None
    pointer_temp: Path | None = None
    with (root / ".publish.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ProfileError("COMPILER_OUTPUT_BUSY") from error
        try:
            generations = root / "generations"
            current = root / "CURRENT.json"
            if generations.is_symlink() or current.is_symlink():
                raise ProfileError("COMPILER_OUTPUT_SYMLINK_FORBIDDEN")
            if current.exists():
                verify_publication(root)
            generations.mkdir(exist_ok=True)
            _sync_directory(root)
            target = generations / bundle.bundle_id
            if target.exists():
                metadata = _verify_generation(target, bundle.bundle_id)
                if metadata != bundle.metadata():
                    raise ProfileError("COMPILER_GENERATION_CONFLICT")
            else:
                staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=generations))
                for name, payload in (*bundle.files, ("manifest.json", bundle.manifest)):
                    if not SAFE_NAME.fullmatch(name):
                        raise ProfileError("INVALID_COMPILER_ARTIFACT_SET")
                    _write_synced(staging / name, payload)
                _verify_generation(staging, bundle.bundle_id)
                _sync_directory(staging)
                os.replace(staging, target)
                staging = None
                _sync_directory(generations)
            pointer = json_bytes({"schema": POINTER_SCHEMA, "bundle_id": bundle.bundle_id,
                                  "path": "generations/" + bundle.bundle_id})
            if not current.exists() or current.read_bytes() != pointer:
                descriptor, temporary = tempfile.mkstemp(prefix=".current-", dir=root)
                pointer_temp = Path(temporary)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(pointer)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(pointer_temp, current)
                pointer_temp = None
                sync_failed = False
                try:
                    _sync_directory(root)
                except OSError:
                    sync_failed = True
                return _verify_committed(root, bundle.bundle_id, sync_failed=sync_failed)
            return verify_publication(root)
        finally:
            if staging is not None and staging.exists():
                shutil.rmtree(staging)
            if pointer_temp is not None and pointer_temp.exists():
                pointer_temp.unlink()
