"""Opt-in complete B01/B12 tensor custody in a fresh CPU process."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.backup import digest_file
from bilqis_mlx.runtime.bamf_bundle import save_bamf_bundle
from bilqis_mlx.runtime.tests.custody.bamf_bundle.full_resume_probe import (
    full_candidate, observe_bundle, observe_student,
)


@unittest.skipUnless(os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
                     "set BILQIS_BAMF_FULL_WITNESS for complete disposable custody")
class FullResumeTests(unittest.TestCase):
    def test_complete_tree_and_numerical_output_match_clean_process(self):
        mx.set_default_device(mx.cpu)
        with TemporaryDirectory() as root:
            root = Path(root)
            with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(root / "plane.sqlite3")}):
                candidate = full_candidate()
                expected = json.loads(json.dumps(observe_student(candidate), sort_keys=True))
                manifest = save_bamf_bundle(candidate, root / "bundle")
                before = {p.name: digest_file(p) for p in (root / "bundle").iterdir()}
                self.assertEqual(observe_bundle(root / "bundle", manifest["manifest_sha256"]), expected)
                self.assertEqual({p.name: digest_file(p) for p in (root / "bundle").iterdir()}, before)
                result = subprocess.run(
                    [sys.executable, "-B", "-m",
                     "bilqis_mlx.runtime.tests.custody.bamf_bundle.full_resume_probe",
                     str(root / "bundle"), manifest["manifest_sha256"]],
                    capture_output=True, text=True, check=True, timeout=180,
                )
                observed = json.loads(result.stdout)
                self.assertEqual(observed, expected)
                self.assertEqual({p.name: digest_file(p) for p in (root / "bundle").iterdir()}, before)
                self.assertEqual(expected["parameter_count"], 79_469_798)
                self.assertEqual(expected["parameter_tensor_count"], 214)
                self.assertEqual(expected["serialized_tensor_count"], 856)
                self.assertEqual(expected["teacher_next_seed"], 42)
                self.assertEqual(expected["teacher_cursor"], "lesson:7")
                self.assertEqual(expected["optimizer_step"], 12)
                self.assertTrue(expected["backbone_output_finite"])
                self.assertEqual(expected["status"], "UNBOUND_NUMERICAL_CUSTODY_ONLY")
