"""Crash convergence, backup/restore, rotation, and migration proofs."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin
from scripts.authority_store import io as lifecycle_io
from scripts.authority_store import lifecycle
from scripts.authority_store import transaction
from tests.authority_store.support import AuthorityStoreTestCase


class AuthorityStoreTests(AuthorityStoreTestCase):
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
            "signer_owner_id": self.registry.keys[0].owner_id,
            "signer_public_key_hex": self.registry.keys[0].public_key_hex,
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
            "signer_owner_id": self.registry.keys[0].owner_id,
            "signer_public_key_hex": self.registry.keys[0].public_key_hex,
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

    def test_real_install_interruptions_fail_closed_and_recover(self):
        publish_original = transaction.AuthorityStoreTransactionMixin._publish_file_unlocked
        replace_original = transaction.replace_json

        failpoints = ("before_registry", "after_registry", "after_state")
        for failpoint in failpoints:
            with self.subTest(failpoint=failpoint):
                if self.root.exists():
                    shutil.rmtree(self.root)
                self.approve(
                    "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
                operator = lifecycle.AuthorityStoreOperator()

                publish_calls = 0
                replace_calls = 0

                def publish(source, destination):
                    nonlocal publish_calls
                    publish_calls += 1
                    if failpoint == "before_registry" and publish_calls == 1:
                        raise OSError("injected publication interruption")
                    publish_original(source, destination)
                    if failpoint == "after_registry" and publish_calls == 1:
                        raise OSError("injected publication interruption")

                def replace(path, record):
                    nonlocal replace_calls
                    replace_calls += 1
                    replace_original(path, record)
                    if failpoint == "after_state" and replace_calls == 2:
                        raise OSError("injected publication interruption")

                with patch.object(
                        transaction.AuthorityStoreTransactionMixin,
                        "_publish_file_unlocked", side_effect=publish), \
                        patch.object(transaction, "replace_json", side_effect=replace), \
                        self.assertRaises(OSError):
                    operator.install(self.registry_bytes, signer_bytes=self.signer_bytes)

                self.assert_runtime_fails_closed()
                recovered = lifecycle.AuthorityStoreOperator().recover()
                self.assertEqual(recovered.registry_sha256, self.registry.digest)
                self.assertTrue(recovered.signer_present)
                self.assertFalse((self.root / darwin._TRANSACTION_FILE).exists())

    def test_process_death_after_registry_or_signer_publish_recovers_fresh(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        input_root = Path(self.temporary.name) / "inputs"
        input_root.mkdir()
        registry_path = input_root / "registry.json"
        signer_path = input_root / "signer.json"
        registry_path.write_bytes(self.registry_bytes)
        signer_path.write_bytes(self.signer_bytes)
        repository = Path(__file__).resolve().parents[2]
        child = r'''
import os
import sys
from pathlib import Path
from bilqis_mlx.runtime.bamf_bundle import _darwin_source_authority as darwin
from scripts.authority_store import lifecycle, transaction

home = Path(sys.argv[1])
registry = Path(sys.argv[2])
signer = Path(sys.argv[3])
die_after = int(sys.argv[4])
darwin._effective_account_home = lambda: (os.geteuid(), str(home))
original = transaction.AuthorityStoreTransactionMixin._publish_file_unlocked
calls = 0

def publish(source, destination):
    global calls
    calls += 1
    original(source, destination)
    if calls == die_after:
        os._exit(91)

transaction.AuthorityStoreTransactionMixin._publish_file_unlocked = staticmethod(publish)
lifecycle.AuthorityStoreOperator().install(
    registry.read_bytes(), signer_bytes=signer.read_bytes())
raise SystemExit(92)
'''
        for die_after, label in ((1, "registry"), (2, "signer")):
            with self.subTest(after=label):
                if self.root.exists():
                    shutil.rmtree(self.root)
                completed = subprocess.run(
                    [
                        sys.executable, "-c", child, str(self.home),
                        str(registry_path), str(signer_path), str(die_after),
                    ],
                    cwd=repository,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 91, completed.stderr)
                marker = json.loads(
                    (self.root / darwin._TRANSACTION_FILE).read_text())
                self.assertEqual(marker["operation"], "install")
                self.assertEqual(
                    marker["signer_owner_id"], self.registry.keys[0].owner_id)
                self.assert_runtime_fails_closed()
                recovered = lifecycle.AuthorityStoreOperator().recover()
                self.assertEqual(recovered.registry_sha256, self.registry.digest)
                self.assertEqual(
                    recovered.signer_owner_id, self.registry.keys[0].owner_id)
                self.assertFalse((self.root / darwin._TRANSACTION_FILE).exists())

    def test_real_rotate_interruption_cannot_expose_new_registry_with_old_signer(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        operator.install(self.registry_bytes, signer_bytes=self.signer_bytes)
        self.approve(
            "rotate", lifecycle.ROLE_AUTHORITY_HOST, self.next_registry.digest,
            self.registry.digest)

        original = transaction.AuthorityStoreTransactionMixin._publish_file_unlocked
        calls = 0

        def publish(source, destination):
            nonlocal calls
            calls += 1
            original(source, destination)
            if calls == 1:
                raise OSError("injected rotate interruption")

        with patch.object(
                transaction.AuthorityStoreTransactionMixin,
                "_publish_file_unlocked", side_effect=publish), \
                self.assertRaises(OSError):
            operator.rotate(
                self.next_registry_bytes, signer_bytes=self.next_signer_bytes)

        self.assert_runtime_fails_closed()
        recovered = lifecycle.AuthorityStoreOperator().recover()
        self.assertEqual(recovered.registry_sha256, self.next_registry.digest)
        self.assertTrue(recovered.signer_present)

    def test_backup_restore_is_exact_and_restore_will_not_rebind(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        installed = operator.install(
            self.registry_bytes,
            signer_bytes=self.signer_bytes,
        )
        backed_up = operator.backup()
        self.assertEqual(backed_up, installed)
        backup = (
            self.home / ".entif-ai" / lifecycle_io.BACKUP_DIR / self.registry.digest
        )
        self.assertTrue((backup / "source-authority-signer.json").is_file())
        self.assertFalse(backup.is_relative_to(Path.cwd()))
        self.assertEqual(
            (backup / darwin._REGISTRY_FILE).read_bytes(), self.registry_bytes)
        self.assertEqual(
            (backup / darwin._SIGNER_FILE).read_bytes(), self.signer_bytes)

        shutil.rmtree(self.root)
        self.approve(
            "restore", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        restored = lifecycle.AuthorityStoreOperator().restore()
        self.assertEqual(restored.registry_sha256, self.registry.digest)
        self.assertTrue(restored.signer_present)

        self.approve(
            "rotate", lifecycle.ROLE_AUTHORITY_HOST, self.next_registry.digest,
            self.registry.digest)
        operator.rotate(
            self.next_registry_bytes,
            signer_bytes=self.next_signer_bytes,
        )
        self.approve(
            "restore", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        with self.assertRaises(BilqisError) as caught:
            operator.restore()
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_REBIND_REQUIRES_EXPLICIT_ROTATION",
        )

    def test_rotation_is_explicit_and_current_digest_fenced(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        operator.install(
            self.registry_bytes,
            signer_bytes=self.signer_bytes,
        )
        self.approve(
            "rotate", lifecycle.ROLE_AUTHORITY_HOST, self.next_registry.digest,
            "0" * 64)
        with self.assertRaises(BilqisError):
            operator.rotate(
                self.next_registry_bytes,
                signer_bytes=self.next_signer_bytes,
            )
        self.approve(
            "rotate", lifecycle.ROLE_AUTHORITY_HOST, self.next_registry.digest,
            self.registry.digest)
        rotated = operator.rotate(
            self.next_registry_bytes,
            signer_bytes=self.next_signer_bytes,
        )
        self.assertEqual(rotated.registry_sha256, self.next_registry.digest)

    def test_migration_is_an_explicit_fenced_operation(self):
        self.approve(
            "install", lifecycle.ROLE_AUTHORITY_HOST, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        operator.install(
            self.registry_bytes,
            signer_bytes=self.signer_bytes,
        )
        self.approve(
            "migrate", lifecycle.ROLE_AUTHORITY_HOST, self.next_registry.digest,
            self.registry.digest)
        migrated = operator.migrate(
            self.next_registry_bytes,
            signer_bytes=self.next_signer_bytes,
        )
        self.assertEqual(migrated.registry_sha256, self.next_registry.digest)

    def test_stage_directory_is_fsynced_before_transaction_marker(self):
        self.approve("install", lifecycle.ROLE_WORKER, self.registry.digest)
        operator = lifecycle.AuthorityStoreOperator()
        events = []
        fsync_original = transaction.fsync_dir
        replace_original = transaction.replace_json

        def fsync(path):
            events.append(("fsync", Path(path).name))
            return fsync_original(path)

        def replace(path, record):
            events.append(("replace", Path(path).name))
            return replace_original(path, record)

        with patch.object(transaction, "fsync_dir", side_effect=fsync), \
                patch.object(transaction, "replace_json", side_effect=replace):
            operator.install(self.registry_bytes)

        stage_fsync = events.index(("fsync", transaction.STAGE_DIR))
        marker_replace = events.index(("replace", darwin._TRANSACTION_FILE))
        self.assertLess(stage_fsync, marker_replace)
