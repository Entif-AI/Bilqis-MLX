"""B13.1 tensor payload reuse through data-plane content-addressed custody."""
from __future__ import annotations

import os
import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.bamf_bundle.publication as publication
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
import bilqis_mlx._data_plane.file_objects as file_objects
from bilqis_mlx.data_plane import close_data_planes, data_plane
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_bundle, load_bamf_generation, publish_bamf_generation, save_bamf_bundle,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    publish_candidate,
    accepted_state, candidate, parent_state, shape_patch,
)


class BamfTensorCasTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()
        close_data_planes()

    def tearDown(self):
        close_data_planes()
        self.environment.stop()
        self.temporary.cleanup()

    def save(self, source, name):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return save_bamf_bundle(source, self.root / name)

    def test_identical_payloads_share_one_content_addressed_file(self):
        source = candidate(parent_state())
        first = self.save(source, "first")
        second = self.save(source, "second")
        digest = first["tensors"]["sha256"]
        self.assertEqual(second["tensors"]["sha256"], digest)
        canonical = data_plane().require_file_object(digest)
        self.assertEqual(first["tensors"]["object_sha256"], digest)
        self.assertEqual(second["tensors"]["object_sha256"], digest)
        self.assertFalse((self.root / "first" / first["tensors"]["filename"]).exists())
        self.assertFalse((self.root / "second" / second["tensors"]["filename"]).exists())
        self.assertTrue(canonical.is_file())

    def test_changed_payload_gets_distinct_object_and_old_bundle_stays_valid(self):
        parent = parent_state()
        first = self.save(candidate(parent), "first")
        second = self.save(candidate(accepted_state(parent)), "second")
        first_digest = first["tensors"]["sha256"]
        second_digest = second["tensors"]["sha256"]
        self.assertNotEqual(first_digest, second_digest)
        self.assertNotEqual(
            data_plane().require_file_object(first_digest),
            data_plane().require_file_object(second_digest))
        with shape_patch():
            self.assertEqual(load_bamf_bundle(self.root / "first").generation, 0)

    def test_valid_local_alias_cannot_hide_corrupt_content_addressed_owner(self):
        manifest = self.save(candidate(parent_state()), "bundle")
        digest = manifest["tensors"]["sha256"]
        canonical = data_plane().require_file_object(digest)
        canonical.write_bytes(canonical.read_bytes() + b"corrupt")
        with shape_patch(), self.assertRaises(BilqisError):
            load_bamf_bundle(self.root / "bundle")

    def test_pointer_crash_retry_reuses_existing_tensor_object(self):
        run = self.root / "run"
        source = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(publication, "_atomic_pointer", side_effect=RuntimeError("crash")):
            with self.assertRaisesRegex(RuntimeError, "crash"):
                publish_candidate(run, source)
        objects = tuple((self.root / "plane.sqlite3.objects").glob("*/*"))
        self.assertEqual(len(objects), 1)
        inode = objects[0].stat().st_ino
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer = publish_candidate(run, source)
        objects_after = tuple((self.root / "plane.sqlite3.objects").glob("*/*"))
        self.assertEqual(len(objects_after), 1)
        self.assertEqual(objects_after[0].stat().st_ino, inode)
        self.assertFalse((run / pointer["bundle"] / "bamf-state.safetensors").exists())

    def test_new_cas_directories_are_durable_before_object_publication(self):
        synced = []
        original = file_objects._fsync_directory

        def record(path):
            synced.append(Path(path))
            original(path)

        with patch.object(file_objects, "_fsync_directory", side_effect=record):
            manifest = self.save(candidate(parent_state()), "bundle")

        digest = manifest["tensors"]["sha256"]
        root = (self.root / "plane.sqlite3.objects").resolve()
        shard = root / digest[:2]
        self.assertIn(root.parent, synced)
        self.assertIn(root, synced)
        self.assertIn(shard, synced)
        self.assertLess(synced.index(root.parent), synced.index(shard))
        self.assertTrue(data_plane().require_file_object(digest).is_file())

    def test_existing_unowned_object_requires_copy_headroom(self):
        import bilqis_mlx.runtime.bamf_bundle.codec as codec
        source = candidate(parent_state())
        manifest = self.save(source, "owned")
        digest = manifest["tensors"]["sha256"]
        plane = data_plane()
        target = plane.require_file_object(digest)
        plane._db.execute("DELETE FROM meta WHERE key=?", (file_objects._OWNER_KEY_PREFIX + digest,))
        inode = target.stat().st_ino
        with patch.object(codec, "assert_headroom", side_effect=RuntimeError("reserve")) as reserve:
            with self.assertRaisesRegex(RuntimeError, "reserve"):
                self.save(source, "unowned")
        self.assertEqual(reserve.call_args.kwargs["reserve_gib"], 100.0)
        self.assertEqual(reserve.call_args.kwargs["required_bytes"], target.stat().st_size)
        self.assertEqual(target.stat().st_ino, inode)

    def test_generic_publication_cannot_advance_vocabulary_extension(self):
        run = self.root / "run"
        state = parent_state()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            first = publish_candidate(run, candidate(state))
            initial = load_bamf_generation(run / "bamf-state.json")
            state = initial.retained_state
            swap = candidate(state, 1, first["manifest_sha256"])
            extents = replace(swap.extents, active_semantic_digest="8" * 64)
            semantic = {**swap.semantic_abi, "active_set_sha256": "8" * 64}
            swap = replace(swap, extents=extents, semantic_abi=semantic,
                           transition={**swap.transition, "kind": "PARAMETER_EXTENSION"})
            with self.assertRaises(BilqisError) as failure:
                publish_candidate(run, swap)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED")
        self.assertEqual(json.loads((run / "bamf-state.json").read_text())["generation"], 0)


if __name__ == "__main__":
    unittest.main()
