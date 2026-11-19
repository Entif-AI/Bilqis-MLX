"""Operator-owned lifecycle for the fixed ordinary-user C09 authority store.

This module hardens the *custody* of the #1031 fixed path.  It never chooses
semantic authority, generates trust roots, or lets a caller redirect production
runtime reads.  Every install is pinned to an already-approved registry digest.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Protocol

from . import (
    _REGISTRY_FILE,
    _SIGNER_FILE,
    _TRANSACTION_FILE,
)
from .lifecycle_io import (
    AuthorityStoreStatus,
    INVALID as _INVALID,
    ROLE_AUTHORITY_HOST,
    ROLE_WORKER,
    ROLES as _ROLES,
    SCHEMA,
    ensure_root as _ensure_root,
    fail as _fail,
    fsync_dir as _fsync_dir,
    parse_registry as _parse_registry,
    read_file as _read_file,
    replace_json as _replace_json,
    validate_signer as _validate_signer,
    write_exact as _write_exact,
)


_STATE_FILE = ".authority-store-state.json"
_LOCK_FILE = ".authority-store-lifecycle.lock"
_STAGE_DIR = ".authority-store-stage"
_SNAPSHOT_MANIFEST = "authority-store-snapshot.json"
_INCOMPLETE = "BAMF_C09_SOURCE_AUTHORITY_LIFECYCLE_INCOMPLETE"
_REBIND = "BAMF_C09_SOURCE_AUTHORITY_REBIND_REQUIRES_EXPLICIT_ROTATION"


class SignerMaterialProvider(Protocol):
    """Optional keychain/secret-manager seam; provider semantics grant no authority."""

    def read_signer_bytes(self) -> bytes: ...


class AuthorityStoreOperator:
    """Serialized ordinary-user lifecycle around the fixed #1031 store."""

    def __init__(self):
        self.euid, self.root = _ensure_root()

    def _locked(self):
        path = self.root / _LOCK_FILE
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        info = os.fstat(fd)
        if info.st_uid != self.euid or not stat.S_ISREG(info.st_mode):
            os.close(fd)
            _fail()
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    @staticmethod
    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    def _status_unlocked(self, *, allow_transaction: bool = False) -> AuthorityStoreStatus:
        if (self.root / _TRANSACTION_FILE).exists() and not allow_transaction:
            _fail(_INCOMPLETE)
        registry_path = self.root / _REGISTRY_FILE
        if not registry_path.exists():
            _fail()
        registry = _parse_registry(_read_file(registry_path, max_bytes=256 * 1024))
        signer_path = self.root / _SIGNER_FILE
        signer_present = signer_path.exists()
        if signer_present:
            _validate_signer(_read_file(signer_path, max_bytes=16 * 1024), registry)
        state_path = self.root / _STATE_FILE
        if state_path.exists():
            try:
                state = json.loads(_read_file(state_path, max_bytes=16 * 1024).decode())
            except (UnicodeDecodeError, json.JSONDecodeError):
                _fail()
            if (state.get("schema") != SCHEMA
                    or state.get("registry_sha256") != registry.digest
                    or state.get("role") not in _ROLES
                    or bool(state.get("signer_present")) != signer_present):
                _fail()
            role = state["role"]
            managed = True
        else:
            role = ROLE_AUTHORITY_HOST if signer_present else ROLE_WORKER
            managed = False
        return AuthorityStoreStatus(role, registry.digest, signer_present, managed)

    def verify(self) -> AuthorityStoreStatus:
        fd = self._locked()
        try:
            return self._status_unlocked()
        finally:
            self._unlock(fd)

    def install(
        self,
        registry_bytes: bytes,
        *,
        expected_registry_sha256: str,
        role: str,
        signer_bytes: bytes | None = None,
        signer_provider: SignerMaterialProvider | None = None,
    ) -> AuthorityStoreStatus:
        return self._install(
            registry_bytes,
            expected_registry_sha256=expected_registry_sha256,
            role=role,
            signer_bytes=signer_bytes,
            signer_provider=signer_provider,
            operation="install",
        )

    def _install(
        self,
        registry_bytes: bytes,
        *,
        expected_registry_sha256: str,
        role: str,
        signer_bytes: bytes | None = None,
        signer_provider: SignerMaterialProvider | None = None,
        operation: str,
        expected_current_registry_sha256: str | None = None,
    ) -> AuthorityStoreStatus:
        allow_rebind = operation in {"rotate", "migrate"}
        if operation not in {"install", "rotate", "migrate"}:
            _fail()
        if (role not in _ROLES or not isinstance(expected_registry_sha256, str)
                or len(expected_registry_sha256) != 64
                or signer_bytes is not None and signer_provider is not None):
            _fail()
        registry = _parse_registry(registry_bytes)
        if registry.digest != expected_registry_sha256:
            _fail()
        if signer_provider is not None:
            signer_bytes = signer_provider.read_signer_bytes()
        if role == ROLE_AUTHORITY_HOST:
            if not isinstance(signer_bytes, bytes):
                _fail()
            _validate_signer(signer_bytes, registry)
        elif signer_bytes is not None:
            _fail()

        fd = self._locked()
        try:
            transaction = self.root / _TRANSACTION_FILE
            if transaction.exists() or transaction.is_symlink():
                _fail(_INCOMPLETE)
            current_path = self.root / _REGISTRY_FILE
            if current_path.exists():
                current = self._status_unlocked()
                if (expected_current_registry_sha256 is not None
                        and current.registry_sha256 != expected_current_registry_sha256):
                    _fail(_REBIND)
                if current.registry_sha256 != registry.digest and not allow_rebind:
                    _fail(_REBIND)
                if role == ROLE_WORKER and current.signer_present:
                    _fail(_REBIND)
            elif expected_current_registry_sha256 is not None:
                _fail(_REBIND)

            stage = self.root / _STAGE_DIR
            if stage.exists() or stage.is_symlink():
                shutil.rmtree(stage)
            stage.mkdir(mode=0o700)
            _write_exact(stage / _REGISTRY_FILE, registry_bytes)
            if signer_bytes is not None:
                _write_exact(stage / _SIGNER_FILE, signer_bytes)
            _replace_json(transaction, {
                "schema": SCHEMA,
                "operation": operation,
                "role": role,
                "registry_sha256": registry.digest,
            })
            _fsync_dir(self.root)
            return self._publish_stage_unlocked()
        finally:
            self._unlock(fd)

    def _publish_stage_unlocked(self) -> AuthorityStoreStatus:
        transaction = self.root / _TRANSACTION_FILE
        stage = self.root / _STAGE_DIR
        if not transaction.exists() or not stage.is_dir() or stage.is_symlink():
            _fail(_INCOMPLETE)
        try:
            tx = json.loads(_read_file(transaction, max_bytes=16 * 1024).decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail(_INCOMPLETE)
        registry_bytes = _read_file(stage / _REGISTRY_FILE, max_bytes=256 * 1024)
        registry = _parse_registry(registry_bytes)
        role = tx.get("role")
        if (tx.get("schema") != SCHEMA or role not in _ROLES
                or tx.get("registry_sha256") != registry.digest):
            _fail(_INCOMPLETE)
        signer_stage = stage / _SIGNER_FILE
        signer_present = signer_stage.exists()
        if (role == ROLE_AUTHORITY_HOST) != signer_present:
            _fail(_INCOMPLETE)
        if signer_present:
            _validate_signer(_read_file(signer_stage, max_bytes=16 * 1024), registry)

        self._publish_file_unlocked(stage / _REGISTRY_FILE, self.root / _REGISTRY_FILE)
        if signer_present:
            self._publish_file_unlocked(signer_stage, self.root / _SIGNER_FILE)
        _replace_json(self.root / _STATE_FILE, {
            "schema": SCHEMA,
            "role": role,
            "registry_sha256": registry.digest,
            "signer_present": signer_present,
        })
        _fsync_dir(self.root)
        transaction.unlink()
        _fsync_dir(self.root)
        shutil.rmtree(stage)
        return self._status_unlocked()

    @staticmethod
    def _publish_file_unlocked(source: Path, destination: Path) -> None:
        """Publish from a durable stage without consuming recovery source bytes."""
        payload = _read_file(source, max_bytes=(
            256 * 1024 if source.name == _REGISTRY_FILE else 16 * 1024
        ))
        temp = destination.with_name(destination.name + ".publish")
        if temp.exists() or temp.is_symlink():
            temp.unlink()
        _write_exact(temp, payload)
        os.replace(temp, destination)

    def recover(self) -> AuthorityStoreStatus:
        fd = self._locked()
        try:
            if not (self.root / _TRANSACTION_FILE).exists():
                return self._status_unlocked()
            return self._publish_stage_unlocked()
        finally:
            self._unlock(fd)

    def backup(self, destination: Path) -> AuthorityStoreStatus:
        destination = Path(destination)
        fd = self._locked()
        try:
            status = self._status_unlocked()
            if destination.exists() or destination.is_symlink():
                _fail()
            destination.mkdir(mode=0o700, parents=True)
            for filename in (_REGISTRY_FILE, _SIGNER_FILE):
                source = self.root / filename
                if source.exists():
                    _write_exact(destination / filename, source.read_bytes())
            _replace_json(destination / _SNAPSHOT_MANIFEST, status.to_record())
            _fsync_dir(destination)
            return status
        finally:
            self._unlock(fd)

    def restore(self, snapshot: Path, *, expected_registry_sha256: str) -> AuthorityStoreStatus:
        snapshot = Path(snapshot)
        try:
            manifest = json.loads(_read_file(
                snapshot / _SNAPSHOT_MANIFEST, max_bytes=16 * 1024).decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail()
        if (manifest.get("schema") != SCHEMA
                or manifest.get("registry_sha256") != expected_registry_sha256
                or manifest.get("role") not in _ROLES):
            _fail()
        signer_path = snapshot / _SIGNER_FILE
        return self._install(
            _read_file(snapshot / _REGISTRY_FILE, max_bytes=256 * 1024),
            expected_registry_sha256=expected_registry_sha256,
            role=manifest["role"],
            signer_bytes=(
                _read_file(signer_path, max_bytes=16 * 1024)
                if signer_path.exists() else None
            ),
            operation="install",
        )

    def rotate(
        self,
        registry_bytes: bytes,
        *,
        expected_current_registry_sha256: str,
        expected_registry_sha256: str,
        signer_bytes: bytes,
    ) -> AuthorityStoreStatus:
        return self._install(
            registry_bytes,
            expected_registry_sha256=expected_registry_sha256,
            role=ROLE_AUTHORITY_HOST,
            signer_bytes=signer_bytes,
            operation="rotate",
            expected_current_registry_sha256=expected_current_registry_sha256,
        )

    def migrate(
        self,
        registry_bytes: bytes,
        *,
        expected_current_registry_sha256: str,
        expected_registry_sha256: str,
        signer_bytes: bytes,
    ) -> AuthorityStoreStatus:
        """Explicit authority migration; semantically identical to fenced rotation."""
        return self._install(
            registry_bytes,
            expected_registry_sha256=expected_registry_sha256,
            role=ROLE_AUTHORITY_HOST,
            signer_bytes=signer_bytes,
            operation="migrate",
            expected_current_registry_sha256=expected_current_registry_sha256,
        )


__all__ = (
    "AuthorityStoreOperator",
    "AuthorityStoreStatus",
    "ROLE_AUTHORITY_HOST",
    "ROLE_WORKER",
    "SCHEMA",
    "SignerMaterialProvider",
)
