"""B13.1 crash, retry, pointer-lineage and outbox witnesses."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from dataclasses import replace
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

    def test_unsafe_run_root_rejects_before_publication_or_lock_writes(self):
        for kind in ("symlink", "file"):
            with self.subTest(kind=kind):
                run = self.root / kind
                outside = self.root / (kind + "-outside")
                if kind == "symlink":
                    outside.mkdir()
                    run.symlink_to(outside, target_is_directory=True)
                else:
                    run.write_text("not-a-directory")
                self.run = run

                with self.assertRaises(BilqisError):
                    self.publish(candidate(parent_state()))
                if kind == "symlink":
                    self.assertEqual(tuple(outside.iterdir()), ())
                else:
                    self.assertEqual(run.read_text(), "not-a-directory")

                with self.assertRaises(BilqisError):
                    load_bamf_generation(run / "bamf-state.json")
                if kind == "symlink":
                    self.assertEqual(tuple(outside.iterdir()), ())

    def test_symlinked_bundle_root_rejects_before_external_bundle_write(self):
        self.run.mkdir()
        outside = self.root / "outside-bundles"
        outside.mkdir()
        (self.run / "bamf-bundles").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(BilqisError):
            self.publish(candidate(parent_state()))

        self.assertEqual(tuple(outside.iterdir()), ())
        self.assertFalse((self.run / "bamf-state.json").exists())

    def test_nested_bundle_alias_cannot_redirect_cold_load(self):
        published = self.publish(candidate(parent_state()))
        source = self.run / published["bundle"]
        outside = self.root / "outside"
        outside.mkdir()
        shutil.copytree(source, outside / published["manifest_sha256"])
        shutil.rmtree(source)
        (self.run / "bamf-bundles" / "alias").symlink_to(
            outside, target_is_directory=True)
        pointer_path = self.run / "bamf-state.json"
        pointer = json.loads(pointer_path.read_text())
        pointer["bundle"] = "bamf-bundles/alias/" + published["manifest_sha256"]
        pointer_path.write_text(json.dumps(pointer))

        with self.assertRaises(BilqisError):
            load_bamf_generation(pointer_path)

    def test_pointer_requires_exact_canonical_bundle_spelling(self):
        published = self.publish(candidate(parent_state()))
        pointer_path = self.run / "bamf-state.json"
        pointer = json.loads(pointer_path.read_text())
        digest = published["manifest_sha256"]
        for spelling in (
                f"bamf-bundles//{digest}",
                f"bamf-bundles/./{digest}",
                f"bamf-bundles/{digest}/"):
            with self.subTest(spelling=spelling):
                pointer["bundle"] = spelling
                pointer_path.write_text(json.dumps(pointer))
                with self.assertRaises(BilqisError):
                    load_bamf_generation(pointer_path)

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

    def test_rejection_uses_live_bundle_state_not_caller_student_fields(self):
        first = self.publish(candidate(parent_state()))
        second = self.publish(candidate(
            accepted_state(parent_state()), 1, first["manifest_sha256"]))
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        forged = replace(
            student,
            retained_state=replace(
                student.retained_state,
                optimizer_step=student.retained_state.optimizer_step + 1))

        record_bamf_rejection(self.run, forged, {"reason": "retention_gate"})

        events = [json.loads(line) for line in (self.run / "events.jsonl").read_text().splitlines()]
        rejected = [row for row in events if row["event"] == "BAMF_CANDIDATE_REJECTED"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["optimizer_step"], 12)
        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text())["manifest_sha256"],
            second["manifest_sha256"])

    def test_rejection_requires_live_local_bundle(self):
        published = self.publish(candidate(parent_state()))
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        shutil.rmtree(self.run / "bamf-bundles")

        with self.assertRaises(BilqisError):
            record_bamf_rejection(self.run, student, {"reason": "retention_gate"})

        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text())["manifest_sha256"],
            published["manifest_sha256"])

    def test_rejection_requires_complete_local_bundle_payload(self):
        published = self.publish(candidate(parent_state()))
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        bundle = self.run / published["bundle"]
        for mode in ("manifest-only", "sidecar-symlink"):
            with self.subTest(mode=mode):
                backup = self.root / ("backup-" + mode)
                shutil.copytree(bundle, backup)
                if mode == "manifest-only":
                    for path in bundle.iterdir():
                        if path.name != "manifest.json":
                            path.unlink()
                else:
                    sidecar = bundle / "semantic-abi.json"
                    outside = self.root / "outside-semantic-abi.json"
                    outside.write_bytes(sidecar.read_bytes())
                    sidecar.unlink()
                    sidecar.symlink_to(outside)
                with self.assertRaises(BilqisError):
                    record_bamf_rejection(
                        self.run, student, {"reason": "retention_gate"})
                shutil.rmtree(bundle)
                backup.rename(bundle)

    def test_rejection_requires_valid_local_tensor_payload(self):
        published = self.publish(candidate(parent_state()))
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        bundle = self.run / published["bundle"]
        tensor = bundle / "bamf-state.safetensors"
        original = tensor.read_bytes()
        outside = self.root / "outside-tensor.safetensors"
        outside.write_bytes(original)
        for mode in ("missing", "symlink", "corrupt"):
            with self.subTest(mode=mode):
                if tensor.exists() or tensor.is_symlink():
                    tensor.unlink()
                if mode == "symlink":
                    tensor.symlink_to(outside)
                elif mode == "corrupt":
                    tensor.write_bytes(original + b"x")
                with self.assertRaises(BilqisError):
                    record_bamf_rejection(
                        self.run, student, {"reason": "retention_gate"})
                if tensor.exists() or tensor.is_symlink():
                    tensor.unlink()
                tensor.write_bytes(original)

    def test_rejection_rejects_symlinked_bundle_custody(self):
        self.publish(candidate(parent_state()))
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        outside = self.root / "outside-bundles"
        (self.run / "bamf-bundles").rename(outside)
        (self.run / "bamf-bundles").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(BilqisError):
            record_bamf_rejection(self.run, student, {"reason": "retention_gate"})

    def test_rejection_rejects_pointer_manifest_run_mismatch(self):
        self.publish(candidate(parent_state()))
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        pointer_path = self.run / "bamf-state.json"
        pointer = json.loads(pointer_path.read_text())
        pointer["run_id"] = "fixture-run-forged"
        pointer_path.write_text(json.dumps(pointer))
        forged = replace(student, run_id="fixture-run-forged")

        with self.assertRaises(BilqisError):
            record_bamf_rejection(self.run, forged, {"reason": "retention_gate"})

    def test_successor_rejects_pointer_manifest_lineage_mismatch(self):
        first = self.publish(candidate(parent_state()))
        pointer_path = self.run / "bamf-state.json"
        pointer = json.loads(pointer_path.read_text())
        pointer["run_id"] = "fixture-run-forged"
        pointer_path.write_text(json.dumps(pointer))
        successor = replace(
            candidate(
                accepted_state(parent_state()), 1, first["manifest_sha256"]),
            run_id="fixture-run-forged")

        with self.assertRaises(BilqisError):
            self.publish(successor)


if __name__ == "__main__":
    unittest.main()
