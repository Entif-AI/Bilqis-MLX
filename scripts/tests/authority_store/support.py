"""Shared fixtures for BAMF authority-store operator tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from scripts.authority_store import io as lifecycle_io


def material(seed: str, owner: str):
    private = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed * 32))
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    registry = SourceAuthorityRegistry((SourceAuthorityKey(
        owner, public,
        (SourceAuthorityScope(DependencyKind.ARTIFACT, "bamf:"),),
    ),))
    registry_bytes = (
        json.dumps(registry.to_record(), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    signer_bytes = (
        json.dumps({
            "schema": "bilqis.mlx.source-authority-signer/v1",
            "owner_id": owner,
            "private_key_hex": seed * 32,
        }, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    return registry, registry_bytes, signer_bytes


class Provider:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls = 0

    def read_signer_bytes(self) -> bytes:
        self.calls += 1
        return self.payload


class AuthorityStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.home = Path(self.temporary.name) / "account"
        self.home.mkdir(mode=0o700)
        self.euid = os.geteuid()
        self.registry, self.registry_bytes, self.signer_bytes = material(
            "29", "fixture:authority-host")
        self.next_registry, self.next_registry_bytes, self.next_signer_bytes = material(
            "31", "fixture:rotated-authority-host")
        self.runtime_home = patch.object(
            darwin, "_effective_account_home", return_value=(self.euid, str(self.home)))
        self.runtime_home.start()

    def tearDown(self):
        self.runtime_home.stop()
        self.temporary.cleanup()

    @property
    def root(self) -> Path:
        return self.home / ".entif-ai" / "bilqis"

    def approve(
        self, operation: str, role: str, registry_sha256: str,
        current_registry_sha256: str | None = None,
    ) -> None:
        approval_path = self.home / ".entif-ai" / lifecycle_io.APPROVAL_FILE
        approval_path.parent.mkdir(mode=0o700, exist_ok=True)
        if approval_path.exists():
            approval_path.unlink()
        lifecycle_io.write_exact(approval_path, (
            json.dumps({
                "schema": lifecycle_io.APPROVAL_SCHEMA,
                "operation": operation,
                "role": role,
                "registry_sha256": registry_sha256,
                "current_registry_sha256": current_registry_sha256,
            }, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode())

    def assert_runtime_fails_closed(self) -> None:
        with self.assertRaises(BilqisError):
            darwin.open_host_source_authority_registry_fd(max_bytes=256 * 1024)
