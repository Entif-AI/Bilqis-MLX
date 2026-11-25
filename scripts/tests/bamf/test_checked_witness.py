"""Checked-witness launch and import/probe regressions; no model execution."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import ModuleType
from unittest.mock import patch

from scripts.bamf.detached.imports import resolve_module, resolve_source
from scripts.bamf.detached.probes import ProbeBook

ROOT = Path(__file__).resolve().parents[3]


class CheckedProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the real production import entrypoint (the leaf is mutually
        # dependent on atlas_model_microbatch).
        from bilqis_mlx.runtime import atlas_model
        cls.model = atlas_model

    def test_runtime_physical_import_reports_canonical_name(self):
        with self.assertRaisesRegex(ImportError, r"bilqis_mlx\.runtime\.microbatch\.execution"):
            resolve_module(
                "bilqis_mlx.runtime._model.backbone.microbatch.execution", ROOT)
        module = resolve_module("bilqis_mlx.runtime.microbatch.execution", ROOT)
        physical = Path("bilqis_mlx/runtime/_model/backbone/microbatch/execution.py")
        self.assertEqual(Path(module.__file__).resolve(), ROOT / physical)
        self.assertIs(resolve_source(physical, ROOT), module)

    def test_wrong_consumer_and_missing_binding_rejected(self):
        probes = ProbeBook(ROOT)
        self.addCleanup(probes.restore)
        with self.assertRaisesRegex(ValueError, "does not load"):
            probes.bind("bilqis_mlx.runtime.atlas_model_microbatch",
                        "_materialize_gradient", "_materialize_gradient")
        with self.assertRaisesRegex(ValueError, "missing.*binding"):
            probes.bind("bilqis_mlx.runtime.microbatch.execution",
                        "_learning_first_microbatch_value_and_grad_impl", "absent")
        probes.bind("bilqis_mlx.runtime.microbatch.execution",
                    "_learning_first_microbatch_value_and_grad_impl", "_materialize_gradient")
        with self.assertRaisesRegex(RuntimeError, "no observed calls"):
            probes.require_calls()
        probes.restore()

    def test_probe_target_duplicate_identity_rejected(self):
        module = resolve_module("bilqis_mlx.runtime.microbatch.execution", ROOT)
        duplicate = ModuleType("bilqis_mlx.test_duplicate_execution")
        duplicate.__file__ = module.__file__
        with patch.dict(sys.modules, {duplicate.__name__: duplicate}):
            with self.assertRaisesRegex(ImportError, "duplicate module identity"):
                resolve_module(module.__name__, ROOT)

    def test_ambiguous_runtime_search_paths_rejected(self):
        from bilqis_mlx import runtime
        with tempfile.TemporaryDirectory() as directory:
            rival = Path(directory) / "microbatch"
            rival.mkdir()
            (rival / "__init__.py").write_text("")
            with patch.object(runtime, "__path__", [*runtime.__path__, directory]):
                with self.assertRaisesRegex(ImportError, "outside snapshot|ambiguous module"):
                    resolve_module("bilqis_mlx.runtime.microbatch.execution", ROOT)

    def test_actual_bad_harness_import_reports_canonical_name(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "probe.py"
            harness.write_text(
                "def prepare(argv, probes):\n"
                "    from bilqis_mlx.runtime._model.backbone.microbatch import execution\n"
                "    return lambda: 0\n")
            result = subprocess.run([
                sys.executable, "-B", "-m", "scripts.bamf.detached.checked_witness",
                "preflight", str(harness), hashlib.sha256(harness.read_bytes()).hexdigest(),
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical import candidate: bilqis_mlx.runtime.microbatch",
                          result.stderr)

    def test_wrong_root_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ImportError, "outside snapshot"):
                resolve_module("bilqis_mlx.runtime.microbatch.execution", Path(directory))

    def test_real_planning_profile_prepares_without_running_planning(self):
        path = ROOT / "scripts/bamf/profiling/planning_incremental_profile.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "profile.json"
            command = [
                sys.executable, "-B", "-m", "scripts.bamf.detached.checked_witness",
                "preflight", str(path), hashlib.sha256(path.read_bytes()).hexdigest(),
                str(root), "--output", str(output),
            ]
            rejected = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("ISSUE1536_DISPOSABLE_PROFILE_MARKER_REQUIRED", rejected.stderr)
            (root / ".issue1536-disposable-profile").touch()
            prepared = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertIn("CHECKED_WITNESS_PREFLIGHT_PASS", prepared.stdout)
            self.assertFalse(output.exists())



if __name__ == "__main__":
    unittest.main()
