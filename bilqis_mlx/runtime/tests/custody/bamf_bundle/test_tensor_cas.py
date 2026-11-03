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
from bilqis_mlx.data_plane import close_data_planes, data_plane
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_bundle, load_bamf_generation, publish_bamf_generation, save_bamf_bundle,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
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
                publish_bamf_generation(run, source)
        objects = tuple((self.root / "plane.sqlite3.objects").glob("*/*"))
        self.assertEqual(len(objects), 1)
        inode = objects[0].stat().st_ino
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer = publish_bamf_generation(run, source)
        objects_after = tuple((self.root / "plane.sqlite3.objects").glob("*/*"))
        self.assertEqual(len(objects_after), 1)
        self.assertEqual(objects_after[0].stat().st_ino, inode)
        self.assertFalse((run / pointer["bundle"] / "bamf-state.safetensors").exists())

    def test_published_generations_reuse_then_separate_payloads(self):
        run = self.root / "run"
        state = parent_state()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            first = publish_bamf_generation(run, candidate(state))
            first_root = run / first["bundle"]
            before = {p.name: p.read_bytes() for p in first_root.iterdir()}
            first_manifest = json.loads(before["manifest.json"])
            digest = first_manifest["tensors"]["object_sha256"]
            original = data_plane().require_file_object(digest)
            original_inode = original.stat().st_ino
            swap = candidate(state, 1, first["manifest_sha256"])
            extents = replace(swap.extents, active_semantic_digest="8" * 64)
            semantic = {**swap.semantic_abi, "active_set_sha256": "8" * 64}
            swap = replace(swap, extents=extents, semantic_abi=semantic,
                           transition={**swap.transition, "kind": "PARAMETER_EXTENSION"})
            second = publish_bamf_generation(run, swap)
            second_manifest = json.loads((run / second["bundle"] / "manifest.json").read_bytes())
            self.assertEqual(second_manifest["tensors"]["object_sha256"], digest)
            self.assertEqual(original.stat().st_ino, original_inode)
            changed = replace(candidate(accepted_state(state), 2, second["manifest_sha256"]),
                              extents=extents, semantic_abi=semantic)
            third = publish_bamf_generation(run, changed)
            third_manifest = json.loads((run / third["bundle"] / "manifest.json").read_bytes())
            self.assertNotEqual(third_manifest["tensors"]["object_sha256"], digest)
            self.assertEqual(load_bamf_generation(run / "bamf-state.json").generation, 2)
            self.assertEqual(load_bamf_bundle(first_root).generation, 0)
            self.assertEqual(load_bamf_bundle(run / second["bundle"]).generation, 1)
            expected_events = [dict(load_bamf_bundle(run / pointer["bundle"]).outbox[0])
                               for pointer in (first, second, third)]
        self.assertEqual({p.name: p.read_bytes() for p in first_root.iterdir()}, before)
        self.assertEqual(len(tuple(original.parent.parent.glob("*/*.safetensors"))), 2)
        events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
        self.assertEqual(events, expected_events)


if __name__ == "__main__":
    unittest.main()
