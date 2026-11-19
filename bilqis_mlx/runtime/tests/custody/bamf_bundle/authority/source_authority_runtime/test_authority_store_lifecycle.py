"""BAMF-0.3 operator lifecycle for the fixed ordinary-user authority store."""
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
    SourceAuthorityKey,
    SourceAuthorityRegistry,
    SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin
from bilqis_mlx.runtime.bamf_bundle._darwin_source_authority import lifecycle
from bilqis_mlx.runtime.bamf_bundle._darwin_source_authority import lifecycle_io
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind


def _material(seed: str, owner: str):
    private = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed * 32))
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    registry = SourceAuthorityRegistry((SourceAuthorityKey(
        owner,
        public,
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


class _Provider:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls = 0

    def read_signer_bytes(self) -> bytes:
        self.calls += 1
        return self.payload


class AuthorityStoreLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.home = Path(self.temporary.name) / "account"
        self.home.mkdir(mode=0o700)
        self.euid = os.geteuid()
        self.registry, self.registry_bytes, self.signer_bytes = _material(
            "29", "fixture:authority-host")
        self.next_registry, self.next_registry_bytes, self.next_signer_bytes = _material(
            "31", "fixture:rotated-authority-host")
        self.lifecycle_home = patch.object(
            lifecycle_io, "_effective_account_home", return_value=(self.euid, str(self.home)))
        self.runtime_home = patch.object(
            darwin, "_effective_account_home", return_value=(self.euid, str(self.home)))
        self.lifecycle_home.start()
        self.runtime_home.start()

    def tearDown(self):
        self.runtime_home.stop()
        self.lifecycle_home.stop()
        self.temporary.cleanup()

    @property
    def root(self) -> Path:
        return self.home / ".entif-ai" / "bilqis"

    def test_worker_install_is_digest_pinned_and_never_installs_signer(self):
        operator = lifecycle.AuthorityStoreOperator()
        with self.assertRaises(BilqisError):
            operator.install(
                self.registry_bytes,
                expected_registry_sha256="0" * 64,
                role=lifecycle.ROLE_WORKER,
            )
        status = operator.install(
            self.registry_bytes,
            expected_registry_sha256=self.registry.digest,
            role=lifecycle.ROLE_WORKER,
        )
        self.assertEqual(status.registry_sha256, self.registry.digest)
        self.assertFalse(status.signer_present)
        self.assertFalse((self.root / "source-authority-signer.json").exists())
        with self.assertRaises(BilqisError):
            operator.install(
                self.registry_bytes,
                expected_registry_sha256=self.registry.digest,
                role=lifecycle.ROLE_WORKER,
                signer_bytes=self.signer_bytes,
            )
        with self.assertRaises(TypeError):
            operator.install(  # type: ignore[call-arg]
                self.next_registry_bytes,
                expected_registry_sha256=self.next_registry.digest,
                role=lifecycle.ROLE_AUTHORITY_HOST,
                signer_bytes=self.next_signer_bytes,
                allow_rebind=True,
            )

    def test_authority_host_accepts_optional_secret_provider_without_exposing_secret(self):
        provider = _Provider(self.signer_bytes)
        operator = lifecycle.AuthorityStoreOperator()
        status = operator.install(
            self.registry_bytes,
            expected_registry_sha256=self.registry.digest,
            role=lifecycle.ROLE_AUTHORITY_HOST,
            signer_provider=provider,
        )
        self.assertEqual(provider.calls, 1)
        self.assertTrue(status.signer_present)
        self.assertNotIn("private", json.dumps(status.to_record()).lower())
        self.assertNotIn("29" * 32, json.dumps(status.to_record()))

    def test_transaction_marker_makes_partial_publication_fail_closed_then_recover(self):
        operator = lifecycle.AuthorityStoreOperator()
        stage = self.root / lifecycle._STAGE_DIR
        stage.mkdir(mode=0o700)
        lifecycle_io.write_exact(stage / "source-authority-registry.json", self.registry_bytes)
        lifecycle_io.write_exact(stage / "source-authority-signer.json", self.signer_bytes)
        lifecycle_io.replace_json(self.root / darwin._TRANSACTION_FILE, {
            "schema": lifecycle.SCHEMA,
            "operation": "install",
            "role": lifecycle.ROLE_AUTHORITY_HOST,
            "registry_sha256": self.registry.digest,
        })

        with self.assertRaises(BilqisError) as caught:
            darwin.open_host_source_authority_registry_fd(max_bytes=256 * 1024)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID",
        )
        status = operator.recover()
        self.assertEqual(status.registry_sha256, self.registry.digest)
        self.assertTrue(status.signer_present)
        self.assertFalse((self.root / darwin._TRANSACTION_FILE).exists())

    def test_recovery_converges_after_registry_was_already_published(self):
        operator = lifecycle.AuthorityStoreOperator()
        stage = self.root / lifecycle._STAGE_DIR
        stage.mkdir(mode=0o700)
        lifecycle_io.write_exact(stage / "source-authority-registry.json", self.registry_bytes)
        lifecycle_io.write_exact(stage / "source-authority-signer.json", self.signer_bytes)
        lifecycle_io.replace_json(self.root / darwin._TRANSACTION_FILE, {
            "schema": lifecycle.SCHEMA,
            "operation": "install",
            "role": lifecycle.ROLE_AUTHORITY_HOST,
            "registry_sha256": self.registry.digest,
        })
        operator._publish_file_unlocked(
            stage / "source-authority-registry.json",
            self.root / "source-authority-registry.json",
        )
        self.assertTrue((stage / "source-authority-registry.json").exists())
        with self.assertRaises(BilqisError):
            darwin.open_host_source_authority_registry_fd(max_bytes=256 * 1024)

        recovered = operator.recover()
        self.assertEqual(recovered.registry_sha256, self.registry.digest)
        self.assertTrue(recovered.signer_present)
        self.assertFalse((self.root / darwin._TRANSACTION_FILE).exists())

    def test_backup_restore_is_exact_and_restore_will_not_rebind(self):
        operator = lifecycle.AuthorityStoreOperator()
        installed = operator.install(
            self.registry_bytes,
            expected_registry_sha256=self.registry.digest,
            role=lifecycle.ROLE_AUTHORITY_HOST,
            signer_bytes=self.signer_bytes,
        )
        snapshot = Path(self.temporary.name) / "snapshot"
        backed_up = operator.backup(snapshot)
        self.assertEqual(backed_up, installed)

        restored_home = Path(self.temporary.name) / "restored"
        restored_home.mkdir(mode=0o700)
        with patch.object(
                lifecycle_io, "_effective_account_home",
                return_value=(self.euid, str(restored_home))):
            restored = lifecycle.AuthorityStoreOperator().restore(
                snapshot, expected_registry_sha256=self.registry.digest)
        self.assertEqual(restored.registry_sha256, self.registry.digest)
        self.assertTrue(restored.signer_present)

        operator.rotate(
            self.next_registry_bytes,
            expected_current_registry_sha256=self.registry.digest,
            expected_registry_sha256=self.next_registry.digest,
            signer_bytes=self.next_signer_bytes,
        )
        with self.assertRaises(BilqisError) as caught:
            operator.restore(snapshot, expected_registry_sha256=self.registry.digest)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_REBIND_REQUIRES_EXPLICIT_ROTATION",
        )

    def test_rotation_is_explicit_and_current_digest_fenced(self):
        operator = lifecycle.AuthorityStoreOperator()
        operator.install(
            self.registry_bytes,
            expected_registry_sha256=self.registry.digest,
            role=lifecycle.ROLE_AUTHORITY_HOST,
            signer_bytes=self.signer_bytes,
        )
        with self.assertRaises(BilqisError):
            operator.rotate(
                self.next_registry_bytes,
                expected_current_registry_sha256="0" * 64,
                expected_registry_sha256=self.next_registry.digest,
                signer_bytes=self.next_signer_bytes,
            )
        rotated = operator.rotate(
            self.next_registry_bytes,
            expected_current_registry_sha256=self.registry.digest,
            expected_registry_sha256=self.next_registry.digest,
            signer_bytes=self.next_signer_bytes,
        )
        self.assertEqual(rotated.registry_sha256, self.next_registry.digest)

    def test_migration_is_an_explicit_fenced_operation(self):
        operator = lifecycle.AuthorityStoreOperator()
        operator.install(
            self.registry_bytes,
            expected_registry_sha256=self.registry.digest,
            role=lifecycle.ROLE_AUTHORITY_HOST,
            signer_bytes=self.signer_bytes,
        )
        migrated = operator.migrate(
            self.next_registry_bytes,
            expected_current_registry_sha256=self.registry.digest,
            expected_registry_sha256=self.next_registry.digest,
            signer_bytes=self.next_signer_bytes,
        )
        self.assertEqual(migrated.registry_sha256, self.next_registry.digest)

    def test_legacy_store_remains_valid_without_lifecycle_state(self):
        operator = lifecycle.AuthorityStoreOperator()
        lifecycle_io.write_exact(self.root / "source-authority-registry.json", self.registry_bytes)
        lifecycle_io.write_exact(self.root / "source-authority-signer.json", self.signer_bytes)
        status = operator.verify()
        self.assertFalse(status.lifecycle_managed)
        self.assertEqual(status.registry_sha256, self.registry.digest)

    def test_symlinked_authority_directory_is_rejected(self):
        entif = self.home / ".entif-ai"
        entif.mkdir(mode=0o700)
        target = Path(self.temporary.name) / "attacker"
        target.mkdir(mode=0o700)
        (entif / "bilqis").symlink_to(target, target_is_directory=True)
        with self.assertRaises(BilqisError):
            lifecycle.AuthorityStoreOperator()


if __name__ == "__main__":
    unittest.main()
