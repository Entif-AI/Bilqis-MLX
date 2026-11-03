"""Immutable content-addressed file objects owned by the shared data plane."""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path

from .contracts import DataPlaneError, HASH_CHUNK_BYTES, SHA256_HEX_LENGTH, _error


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_BYTES):
            value.update(chunk)
    return value.hexdigest()


def _valid_digest(value: object) -> bool:
    return (isinstance(value, str) and len(value) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class DataPlaneFileObjectMixin:
    """Persist large immutable payloads without duplicating them in SQLite."""

    def file_object_destination(self, digest: str) -> Path:
        """Return the deterministic CAS destination without creating it."""
        if not _valid_digest(digest):
            raise ValueError(DataPlaneError.OBJECT_DIGEST_INVALID.value)
        root = self.path.with_name(self.path.name + ".objects")
        return root / digest[:2] / (digest + ".safetensors")

    def _file_object_root(self, *, create: bool) -> Path:
        root = self.path.with_name(self.path.name + ".objects")
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise ValueError(_error(DataPlaneError.OBJECT_CORRUPTED, root))
        if create:
            root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise ValueError(_error(DataPlaneError.OBJECT_MISSING, root))
        return root

    def _file_object_path(self, digest: str, *, create: bool) -> Path:
        if not _valid_digest(digest):
            raise ValueError(DataPlaneError.OBJECT_DIGEST_INVALID.value)
        root = self._file_object_root(create=create)
        shard = root / digest[:2]
        if shard.is_symlink() or (shard.exists() and not shard.is_dir()):
            raise ValueError(_error(DataPlaneError.OBJECT_CORRUPTED, shard))
        if create:
            shard.mkdir(exist_ok=True)
        if not shard.is_dir():
            raise ValueError(_error(DataPlaneError.OBJECT_MISSING, digest))
        return shard / (digest + ".safetensors")

    def require_file_object(self, digest: str) -> Path:
        """Return one verified immutable file object or fail closed."""
        target = self._file_object_path(digest, create=False)
        if target.is_symlink() or not target.is_file():
            raise ValueError(_error(DataPlaneError.OBJECT_MISSING, digest))
        if _digest(target) != digest:
            raise ValueError(_error(DataPlaneError.OBJECT_CORRUPTED, digest))
        return target

    def _copy_file_object(self, source: Path, target: Path, digest: str) -> None:
        temporary = target.with_name("." + digest + "." + uuid.uuid4().hex + ".tmp")
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                shutil.copyfileobj(reader, writer, HASH_CHUNK_BYTES)
                writer.flush()
                os.fsync(writer.fileno())
            if _digest(temporary) != digest:
                raise ValueError(_error(DataPlaneError.OBJECT_DIGEST_INVALID, digest))
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        finally:
            if temporary.exists() or temporary.is_symlink():
                temporary.unlink()

    def adopt_file_object(self, source: Path, digest: str) -> Path:
        """Persist a completed file once under its content address."""
        source = Path(source)
        if source.is_symlink() or not source.is_file():
            raise ValueError(_error(DataPlaneError.OBJECT_MISSING, source))
        if not _valid_digest(digest) or _digest(source) != digest:
            raise ValueError(DataPlaneError.OBJECT_DIGEST_INVALID.value)
        with self._lock:
            target = self._file_object_path(digest, create=True)
            if not (target.exists() or target.is_symlink()):
                self._copy_file_object(source, target, digest)
            self.require_file_object(digest)
            # Persist every directory entry before a generation can reference it.
            for directory in (target.parent, target.parent.parent, self.path.parent):
                _fsync_directory(directory)
            return target
