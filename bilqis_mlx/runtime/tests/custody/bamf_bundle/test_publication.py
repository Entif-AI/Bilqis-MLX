"""B13.1 crash, retry, pointer-lineage and outbox witnesses."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.bamf_bundle.publication as publication
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation, publish_bamf_generation, record_bamf_rejection,
)

from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, parent_state, rejected_state, shape_patch,
)


class BamfPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_bamf_generation(self.run, source)

    def test_accepted_generation_advances_once_and_parent_bundle_remains(self):
        initial_state = parent_state()
        first = self.publish(candidate(initial_state))
        retained = accepted_state(initial_state)
        second_source = candidate(retained, 1, first["manifest_sha256"])
        second = self.publish(second_source)
        with shape_patch():
            loaded = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(loaded.generation, 1)
        self.assertEqual(loaded.retained_state.optimizer_step, 12)
        self.assertEqual(loaded.parent_manifest_sha256, first["manifest_sha256"])
        self.assertTrue((self.run / first["bundle"]).is_dir())
        self.assertNotEqual(first["manifest_sha256"], second["manifest_sha256"])

    def test_retry_converges_after_renamed_bundle_before_pointer(self):
        source = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(publication, "_atomic_pointer", side_effect=RuntimeError("crash")):
            with self.assertRaisesRegex(RuntimeError, "crash"):
                publish_bamf_generation(self.run, source)
        self.assertFalse((self.run / "bamf-state.json").exists())
        published = self.publish(source)
        self.assertTrue((self.run / published["bundle"]).is_dir())
        self.assertEqual(json.loads((self.run / "bamf-state.json").read_text()), published)

    def test_stale_old_style_stage_does_not_block_retry(self):
        stale = self.run / ".bamf-staging" / "0000000"
        stale.mkdir(parents=True)
        (stale / "partial").write_text("interrupted")
        published = self.publish(candidate(parent_state()))
        self.assertTrue((self.run / published["bundle"]).is_dir())
        self.assertEqual((stale / "partial").read_text(), "interrupted")

    def test_pointer_written_before_outbox_crash_replays_exactly_once(self):
        source = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(publication, "reconcile_bamf_outbox", side_effect=RuntimeError("crash")):
            with self.assertRaisesRegex(RuntimeError, "crash"):
                publish_bamf_generation(self.run, source)
        self.assertTrue((self.run / "bamf-state.json").is_file())
        with shape_patch():
            first = load_bamf_generation(self.run / "bamf-state.json")
            second = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(first.retained_state.optimizer_step, 11)
        self.assertEqual(second.retained_state.optimizer_step, 11)
        events = [json.loads(line) for line in (self.run / "events.jsonl").read_text().splitlines()]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "FIXTURE_ACCEPTED")

    def test_competing_same_generation_cannot_overwrite_pointer(self):
        first = self.publish(candidate(parent_state()))
        different = candidate(accepted_state(parent_state()))
        with self.assertRaises(BilqisError):
            self.publish(different)
        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text())["manifest_sha256"],
            first["manifest_sha256"])

    def test_second_process_holding_writer_lock_fails_before_pointer_change(self):
        script = (
            "import fcntl,os,sys,pathlib; "
            "root=pathlib.Path(sys.argv[1]); root.mkdir(parents=True,exist_ok=True); "
            "fd=os.open(root/'.bamf-pointer.lock',os.O_RDWR|os.O_CREAT,0o600); "
            "fcntl.flock(fd,fcntl.LOCK_EX); print('locked',flush=True); "
            "sys.stdin.readline(); fcntl.flock(fd,fcntl.LOCK_UN); os.close(fd)"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(self.run)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "locked")
            with self.assertRaises(BilqisError):
                self.publish(candidate(parent_state()))
            self.assertFalse((self.run / "bamf-state.json").exists())
        finally:
            process.stdin.write("\n")
            process.stdin.flush()
            process.wait(timeout=5)

    def test_b12_rejection_records_evidence_without_generation_change(self):
        initial = parent_state()
        first = self.publish(candidate(initial))
        accepted = accepted_state(initial)
        second = self.publish(candidate(accepted, 1, first["manifest_sha256"]))
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        rejected = rejected_state(accepted)
        self.assertIs(rejected, accepted)
        attempted_successor = candidate(
            rejected, 2, second["manifest_sha256"])
        with self.assertRaises(BilqisError):
            self.publish(attempted_successor)
        evidence = {"reason": "retention_gate", "candidate_optimizer_step": 13}
        first_receipt = record_bamf_rejection(self.run, student, evidence)
        second_receipt = record_bamf_rejection(self.run, student, evidence)
        self.assertEqual(first_receipt, second_receipt)
        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text())["manifest_sha256"],
            second["manifest_sha256"])
        events = [json.loads(line) for line in (self.run / "events.jsonl").read_text().splitlines()]
        rejected_events = [row for row in events if row["event"] == "BAMF_CANDIDATE_REJECTED"]
        self.assertEqual(len(rejected_events), 1)
        self.assertEqual(rejected_events[0]["optimizer_step"], 12)
        with shape_patch():
            resumed = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(resumed.generation, 1)
        self.assertEqual(resumed.retained_state.optimizer_step, 12)
        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text())["manifest_sha256"],
            second["manifest_sha256"])


if __name__ == "__main__":
    unittest.main()
