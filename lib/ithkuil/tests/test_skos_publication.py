import fcntl
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.publication import (
    ArtifactBundle, make_bundle, publish_bundle, verify_publication,
)
import lib.ithkuil.src.skos.publication as publication


def fixture(version="one"):
    return make_bundle({"canonical.nt": f'<urn:s> <urn:p> "{version}" .\n'.encode(),
                        "held.json": b'{"entries":[]}\n', "digest.json": b'{}\n',
                        "input.json": b'{}\n'}, {"status": "complete", "profile_version": "fixture/1"})


class ArtifactPublicationTests(unittest.TestCase):
    def code(self, expected, function, *args, **kwargs):
        with self.assertRaises(ProfileError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, expected)

    def test_publication_verifies_all_payloads_and_repeat_is_idempotent(self):
        bundle = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "output"
            receipt = publish_bundle(bundle, root)
            self.assertEqual(receipt["bundle_id"], hashlib.sha256(bundle.manifest).hexdigest())
            generation = root / "generations" / bundle.bundle_id
            self.assertEqual({p.name for p in generation.iterdir()},
                             {"canonical.nt", "held.json", "digest.json", "input.json", "manifest.json"})
            for name, expected in bundle.files:
                self.assertEqual((generation / name).read_bytes(), expected)
            before = (root / "CURRENT.json").stat().st_mtime_ns
            self.assertEqual(publish_bundle(bundle, root), receipt)
            self.assertEqual((root / "CURRENT.json").stat().st_mtime_ns, before)
            self.assertEqual(verify_publication(root), receipt)
            self.assertEqual(len(list((root / "generations").iterdir())), 1)

    def test_new_generation_preserves_previous_immutable_artifacts(self):
        first, second = fixture(), fixture("two")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            publish_bundle(first, root)
            publish_bundle(second, root)
            self.assertEqual(verify_publication(root)["bundle_id"], second.bundle_id)
            self.assertEqual((root / "generations" / first.bundle_id / "canonical.nt").read_bytes(),
                             b'<urn:s> <urn:p> "one" .\n')
            self.assertEqual(len(list((root / "generations").iterdir())), 2)

    def test_invalid_payload_bundle_rejected_before_output_creation(self):
        bundle = fixture()
        bad = ArtifactBundle(bundle.manifest, tuple((name, b"wrong") for name, _ in bundle.files))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "output"
            self.code("COMPILER_ARTIFACT_DIGEST_MISMATCH", publish_bundle, bad, root)
            self.assertFalse(root.exists())
            duplicate = ArtifactBundle(bundle.manifest, bundle.files + (bundle.files[0],))
            self.code("INVALID_COMPILER_ARTIFACT_SET", publish_bundle, duplicate, root)
            self.assertFalse(root.exists())

    def test_v1_bundle_requires_exactly_the_four_public_artifacts(self):
        bundle = fixture()
        files = {**dict(bundle.files), "extra.bin": b"unexpected"}
        self.code("INVALID_COMPILER_ARTIFACT_SET", make_bundle, files,
                  {"status": "complete", "profile_version": "fixture/1"})

    def test_invalid_manifests_and_missing_files_fail_with_stable_codes(self):
        original = fixture()
        for value, code in (([], "COMPILER_MANIFEST_MISMATCH"),
                            ({"schema": "unknown"}, "COMPILER_MANIFEST_MISMATCH"),
                            ({**original.metadata(), "files": {}}, "INVALID_COMPILER_ARTIFACT_SET"),
                            ({**original.metadata(), "files": {**original.metadata()["files"], "input.json": []}},
                             "INVALID_COMPILER_ARTIFACT_RECEIPT")):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                bundle = ArtifactBundle(json.dumps(value).encode(), original.files)
                self.code(code, publish_bundle, bundle, Path(temporary) / "output")
        self.code("INVALID_COMPILER_ARTIFACT_SET", make_bundle, {"canonical.nt": b""}, {})
        self.code("INVALID_COMPILER_ARTIFACT_SET", make_bundle,
                  {**dict(original.files), "../escape": b""}, {})

    def test_tampered_generation_does_not_get_rewritten_or_selected_again(self):
        bundle = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            publish_bundle(bundle, root)
            path = root / "generations" / bundle.bundle_id / "canonical.nt"
            path.write_bytes(b"tampered")
            self.code("COMPILER_ARTIFACT_DIGEST_MISMATCH", verify_publication, root)
            self.code("COMPILER_ARTIFACT_DIGEST_MISMATCH", publish_bundle, fixture("new"), root)
            self.assertEqual(path.read_bytes(), b"tampered")

    def test_invalid_pointer_does_not_get_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CURRENT.json").write_text("[]")
            self.code("INVALID_COMPILER_POINTER", verify_publication, root)
            self.code("INVALID_COMPILER_POINTER", publish_bundle, fixture(), root)
            self.assertEqual((root / "CURRENT.json").read_text(), "[]")

    def test_current_pointer_requires_exact_generated_v1_bytes(self):
        bundle = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); publish_bundle(bundle, root)
            pointer = json.loads((root / "CURRENT.json").read_bytes())
            variants = (
                json.dumps(pointer, sort_keys=True).encode("utf-8"),
                publication.json_bytes({**pointer, "extra": "tampered"}),
            )
            for payload in variants:
                with self.subTest(payload=payload):
                    (root / "CURRENT.json").write_bytes(payload)
                    self.code("INVALID_COMPILER_POINTER", verify_publication, root)
                    self.code("INVALID_COMPILER_POINTER", publish_bundle, bundle, root)
                    self.assertEqual((root / "CURRENT.json").read_bytes(), payload)
                    (root / "CURRENT.json").write_bytes(publication.json_bytes(pointer))

    def test_mid_generation_failure_preserves_prior_selection_and_cleans_only_staging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = fixture(); publish_bundle(first, root)
            original = publication._write_synced
            def fail(path, payload):
                if path.name == "held.json":
                    raise OSError("synthetic interrupted write")
                return original(path, payload)
            with patch.object(publication, "_write_synced", side_effect=fail):
                with self.assertRaises(OSError):
                    publish_bundle(fixture("two"), root)
            self.assertEqual(verify_publication(root)["bundle_id"], first.bundle_id)
            self.assertEqual({p.name for p in (root / "generations").iterdir()}, {first.bundle_id})

    def test_failure_before_pointer_swap_leaves_reusable_unselected_generation(self):
        first, second = fixture(), fixture("two")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); publish_bundle(first, root)
            original = publication.os.replace
            def fail(source, target):
                if Path(target).name == "CURRENT.json":
                    raise OSError("synthetic pointer interruption")
                return original(source, target)
            with patch.object(publication.os, "replace", side_effect=fail):
                with self.assertRaises(OSError):
                    publish_bundle(second, root)
            self.assertEqual(verify_publication(root)["bundle_id"], first.bundle_id)
            self.assertTrue((root / "generations" / second.bundle_id).is_dir())
            self.assertEqual(list(root.glob(".current-*")), [])
            self.assertEqual(publish_bundle(second, root)["bundle_id"], second.bundle_id)

    def test_competing_writer_receives_busy_without_touching_pointer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (root / ".publish.lock").open("a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.code("COMPILER_OUTPUT_BUSY", publish_bundle, fixture(), root)
                self.assertFalse((root / "CURRENT.json").exists())
            self.assertEqual(publish_bundle(fixture(), root)["bundle_id"], fixture().bundle_id)

    def test_generation_symlink_is_not_a_publication_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "output"; root.mkdir()
            outside = Path(temporary) / "outside"; outside.mkdir()
            (root / "generations").symlink_to(outside, target_is_directory=True)
            self.code("COMPILER_OUTPUT_SYMLINK_FORBIDDEN", publish_bundle, fixture(), root)
            self.assertEqual(list(outside.iterdir()), [])

    def test_output_root_and_standalone_current_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            outside = base / "outside"; outside.mkdir()
            root = base / "output"; root.symlink_to(outside, target_is_directory=True)
            self.code("COMPILER_OUTPUT_SYMLINK_FORBIDDEN", publish_bundle, fixture(), root)
            self.assertEqual(list(outside.iterdir()), [])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = fixture(); publish_bundle(bundle, root)
            real_pointer = root / "CURRENT.real"
            (root / "CURRENT.json").replace(real_pointer)
            (root / "CURRENT.json").symlink_to(real_pointer.name)
            self.code("COMPILER_OUTPUT_SYMLINK_FORBIDDEN", verify_publication, root)

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            real = base / "real"; bundle = fixture(); publish_bundle(bundle, real)
            root = base / "output"; root.mkdir()
            (root / "generations").symlink_to(real / "generations", target_is_directory=True)
            (root / "CURRENT.json").write_bytes((real / "CURRENT.json").read_bytes())
            self.code("COMPILER_OUTPUT_SYMLINK_FORBIDDEN", verify_publication, root)

    def test_postcommit_directory_sync_failure_returns_verified_warning(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = fixture(), fixture("two")
            publish_bundle(first, root)
            original = publication._sync_directory
            calls = {"root": 0}

            def fail_after_pointer_commit(directory):
                if Path(directory) == root:
                    calls["root"] += 1
                    if calls["root"] == 2:
                        raise OSError("synthetic post-commit directory fsync failure")
                return original(directory)

            with patch.object(publication, "_sync_directory", side_effect=fail_after_pointer_commit):
                receipt = publish_bundle(second, root)
            self.assertEqual(receipt["bundle_id"], second.bundle_id)
            self.assertEqual(receipt["durability_warning"]["code"], "DIRSYNC_UNCONFIRMED")
            self.assertEqual(verify_publication(root)["bundle_id"], second.bundle_id)

    def test_postcommit_readback_failure_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = fixture(), fixture("two")
            publish_bundle(first, root)
            original = publication.verify_publication
            calls = {"count": 0}

            def fail_only_after_commit(output_root):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise ProfileError("SYNTHETIC_POSTCOMMIT_READBACK_FAILURE")
                return original(output_root)

            with patch.object(publication, "verify_publication", side_effect=fail_only_after_commit):
                with self.assertRaises(ProfileError) as caught:
                    publish_bundle(second, root)
            self.assertEqual(caught.exception.code,
                             "COMPILER_PUBLICATION_COMMITTED_READBACK_REQUIRED")
            self.assertIn(second.bundle_id, caught.exception.details)
            self.assertEqual(original(root)["bundle_id"], second.bundle_id)

    def test_postcommit_readback_of_another_valid_generation_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = fixture(), fixture("two")
            publish_bundle(first, root)
            first_pointer = (root / "CURRENT.json").read_bytes()
            original_verify = publication.verify_publication
            original_sync = publication._sync_directory
            verify_calls = {"count": 0}
            sync_calls = {"root": 0}

            def swap_to_first_before_postcommit_readback(output_root):
                verify_calls["count"] += 1
                if verify_calls["count"] == 2:
                    (root / "CURRENT.json").write_bytes(first_pointer)
                return original_verify(output_root)

            def fail_postcommit_dirsync(directory):
                if Path(directory) == root:
                    sync_calls["root"] += 1
                    if sync_calls["root"] == 2:
                        raise OSError("synthetic post-commit directory fsync failure")
                return original_sync(directory)

            with patch.object(publication, "verify_publication",
                              side_effect=swap_to_first_before_postcommit_readback), \
                    patch.object(publication, "_sync_directory", side_effect=fail_postcommit_dirsync):
                with self.assertRaises(ProfileError) as caught:
                    publish_bundle(second, root)
            self.assertEqual(caught.exception.code,
                             "COMPILER_PUBLICATION_COMMITTED_READBACK_REQUIRED")
            self.assertIn(second.bundle_id, caught.exception.details)
            self.assertEqual(original_verify(root)["bundle_id"], first.bundle_id)


if __name__ == "__main__":
    unittest.main()
