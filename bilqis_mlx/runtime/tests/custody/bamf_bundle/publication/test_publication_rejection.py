"""B13 rejection evidence remains bound to live immutable publication custody."""
from __future__ import annotations

import json
import os
import shutil
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation, record_bamf_rejection,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    publish_candidate, accepted_state, candidate, parent_state, rejected_state,
    shape_patch,
)


class BamfPublicationRejectionTests(unittest.TestCase):
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
            return publish_candidate(self.run, source)

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

    def test_rejection_requires_valid_content_addressed_tensor_payload(self):
        published = self.publish(candidate(parent_state()))
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        bundle = self.run / published["bundle"]
        manifest = json.loads((bundle / "manifest.json").read_text())
        tensor = data_plane().require_file_object(manifest["tensors"]["object_sha256"])
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



if __name__ == "__main__":
    unittest.main()
