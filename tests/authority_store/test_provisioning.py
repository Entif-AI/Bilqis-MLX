"""Authority selection, worker isolation, and compatibility proofs."""
from __future__ import annotations

import json
import os
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin
from scripts.authority_store import io as lifecycle_io
from scripts.authority_store import lifecycle
from scripts.authority_store import transaction
from tests.authority_store.support import (
    AuthorityStoreTestCase, Provider as _Provider, material as _material,
)


class AuthorityStoreTests(AuthorityStoreTestCase):
    def test_install_requires_fixed_external_approval(self):
        operator = lifecycle.AuthorityStoreOperator()
        with self.assertRaises(BilqisError) as caught:
            operator.install(self.registry_bytes)
        self.assertEqual(
            caught.exception.context["reason"],
            lifecycle_io.APPROVAL_REQUIRED,
        )

    def test_worker_install_uses_fixed_approval_and_never_installs_signer(self):
        self.approve(
            "install", lifecycle.ROLE_WORKER, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        with self.assertRaises(BilqisError):
            operator.install(self.next_registry_bytes)
        status = operator.install(self.registry_bytes)
        self.assertEqual(status.registry_sha256, self.registry.digest)
        self.assertFalse(status.signer_present)
        self.assertEqual(set(status.to_record()), {
            "schema", "role", "registry_sha256", "signer_present",
            "lifecycle_managed", "signer_owner_id", "signer_public_key_hex",
        })
        self.assertIsNone(status.signer_owner_id)
        self.assertIsNone(status.signer_public_key_hex)
        self.assertFalse((self.root / "source-authority-signer.json").exists())
        with self.assertRaises(BilqisError):
            operator.install(
                self.registry_bytes,
                signer_bytes=self.signer_bytes,
            )
        with self.assertRaises(TypeError):
            operator.install(  # type: ignore[call-arg]
                self.next_registry_bytes,
                role=lifecycle.ROLE_AUTHORITY_HOST,
            )

    def test_authority_host_accepts_optional_secret_provider_without_exposing_secret(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        provider = _Provider(self.signer_bytes)
        operator = lifecycle.AuthorityStoreOperator()
        status = operator.install(
            self.registry_bytes,
            signer_provider=provider,
        )
        self.assertEqual(provider.calls, 1)
        self.assertTrue(status.signer_present)
        self.assertNotIn("private", json.dumps(status.to_record()).lower())
        self.assertNotIn("29" * 32, json.dumps(status.to_record()))

    def test_worker_approval_never_reads_secret_provider(self):
        self.approve("install", lifecycle.ROLE_WORKER, self.registry.digest)
        provider = _Provider(self.signer_bytes)
        operator = lifecycle.AuthorityStoreOperator()
        with self.assertRaises(BilqisError):
            operator.install(self.registry_bytes, signer_provider=provider)
        self.assertEqual(provider.calls, 0)

    def test_signer_must_match_exact_runtime_schema_and_registry_key(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        wrong_registry, _wrong_bytes, wrong_signer = _material(
            "41", "fixture:other-owner")
        del wrong_registry
        with self.assertRaises(BilqisError):
            operator.install(self.registry_bytes, signer_bytes=wrong_signer)
        malformed = json.loads(self.signer_bytes)
        malformed["extra"] = "not-runtime-valid"
        with self.assertRaises(BilqisError):
            operator.install(
                self.registry_bytes,
                signer_bytes=(json.dumps(malformed) + "\n").encode(),
            )

    def test_approval_pins_one_signer_principal_inside_multi_key_registry(self):
        first, _first_bytes, first_signer = _material("41", "fixture:principal-a")
        second, _second_bytes, second_signer = _material("43", "fixture:principal-b")
        registry = type(self.registry)(tuple(sorted(
            (*first.keys, *second.keys), key=lambda key: key.owner_id)))
        registry_bytes = (
            json.dumps(registry.to_record(), sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
        pinned = registry.keys[0]
        rejected_signer = second_signer if pinned.owner_id == first.keys[0].owner_id else first_signer
        accepted_signer = first_signer if pinned.owner_id == first.keys[0].owner_id else second_signer
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, registry.digest,
            signer_owner_id=pinned.owner_id,
            signer_public_key_hex=pinned.public_key_hex,
        )
        operator = lifecycle.AuthorityStoreOperator()
        with self.assertRaises(BilqisError) as caught:
            operator.install(registry_bytes, signer_bytes=rejected_signer)
        self.assertEqual(
            caught.exception.context["reason"], lifecycle_io.APPROVAL_INVALID)
        status = operator.install(registry_bytes, signer_bytes=accepted_signer)
        self.assertEqual(status.signer_owner_id, pinned.owner_id)
        self.assertEqual(status.signer_public_key_hex, pinned.public_key_hex)

    def test_residual_managed_state_cannot_be_treated_as_virgin_store(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        operator.install(self.registry_bytes, signer_bytes=self.signer_bytes)
        (self.root / darwin._REGISTRY_FILE).unlink()
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.next_registry.digest)
        with self.assertRaises(BilqisError) as caught:
            operator.install(
                self.next_registry_bytes, signer_bytes=self.next_signer_bytes)
        self.assertEqual(
            caught.exception.context["reason"],
            transaction.INCOMPLETE,
        )

    def test_managed_state_role_and_signer_presence_must_agree(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        operator.install(self.registry_bytes, signer_bytes=self.signer_bytes)
        state_path = self.root / darwin._LIFECYCLE_STATE_FILE
        state = json.loads(state_path.read_text())
        state["role"] = lifecycle.ROLE_WORKER
        state_path.unlink()
        lifecycle_io.replace_json(state_path, state)
        with self.assertRaises(BilqisError):
            operator.verify()

    def test_managed_store_private_mode_is_enforced_without_retroactive_legacy_migration(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        operator.install(self.registry_bytes, signer_bytes=self.signer_bytes)
        os.chmod(self.root / darwin._REGISTRY_FILE, 0o644)
        with self.assertRaises(BilqisError):
            operator.verify()
        with self.assertRaises(BilqisError):
            darwin.open_host_source_authority_registry_fd(max_bytes=256 * 1024)

    def test_runtime_surface_has_no_authority_store_provisioner(self):
        from bilqis_mlx.runtime.bamf_bundle import source_authority_custody

        self.assertFalse(hasattr(source_authority_custody, "AuthorityStoreOperator"))
        self.assertFalse(hasattr(source_authority_custody, "install_authority_store"))
        self.assertFalse(hasattr(darwin, "AuthorityStoreOperator"))

    def test_backup_has_no_caller_selected_destination(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        operator.install(self.registry_bytes, signer_bytes=self.signer_bytes)
        with self.assertRaises(TypeError):
            operator.backup(Path.cwd())  # type: ignore[call-arg]
        status = operator.backup()
        self.assertEqual(status.registry_sha256, self.registry.digest)
        fixed = self.home / ".entif-ai" / lifecycle_io.BACKUP_DIR / self.registry.digest
        self.assertTrue((fixed / darwin._SIGNER_FILE).is_file())

    def test_legacy_store_remains_valid_without_lifecycle_state(self):
        operator = lifecycle.AuthorityStoreOperator()
        lifecycle_io.write_exact(self.root / "source-authority-registry.json", self.registry_bytes)
        lifecycle_io.write_exact(self.root / "source-authority-signer.json", self.signer_bytes)
        os.chmod(self.root / "source-authority-registry.json", 0o644)
        os.chmod(self.root / "source-authority-signer.json", 0o644)
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
