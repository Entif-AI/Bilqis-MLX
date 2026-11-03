"""B13.2 cold-resume continuation witnesses through the published pointer path.

The witness starts from a source-qualified accepted generation published
through the real pointer and lock path, cold resumes it in a clean process,
executes the next controlled optimizer step and publishes the successor
generation. Synthetic direct save-load paths cannot satisfy acceptance.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation, publish_bamf_generation, save_bamf_bundle,
)

from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import (
    retained_digest,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, parent_state, shape_patch,
)

PROBE = ("bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe")
REPOSITORY_ROOT = Path(__file__).resolve().parents[5]


class BamfColdResumeContinuationTests(unittest.TestCase):
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

    def probe(self, run=None):
        """Cold resume in a clean process and return its receipt."""
        target = Path(run or self.run)
        process = subprocess.run(
            [sys.executable, "-m", PROBE, str(target)],
            cwd=str(REPOSITORY_ROOT), capture_output=True, text=True,
            env=dict(os.environ), timeout=300)
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout.strip().splitlines()[-1])

    def test_cold_resume_continues_the_next_controlled_optimizer_step(self):
        initial = parent_state()
        first = self.publish(candidate(initial))
        receipt = self.probe()
        self.assertEqual(receipt["generation"], 0)
        self.assertEqual(receipt["manifest_sha256"], first["manifest_sha256"])
        self.assertEqual(receipt["state_digest"], retained_digest(initial))
        self.assertEqual(receipt["teacher_state"], dict(
            candidate(initial).teacher_state))
        self.assertEqual(receipt["optimizer_step"], initial.optimizer_step)
        expected = accepted_state(initial)
        self.assertEqual(receipt["successor_optimizer_step"], expected.optimizer_step)
        self.assertEqual(receipt["successor_digest"], retained_digest(expected))
        self.assertEqual(receipt["published"]["generation"], 1)
        self.assertEqual(
            receipt["published"]["parent_manifest_sha256"], first["manifest_sha256"])

    def test_cold_resumed_generation_is_the_published_generation(self):
        initial = parent_state()
        first = self.publish(candidate(initial))
        self.probe()
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["generation"], 1)
        self.assertEqual(pointer["parent_manifest_sha256"], first["manifest_sha256"])
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(student.generation, 1)
        self.assertEqual(student.retained_state.optimizer_step, 12)
        self.assertEqual(retained_digest(student.retained_state),
                         retained_digest(accepted_state(initial)))

    def test_synthetic_direct_save_load_cannot_satisfy_acceptance(self):
        initial = parent_state()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            save_bamf_bundle(candidate(initial), self.root / "unpublished")
        self.assertFalse((self.root / "unpublished" / "bamf-state.json").exists())
        with self.assertRaises(BilqisError):
            load_bamf_generation(self.root / "unpublished" / "bamf-state.json")
        process = subprocess.run(
            [sys.executable, "-m", PROBE, str(self.root / "unpublished")],
            cwd=str(REPOSITORY_ROOT), capture_output=True, text=True,
            env=dict(os.environ), timeout=300)
        self.assertNotEqual(process.returncode, 0)

    def test_cold_resume_refuses_a_generation_without_published_custody(self):
        process = subprocess.run(
            [sys.executable, "-m", PROBE, str(self.root / "absent")],
            cwd=str(REPOSITORY_ROOT), capture_output=True, text=True,
            env=dict(os.environ), timeout=300)
        self.assertNotEqual(process.returncode, 0)


if __name__ == "__main__":
    unittest.main()
