import os
from unittest.mock import patch
from .base import DataPlaneCase
from bilqis_mlx.data_plane import data_plane, verify_file_digest

class DataPlaneStoreTests(DataPlaneCase):
    def test_public_symbols_keep_historical_module_identity(self):
        import bilqis_mlx.data_plane as data_plane_module
        names = ("DataPlaneError", "default_path", "event_payload_digest",
                 "live_grade_soups", "referenced_custody_files",
                 "dedupe_bundle_payloads", "main")
        self.assertEqual(
            {name: getattr(data_plane_module, name).__module__ for name in names},
            {name: "bilqis_mlx.data_plane" for name in names},
        )

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

    def test_verified_file_cache_reuses_same_inode_across_hardlink_aliases(self):
        import hashlib
        first = self.root / "first.bin"
        second = self.root / "second.bin"
        first.write_bytes(b"shared immutable payload" * 1000)
        os.link(first, second)
        expected = hashlib.sha256(first.read_bytes()).hexdigest()
        self.assertTrue(verify_file_digest(first, expected))

        with patch("bilqis_mlx.data_plane._digest_file",
                   side_effect=AssertionError("duplicate inode rehash")):
            self.assertTrue(verify_file_digest(second, expected))

    def test_objects_deduplicate_by_content_hash(self):
        import hashlib
        raw = b'{"x":1}'
        digest = hashlib.sha256(raw).hexdigest()
        plane = data_plane()
        plane.put_object(digest, raw)
        plane.put_object(digest, raw)
        self.assertEqual(plane.get_object(digest), raw)
        self.assertEqual(plane.stats()["objects"], 1)
