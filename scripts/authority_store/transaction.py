"""Crash-convergent publication transaction for the operator authority store."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin
from scripts.authority_store.io import (
    AuthorityStoreStatus,
    ROLE_AUTHORITY_HOST,
    ROLE_WORKER,
    ROLES,
    SCHEMA,
    fail,
    fsync_dir,
    parse_registry,
    read_file,
    replace_json,
    validate_signer,
    write_exact,
)


STAGE_DIR = ".authority-store-stage"
INCOMPLETE = "BAMF_C09_SOURCE_AUTHORITY_LIFECYCLE_INCOMPLETE"
REBIND = "BAMF_C09_SOURCE_AUTHORITY_REBIND_REQUIRES_EXPLICIT_ROTATION"


class AuthorityStoreTransactionMixin:
    """Internal transaction mechanics; public authority selection lives elsewhere."""

    @staticmethod
    def _validate_request(
        *, operation: str, role: str, expected_registry_sha256: str,
        expected_current_registry_sha256: str | None,
        expected_signer_owner_id: str | None,
        expected_signer_public_key_hex: str | None,
        signer_bytes: bytes | None, signer_provider,
    ) -> bool:
        allow_rebind = operation in {"rotate", "migrate"}
        if operation not in {"install", "restore", "rotate", "migrate"}:
            fail()
        if (allow_rebind and not isinstance(expected_current_registry_sha256, str)
                or not allow_rebind and expected_current_registry_sha256 is not None):
            fail()
        if (role not in ROLES or not isinstance(expected_registry_sha256, str)
                or len(expected_registry_sha256) != 64
                or signer_bytes is not None and signer_provider is not None):
            fail()
        signer_pinned = (
            isinstance(expected_signer_owner_id, str)
            and bool(expected_signer_owner_id)
            and isinstance(expected_signer_public_key_hex, str)
            and len(expected_signer_public_key_hex) == 64
        )
        if (role == ROLE_AUTHORITY_HOST) != signer_pinned:
            fail()
        if (role == ROLE_WORKER
                and (expected_signer_owner_id is not None
                     or expected_signer_public_key_hex is not None)):
            fail()
        return allow_rebind

    @staticmethod
    def _resolve_signer(
        *, role: str, signer_bytes: bytes | None, signer_provider,
        registry, expected_signer_owner_id: str | None,
        expected_signer_public_key_hex: str | None,
    ) -> bytes | None:
        if role == ROLE_WORKER:
            if signer_bytes is not None or signer_provider is not None:
                fail()
            return None
        if signer_provider is not None:
            signer_bytes = signer_provider.read_signer_bytes()
        if not isinstance(signer_bytes, bytes):
            fail()
        validate_signer(
            signer_bytes, registry,
            expected_owner_id=expected_signer_owner_id,
            expected_public_key_hex=expected_signer_public_key_hex,
        )
        return signer_bytes

    def _require_store_fence_unlocked(
        self, *, registry, role: str, allow_rebind: bool,
        expected_current_registry_sha256: str | None,
    ) -> None:
        transaction = self.root / darwin._TRANSACTION_FILE
        if transaction.exists() or transaction.is_symlink():
            fail(INCOMPLETE)
        current_path = self.root / darwin._REGISTRY_FILE
        current_present = current_path.exists() or current_path.is_symlink()
        residual_authority = any(
            path.exists() or path.is_symlink()
            for path in (
                self.root / darwin._LIFECYCLE_STATE_FILE,
                self.root / darwin._SIGNER_FILE,
            )
        )
        if not current_present:
            if residual_authority:
                fail(INCOMPLETE)
            if expected_current_registry_sha256 is not None:
                fail(REBIND)
            return
        current = self._status_unlocked()
        if (expected_current_registry_sha256 is not None
                and current.registry_sha256 != expected_current_registry_sha256):
            fail(REBIND)
        if current.registry_sha256 != registry.digest and not allow_rebind:
            fail(REBIND)
        if role == ROLE_WORKER and current.signer_present:
            fail(REBIND)

    def _stage_transaction_unlocked(
        self, *, registry_bytes: bytes, signer_bytes: bytes | None,
        registry, operation: str, role: str,
        expected_signer_owner_id: str | None,
        expected_signer_public_key_hex: str | None,
    ) -> None:
        stage = self.root / STAGE_DIR
        if stage.exists() or stage.is_symlink():
            shutil.rmtree(stage)
        stage.mkdir(mode=0o700)
        write_exact(stage / darwin._REGISTRY_FILE, registry_bytes)
        if signer_bytes is not None:
            write_exact(stage / darwin._SIGNER_FILE, signer_bytes)
        fsync_dir(stage)
        replace_json(self.root / darwin._TRANSACTION_FILE, {
            "schema": SCHEMA,
            "operation": operation,
            "role": role,
            "registry_sha256": registry.digest,
            "signer_owner_id": expected_signer_owner_id,
            "signer_public_key_hex": expected_signer_public_key_hex,
        })
        fsync_dir(self.root)

    def _install(
        self,
        registry_bytes: bytes,
        *,
        expected_registry_sha256: str,
        role: str,
        signer_bytes: bytes | None = None,
        signer_provider=None,
        operation: str,
        expected_current_registry_sha256: str | None = None,
        expected_signer_owner_id: str | None = None,
        expected_signer_public_key_hex: str | None = None,
    ) -> AuthorityStoreStatus:
        allow_rebind = self._validate_request(
            operation=operation, role=role,
            expected_registry_sha256=expected_registry_sha256,
            expected_current_registry_sha256=expected_current_registry_sha256,
            expected_signer_owner_id=expected_signer_owner_id,
            expected_signer_public_key_hex=expected_signer_public_key_hex,
            signer_bytes=signer_bytes, signer_provider=signer_provider,
        )
        registry = parse_registry(registry_bytes)
        if registry.digest != expected_registry_sha256:
            fail()
        signer_bytes = self._resolve_signer(
            role=role, signer_bytes=signer_bytes, signer_provider=signer_provider,
            registry=registry,
            expected_signer_owner_id=expected_signer_owner_id,
            expected_signer_public_key_hex=expected_signer_public_key_hex,
        )

        fd = self._locked()
        try:
            self._require_store_fence_unlocked(
                registry=registry, role=role, allow_rebind=allow_rebind,
                expected_current_registry_sha256=expected_current_registry_sha256,
            )
            self._stage_transaction_unlocked(
                registry_bytes=registry_bytes, signer_bytes=signer_bytes,
                registry=registry, operation=operation, role=role,
                expected_signer_owner_id=expected_signer_owner_id,
                expected_signer_public_key_hex=expected_signer_public_key_hex,
            )
            return self._publish_stage_unlocked()
        finally:
            self._unlock(fd)

    def _publish_stage_unlocked(self) -> AuthorityStoreStatus:
        transaction = self.root / darwin._TRANSACTION_FILE
        stage = self.root / STAGE_DIR
        if not transaction.exists() or not stage.is_dir() or stage.is_symlink():
            fail(INCOMPLETE)
        try:
            tx = json.loads(read_file(
                transaction, max_bytes=16 * 1024, expected_uid=self.euid,
                require_private=True).decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            fail(INCOMPLETE)
        registry_bytes = read_file(
            stage / darwin._REGISTRY_FILE,
            max_bytes=256 * 1024,
            expected_uid=self.euid,
            require_private=True,
        )
        registry = parse_registry(registry_bytes)
        if set(tx) != {
                "schema", "operation", "role", "registry_sha256",
                "signer_owner_id", "signer_public_key_hex",
        }:
            fail(INCOMPLETE)
        role = tx.get("role")
        signer_owner_id = tx.get("signer_owner_id")
        signer_public_key_hex = tx.get("signer_public_key_hex")
        if (tx.get("schema") != SCHEMA
                or tx.get("operation") not in {"install", "restore", "rotate", "migrate"}
                or role not in ROLES
                or tx.get("registry_sha256") != registry.digest
                or (role == ROLE_AUTHORITY_HOST)
                    != (isinstance(signer_owner_id, str)
                        and bool(signer_owner_id)
                        and isinstance(signer_public_key_hex, str)
                        and len(signer_public_key_hex) == 64)
                or (role == ROLE_WORKER
                    and (signer_owner_id is not None
                         or signer_public_key_hex is not None))):
            fail(INCOMPLETE)
        signer_stage = stage / darwin._SIGNER_FILE
        signer_present = signer_stage.exists()
        if (role == ROLE_AUTHORITY_HOST) != signer_present:
            fail(INCOMPLETE)
        if signer_present:
            validate_signer(read_file(
                signer_stage, max_bytes=16 * 1024,
                expected_uid=self.euid, require_private=True), registry,
                expected_owner_id=signer_owner_id,
                expected_public_key_hex=signer_public_key_hex)

        self._publish_file_unlocked(
            stage / darwin._REGISTRY_FILE, self.root / darwin._REGISTRY_FILE)
        if signer_present:
            self._publish_file_unlocked(
                signer_stage, self.root / darwin._SIGNER_FILE)
        replace_json(self.root / darwin._LIFECYCLE_STATE_FILE, {
            "schema": SCHEMA,
            "role": role,
            "registry_sha256": registry.digest,
            "signer_present": signer_present,
            "signer_owner_id": signer_owner_id,
            "signer_public_key_hex": signer_public_key_hex,
        })
        fsync_dir(self.root)
        transaction.unlink()
        fsync_dir(self.root)
        shutil.rmtree(stage)
        return self._status_unlocked()

    @staticmethod
    def _publish_file_unlocked(source: Path, destination: Path) -> None:
        payload = read_file(
            source,
            max_bytes=(
                256 * 1024 if source.name == darwin._REGISTRY_FILE else 16 * 1024),
            expected_uid=os.geteuid(),
            require_private=True,
        )
        temp = destination.with_name(destination.name + ".publish")
        if temp.exists() or temp.is_symlink():
            temp.unlink()
        write_exact(temp, payload)
        os.replace(temp, destination)

    def recover(self) -> AuthorityStoreStatus:
        fd = self._locked()
        try:
            if not (self.root / darwin._TRANSACTION_FILE).exists():
                return self._status_unlocked()
            return self._publish_stage_unlocked()
        finally:
            self._unlock(fd)


__all__ = ("AuthorityStoreTransactionMixin", "INCOMPLETE", "REBIND", "STAGE_DIR")
