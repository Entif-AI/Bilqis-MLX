"""Disposable backup fixtures; no real historical runs are copied or deleted."""
from pathlib import Path
import errno
import json
import tempfile
import unittest
from unittest.mock import patch
from bilqis_mlx import backup


class BackupTests(unittest.TestCase):
    def setup_tree(self, root):
        source=root/"selected-old-bilqis"
        target=root/"fake-external-volume"
        source.mkdir()
        target.mkdir()
        (source/".git").write_text("gitdir: /unavailable/object-root\n")
        (source/"model").mkdir()
        (source/"empty").mkdir()
        (source/"model"/"trained.pt").write_bytes(b"model plus optimizer bytes")
        (source/"train.py").write_text("# version-pinned legacy code\n")
        (source/"linked").symlink_to("train.py")
        return source,target

    def test_plan_then_copy_verify_and_source_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,dst=self.setup_tree(Path(tmp))
            original=(src/"model"/"trained.pt").read_bytes()
            p=backup.plan([src],dst)
            self.assertEqual(p["status"],"PLAN_ONLY_NO_FILES_COPIED")
            self.assertEqual(p["source_trees"][0]["file_count"],3)
            self.assertTrue(p["source_trees"][0]["git_object_warning"])
            self.assertFalse((dst/"bilqis-mlx-archive").exists())
            r=backup.copy([src],dst,confirm_copy=True,max_gib=.05,
                          require_external=False,minimum_destination_free_gib=0)
            self.assertEqual(r["status"],"COPY_VERIFIED_NO_SOURCE_DELETION")
            self.assertFalse(r["sources_deleted"])
            report=backup.verify(Path(r["archives"][0]["manifest"]))
            self.assertEqual(report["verified_entries"],6)
            self.assertEqual((src/"model"/"trained.pt").read_bytes(),original)
            self.assertTrue((src/"linked").is_symlink())
            again=backup.copy([src],dst,confirm_copy=True,max_gib=.05,
                              require_external=False,minimum_destination_free_gib=0)
            self.assertEqual(again["archives"][0]["verified_entries"],6)

    def test_backup_detects_tampered_external_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,dst=self.setup_tree(Path(tmp))
            r=backup.copy([src],dst,confirm_copy=True,max_gib=.05,
                          require_external=False,minimum_destination_free_gib=0)
            manifest=Path(r["archives"][0]["manifest"])
            (manifest.parent/"tree"/"model"/"trained.pt").write_bytes(b"oops")
            with self.assertRaisesRegex(ValueError,"WRONG_SIZE|HASH_MISMATCH"):
                backup.verify(manifest)
            self.assertTrue((src/"model"/"trained.pt").exists())

    def test_no_copy_without_confirmation_budget_or_external_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,dst=self.setup_tree(Path(tmp))
            with self.assertRaisesRegex(ValueError,"CONFIRMATION"):
                backup.copy([src],dst,confirm_copy=False,max_gib=1,
                            require_external=False)
            with self.assertRaisesRegex(ValueError,"GIB_CAP"):
                backup.copy([src],dst,confirm_copy=True,max_gib=0,
                            require_external=False)
            with self.assertRaisesRegex(ValueError,"EXTERNAL_VOLUME"):
                backup.copy([src],dst,confirm_copy=True,max_gib=1,
                            minimum_destination_free_gib=0)
            self.assertFalse((dst/"bilqis-mlx-archive").exists())

    def test_refuses_to_sweep_code_root_or_copy_into_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,dst=self.setup_tree(Path(tmp))
            with self.assertRaisesRegex(ValueError,"OVERLAP"):
                backup.plan([src],src)
            with self.assertRaisesRegex(ValueError,"BROAD"):
                backup.safe_source(Path.home()/"Code")
            with self.assertRaisesRegex(ValueError,"DUPLICATE"):
                backup.plan([src,src],dst)

    def test_usb_without_symlinks_keeps_link_in_verified_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,dst=self.setup_tree(Path(tmp))
            with patch.object(Path,"symlink_to",
                    side_effect=OSError(errno.EOPNOTSUPP,"No symlinks on device")):
                outcome=backup.copy([src],dst,confirm_copy=True,max_gib=.05,
                                    require_external=False,minimum_destination_free_gib=0)
            manifest=Path(outcome["archives"][0]["manifest"])
            record=next(e for e in json.loads(manifest.read_text())["entries"]
                        if e["path"]=="linked")
            self.assertEqual(record["link_storage"],"manifest_only")
            self.assertEqual(record["link_target"],"train.py")
            self.assertEqual(backup.verify(manifest)["status"],
                             "EVERY_MANIFEST_ENTRY_VERIFIED")
            self.assertTrue((src/"linked").is_symlink())
            self.assertFalse((manifest.parent/"tree"/"linked").exists())


if __name__=="__main__":
    unittest.main()
