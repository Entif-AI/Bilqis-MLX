"""Retirement preserves review evidence and refuses unsafe deletion."""
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts.bamf.detached.retire_replica import retire


class RetireDisposableReplicaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.replica = self.root / "profile"
        run = self.replica / "run"
        run.mkdir(parents=True)
        (self.replica / "plane.sqlite3").write_bytes(b"database")
        (run / "bamf-state.json").write_text("{}")
        (run / "events.jsonl").write_text('{"event":"done"}\n')
        (self.root / "result.json").write_text("{}")
        (self.root / "run.log").write_text("completed")
        self.receipt = self.root / "receipt.json"
        self.record = {
            "schema": "bilqis.bamf.detached-long-run/v2", "status": "PASS",
            "returncode": 0, "source_mutated": False, "finished_at": "finished",
            "workdir": str(self.root / "source-snapshot"),
            "source_workdir": str(self.root.parent / "source"),
            "pid": 999999, "log": str(self.root / "run.log"),
            "source_sha256": "a" * 64, "snapshot_sha256": "a" * 64,
        }
        self.write_receipt()
        self.idle = patch("scripts.bamf.detached.retire_replica.require_idle")
        self.idle.start()
        self.addCleanup(self.idle.stop)

    def write_receipt(self):
        self.receipt.write_text(json.dumps(self.record))

    def retire(self, replica="profile", apply=False):
        return retire(self.receipt, replica, ["result.json"], apply=apply)

    def test_dry_run_then_verified_retirement_is_idempotent(self):
        self.assertEqual(self.retire()["status"], "DRY_RUN")
        self.assertTrue(self.replica.exists())
        self.assertEqual(self.retire(apply=True)["status"], "RETIRED")
        self.assertFalse(self.replica.exists())
        self.assertTrue(self.receipt.exists())
        self.assertTrue((self.root / "result.json").exists())
        self.assertTrue((self.root / "run.log").exists())
        with tarfile.open(self.root / "retired-profile-evidence.tar.gz") as bundle:
            self.assertEqual(bundle.extractfile("events.jsonl").read(),
                             b'{"event":"done"}\n')
        self.assertEqual(self.retire(apply=True)["status"], "RETIRED")

    def test_refuses_running_or_mutated_run(self):
        for status, mutated in (("RUNNING", False), ("PASS", True), ("FAIL", False)):
            self.record.update(status=status, source_mutated=mutated)
            self.write_receipt()
            with self.assertRaises(ValueError):
                self.retire(apply=True)
            self.assertTrue(self.replica.exists())

    def test_refuses_path_escape_and_snapshot(self):
        for name in ("../profile", "source-snapshot", "/tmp"):
            with self.assertRaises(ValueError):
                self.retire(name, apply=True)
        self.assertTrue(self.replica.exists())

    def test_refuses_missing_result(self):
        (self.root / "result.json").unlink()
        with self.assertRaises(ValueError):
            self.retire(apply=True)
        self.assertTrue(self.replica.exists())

    def test_refuses_live_replica(self):
        with patch("scripts.bamf.detached.retire_replica.require_idle",
                   side_effect=ValueError("replica still has open files")):
            with self.assertRaisesRegex(ValueError, "open files"):
                self.retire(apply=True)
        self.assertTrue(self.replica.exists())


if __name__ == "__main__":
    unittest.main()
