"""Operator-owned lifecycle for the fixed ordinary-user C09 authority store.

This module hardens the *custody* of the #1031 fixed path.  It never chooses
semantic authority, generates trust roots, or lets a caller redirect production
runtime reads.  Every install is pinned to an already-approved registry digest.
"""
from __future__ import annotations

import fcntl
import json
import os
import shutil
import stat
from typing import Protocol

from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin
from scripts.authority_store.io import (
    APPROVAL_INVALID as _APPROVAL_INVALID,
    AuthorityStoreStatus,
    INVALID as _INVALID,
    ROLE_AUTHORITY_HOST,
    ROLE_WORKER,
    ROLES as _ROLES,
    SCHEMA,
    ensure_root as _ensure_root,
    fail as _fail,
    fixed_backup_path as _fixed_backup_path,
    fsync_dir as _fsync_dir,
    parse_registry as _parse_registry,
    read_file as _read_file,
    read_fixed_approval as _read_fixed_approval,
    replace_json as _replace_json,
    require_private_directory as _require_private_directory,
    validate_signer as _validate_signer,
    write_exact as _write_exact,
)
from scripts.authority_store.transaction import (
    AuthorityStoreTransactionMixin,
    INCOMPLETE as _INCOMPLETE,
    REBIND as _REBIND,
    STAGE_DIR as _STAGE_DIR,
)


_REGISTRY_FILE = darwin._REGISTRY_FILE
_SIGNER_FILE = darwin._SIGNER_FILE
_TRANSACTION_FILE = darwin._TRANSACTION_FILE
_STATE_FILE = darwin._LIFECYCLE_STATE_FILE
_SNAPSHOT_MANIFEST = "authority-store-snapshot.json"


class SignerMaterialProvider(Protocol):
    """Optional keychain/secret-manager seam; provider semantics grant no authority."""

    def read_signer_bytes(self) -> bytes: ...


class AuthorityStoreOperator(AuthorityStoreTransactionMixin):
    """Serialized ordinary-user lifecycle around the fixed #1031 store."""

    def __init__(self):
        self.euid, self.root = _ensure_root()

    def _locked(self):
        path = self.root / darwin._LIFECYCLE_LOCK_FILE
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        info = os.fstat(fd)
        if (info.st_uid != self.euid or not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o077):
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
        state_path = self.root / _STATE_FILE
        managed = state_path.exists()
        registry_path = self.root / _REGISTRY_FILE
        if not registry_path.exists():
            _fail()
        registry = _parse_registry(_read_file(
            registry_path,
            max_bytes=256 * 1024,
            expected_uid=self.euid,
            require_private=managed,
        ))
        signer_path = self.root / _SIGNER_FILE
        signer_present = signer_path.exists()
        if signer_present:
            _validate_signer(_read_file(
                signer_path,
                max_bytes=16 * 1024,
                expected_uid=self.euid,
                require_private=managed,
            ), registry)
        if managed:
            try:
                state = json.loads(_read_file(
                    state_path,
                    max_bytes=16 * 1024,
                    expected_uid=self.euid,
                    require_private=True,
                ).decode())
            except (UnicodeDecodeError, json.JSONDecodeError):
                _fail()
            if (state.get("schema") != SCHEMA
                    or state.get("registry_sha256") != registry.digest
                    or state.get("role") not in _ROLES
                    or bool(state.get("signer_present")) != signer_present
                    or (state.get("role") == ROLE_AUTHORITY_HOST) != signer_present):
                _fail()
            role = state["role"]
        else:
            role = ROLE_AUTHORITY_HOST if signer_present else ROLE_WORKER
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
        signer_bytes: bytes | None = None,
        signer_provider: SignerMaterialProvider | None = None,
    ) -> AuthorityStoreStatus:
        approval = self._approval("install")
        return self._install(
            registry_bytes,
            expected_registry_sha256=approval.registry_sha256,
            role=approval.role,
            signer_bytes=signer_bytes,
            signer_provider=signer_provider,
            operation="restore",
        )

    @staticmethod
    def _approval(operation: str):
        approval = _read_fixed_approval()
        if approval.operation != operation:
            _fail(_APPROVAL_INVALID)
        return approval

    def backup(self) -> AuthorityStoreStatus:
        fd = self._locked()
        try:
            status = self._status_unlocked()
            destination = _fixed_backup_path(status.registry_sha256)
            if destination.exists() or destination.is_symlink():
                _fail()
            stage = destination.with_name(destination.name + ".stage")
            if stage.exists() or stage.is_symlink():
                shutil.rmtree(stage)
            stage.mkdir(mode=0o700)
            for filename in (_REGISTRY_FILE, _SIGNER_FILE):
                source = self.root / filename
                if source.exists():
                    _write_exact(stage / filename, _read_file(
                        source,
                        max_bytes=(256 * 1024 if filename == _REGISTRY_FILE else 16 * 1024),
                        expected_uid=self.euid,
                        require_private=status.lifecycle_managed,
                    ))
            _replace_json(stage / _SNAPSHOT_MANIFEST, status.to_record())
            _fsync_dir(stage)
            os.replace(stage, destination)
            _fsync_dir(destination.parent)
            return status
        finally:
            self._unlock(fd)

    def restore(self) -> AuthorityStoreStatus:
        approval = self._approval("restore")
        snapshot = _fixed_backup_path(approval.registry_sha256)
        _require_private_directory(snapshot, expected_uid=self.euid)
        try:
            manifest = json.loads(_read_file(
                snapshot / _SNAPSHOT_MANIFEST,
                max_bytes=16 * 1024,
                require_private=True,
            ).decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail()
        if (manifest.get("schema") != SCHEMA
                or manifest.get("registry_sha256") != approval.registry_sha256
                or manifest.get("role") != approval.role):
            _fail()
        signer_path = snapshot / _SIGNER_FILE
        return self._install(
            _read_file(
                snapshot / _REGISTRY_FILE,
                max_bytes=256 * 1024,
                require_private=True,
            ),
            expected_registry_sha256=approval.registry_sha256,
            role=approval.role,
            signer_bytes=(
                _read_file(signer_path, max_bytes=16 * 1024, require_private=True)
                if signer_path.exists() else None
            ),
            operation="install",
        )

    def rotate(self, registry_bytes: bytes, *, signer_bytes: bytes) -> AuthorityStoreStatus:
        approval = self._approval("rotate")
        return self._install(
            registry_bytes,
            expected_registry_sha256=approval.registry_sha256,
            role=approval.role,
            signer_bytes=signer_bytes,
            operation="rotate",
            expected_current_registry_sha256=approval.current_registry_sha256,
        )

    def migrate(self, registry_bytes: bytes, *, signer_bytes: bytes) -> AuthorityStoreStatus:
        """Explicit authority migration; semantically identical to fenced rotation."""
        approval = self._approval("migrate")
        return self._install(
            registry_bytes,
            expected_registry_sha256=approval.registry_sha256,
            role=approval.role,
            signer_bytes=signer_bytes,
            operation="migrate",
            expected_current_registry_sha256=approval.current_registry_sha256,
        )


__all__ = (
    "AuthorityStoreOperator",
    "AuthorityStoreStatus",
    "ROLE_AUTHORITY_HOST",
    "ROLE_WORKER",
    "SCHEMA",
    "SignerMaterialProvider",
)
