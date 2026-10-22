import os
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.data_plane import (
    close_data_planes, data_plane, dedupe_bundle_payloads,
    referenced_custody_files, verify_file_digest,
)


class DataPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.previous = os.environ.get("BILQIS_DATA_PLANE")
        os.environ["BILQIS_DATA_PLANE"] = str(self.root / "plane.sqlite3")
        close_data_planes()

    def tearDown(self):
        close_data_planes()
        if self.previous is None:
            os.environ.pop("BILQIS_DATA_PLANE", None)
        else:
            os.environ["BILQIS_DATA_PLANE"] = self.previous
        self.temp.cleanup()

    def test_verified_file_cache_is_shared_and_invalidates_on_file_change(self):
        import hashlib
        target = self.root / "artifact.bin"
        target.write_bytes(b"abc" * 1000)
        expected = hashlib.sha256(target.read_bytes()).hexdigest()
        self.assertTrue(verify_file_digest(target, expected))
        self.assertTrue(verify_file_digest(target, expected))
        self.assertEqual(data_plane().stats()["verified_files"], 1)
        target.write_bytes(b"abd" * 1000)
        self.assertFalse(verify_file_digest(target, expected))

    def test_objects_deduplicate_by_content_hash(self):
        import hashlib
        raw = b'{"x":1}'
        digest = hashlib.sha256(raw).hexdigest()
        plane = data_plane()
        plane.put_object(digest, raw)
        plane.put_object(digest, raw)
        self.assertEqual(plane.get_object(digest), raw)
        self.assertEqual(plane.stats()["objects"], 1)

    def test_custody_file_discovery_is_bounded_to_bundle_and_soup_payloads(self):
        receipt = {
            "school": {"current_student": {
                "filename": "bundles/working-1", "sha256": "a" * 64}},
            "mentor_epoch": {"active_grade_soups": {"C": {
                "filename": "soups/C-abc.safetensors", "sha256": "b" * 64}}},
            "unrelated": {"filename": "cohorts/x.json", "sha256": "c" * 64},
        }
        found = referenced_custody_files(self.root, receipt)
        self.assertEqual(found, (
            ((self.root / "bundles/working-1/model-and-own-adamw.safetensors").resolve(),
             "a" * 64),
            ((self.root / "soups/C-abc.safetensors").resolve(), "b" * 64),
        ))

    def test_bundle_deduper_preserves_alias_paths_and_shares_identical_payload(self):
        import hashlib
        import json
        bundles = self.root / "bundles"
        payload = b"same-model-and-adamw" * 100
        digest = hashlib.sha256(payload).hexdigest()
        paths = []
        for name in ("best-one", "best-two"):
            folder = bundles / name
            folder.mkdir(parents=True)
            blob = folder / "model-and-own-adamw.safetensors"
            blob.write_bytes(payload)
            (folder / "manifest.json").write_text(json.dumps({
                "safetensors_sha256": digest, "optimizer_step": 17,
            }))
            paths.append(blob)

        result = dedupe_bundle_payloads(self.root)

        self.assertEqual(result["linked_aliases"], 1)
        self.assertEqual(result["reclaimed_bytes"], len(payload))
        self.assertEqual(paths[0].read_bytes(), payload)
        self.assertEqual(paths[1].read_bytes(), payload)
        self.assertEqual(paths[0].stat().st_ino, paths[1].stat().st_ino)
        self.assertEqual(dedupe_bundle_payloads(self.root)["linked_aliases"], 0)


if __name__ == "__main__":
    unittest.main()
