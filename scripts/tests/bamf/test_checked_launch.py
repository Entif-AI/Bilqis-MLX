"""Portable checked-witness detached lifecycle regressions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


class CheckedLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        tooling = self.source / "scripts/bamf"
        tooling.mkdir(parents=True)
        shutil.copytree(ROOT / "scripts/bamf/detached", tooling / "detached",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "scripts/bamf/detached_long_run.py", tooling)
        package = self.source / "bilqis_mlx"
        package.mkdir()
        (package / "__init__.py").write_text("")
        (package / "consumer.py").write_text(
            "def kernel(): return 7\ndef use(): return kernel()\n")
        self.harness = self.root / "witness.py"
        self.output = self.root / "ran"
        self.log = self.root / "log"
        self.receipt = self.root / "receipt.json"

    def launch(self, source, launcher=None):
        self.harness.write_text(source)
        return subprocess.run([
            sys.executable, "-B", str(launcher or self.source / "scripts/bamf/detached_long_run.py"),
            "launch", "--label", "checked-test", "--workdir", str(self.source),
            "--snapshot", str(self.root / "snapshot"), "--log", str(self.log),
            "--receipt", str(self.receipt), "--pid-file", str(self.root / "pid"),
            "--no-notify", "--witness", str(self.harness), "--", str(self.output),
        ], cwd=self.source, capture_output=True, text=True, timeout=20)

    def test_import_failure_blocks_launch_and_expensive_callback(self):
        result = self.launch(
            "def prepare(argv, probes):\n"
            "    import bilqis_mlx.missing\n"
            "    return lambda: open(argv[0], 'w').write('bad')\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())
        self.assertFalse((self.root / "pid").exists())
        self.assertEqual(json.loads(self.receipt.read_text())["stage"], "PREFLIGHT")
        self.assertIn("bilqis_mlx.missing", self.log.read_text())
        self.assertFalse((self.root / "snapshot").exists())

    def test_missing_snapshot_worker_fails_before_detachment(self):
        (self.source / "scripts/bamf/detached_long_run.py").unlink()
        result = self.launch(
            "def prepare(argv, probes): return lambda: 0\n",
            launcher=ROOT / "scripts/bamf/detached_long_run.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(self.receipt.read_text())["stage"], "PREFLIGHT")
        self.assertIn("snapshot worker entrypoint missing", self.log.read_text())
        self.assertFalse((self.root / "snapshot").exists())
        self.assertFalse((self.root / "pid").exists())

    def test_failed_git_snapshot_retires_only_owned_copy(self):
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.source), *args], text=True)
        git("init", "-q")
        git("config", "user.name", "Detached tests")
        git("config", "user.email", "tests@example.invalid")
        git("add", ".")
        git("commit", "-qm", "seed")
        (self.source / "dirty.txt").write_text("preserve")
        result = self.launch("def prepare(argv, probes): raise ValueError('bad fixture')\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.source / "dirty.txt").read_text(), "preserve")
        self.assertFalse((self.root / "snapshot").exists())
        self.assertNotIn(str((self.root / "snapshot").resolve()), git("worktree", "list"))
        self.assertTrue(json.loads(self.receipt.read_text())["snapshot_removed"])

    def test_checked_execution_requires_actual_consumer_calls(self):
        self.harness.write_text(
            "def prepare(argv, probes):\n"
            "    from bilqis_mlx import consumer\n"
            "    probes.bind('bilqis_mlx.consumer', 'use', 'kernel')\n"
            "    consumer.use()\n"
            "    return lambda: consumer.kernel() and 0\n")
        digest = hashlib.sha256(self.harness.read_bytes()).hexdigest()
        result = subprocess.run([
            sys.executable, "-B", "-m", "scripts.bamf.detached.checked_witness",
            "run", str(self.harness), digest,
        ], cwd=self.source, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no observed calls", result.stderr)

    def test_changed_witness_is_rejected_before_setup(self):
        self.harness.write_text("def prepare(argv, probes): return lambda: 0\n")
        digest = hashlib.sha256(self.harness.read_bytes()).hexdigest()
        self.harness.write_text("raise AssertionError('changed code executed')\n")
        result = subprocess.run([
            sys.executable, "-B", "-m", "scripts.bamf.detached.checked_witness",
            "run", str(self.harness), digest,
        ], cwd=self.source, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checked witness source changed", result.stderr)
        self.assertNotIn("changed code executed", result.stderr)

    def test_legacy_raw_harness_requires_explicit_disposition(self):
        self.harness.write_text("raise AssertionError('must not execute')\n")
        result = subprocess.run([
            sys.executable, "-B", str(self.source / "scripts/bamf/detached_long_run.py"),
            "launch", "--label", "unchecked-test", "--workdir", str(self.source),
            "--snapshot", str(self.root / "snapshot"), "--log", str(self.log),
            "--receipt", str(self.receipt), "--pid-file", str(self.root / "pid"),
            "--no-notify", "--", sys.executable, "-B", str(self.harness),
        ], cwd=self.source, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --witness PATH", result.stderr)
        self.assertFalse((self.root / "snapshot").exists())

    def test_preflight_source_mutation_is_rejected(self):
        result = self.launch(
            "from pathlib import Path\n"
            "def prepare(argv, probes):\n"
            "    Path('unexpected.py').write_text('pass')\n"
            "    return lambda: 0\n")
        self.assertNotEqual(result.returncode, 0)
        receipt = json.loads(self.receipt.read_text())
        self.assertTrue(receipt["source_mutated"])
        self.assertEqual(receipt["stage"], "PREFLIGHT")
        self.assertFalse((self.root / "pid").exists())
        self.assertEqual((self.root / "snapshot/unexpected.py").read_text(), "pass")

    def test_worker_snapshot_mismatch_has_terminal_receipt(self):
        result = subprocess.run([
            sys.executable, "-B", str(self.source / "scripts/bamf/detached_long_run.py"),
            "_worker", "--label", "changed-snapshot", "--workdir", str(self.source),
            "--snapshot-sha256", "0" * 64, "--log", str(self.log),
            "--receipt", str(self.receipt), "--pid-file", str(self.root / "pid"),
            "--no-notify", "--", sys.executable, "-c", "print('must not run')",
        ], cwd=self.source, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["stage"], "WORKER_START")
        self.assertTrue(receipt["source_mutated"])
        self.assertNotIn("must not run", self.log.read_text())

    def terminal_receipt(self):
        for _ in range(100):
            if self.receipt.exists():
                receipt = json.loads(self.receipt.read_text())
                if receipt["status"] in ("PASS", "FAIL"):
                    return receipt
            time.sleep(.05)
        self.fail("detached fixture did not produce terminal receipt")

    def test_changed_probe_contract_blocks_expensive_callback(self):
        result = self.launch(
            "from pathlib import Path\n"
            "import sys\n"
            "def prepare(argv, probes):\n"
            "    if sys.argv[1] == 'preflight':\n"
            "        probes.bind('bilqis_mlx.consumer', 'use', 'kernel')\n"
            "    def run():\n"
            "        Path(argv[0]).write_text('must not run')\n"
            "    return run\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = self.terminal_receipt()
        self.assertEqual(receipt["status"], "FAIL")
        self.assertFalse(self.output.exists())
        self.assertIn("probe contract changed", self.log.read_text())

    def test_checked_worker_cannot_claim_unperformed_preflight(self):
        result = subprocess.run([
            sys.executable, "-B", str(self.source / "scripts/bamf/detached_long_run.py"),
            "_worker", "--label", "unchecked-worker", "--workdir", str(self.source),
            "--log", str(self.log), "--receipt", str(self.receipt),
            "--pid-file", str(self.root / "pid"), "--no-notify",
            "--witness", str(self.harness), "--", sys.executable, "-c",
            "print('unchecked callback')",
        ], cwd=self.source, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt["stage"], "WORKER_START")
        self.assertNotEqual(receipt.get("preflight_status"), "PASS")
        self.assertNotIn("unchecked callback", self.log.read_text())

    def test_zero_exit_without_completion_marker_is_failure(self):
        result = self.launch(
            "import os\n"
            "def prepare(argv, probes):\n"
            "    from bilqis_mlx import consumer\n"
            "    probes.bind('bilqis_mlx.consumer', 'use', 'kernel')\n"
            "    consumer.use()\n"
            "    return lambda: os._exit(0)\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = self.terminal_receipt()
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["command_returncode"], 0)
        self.assertIn("checked witness completion", self.log.read_text())

    def test_verified_snapshot_executes_same_preparation_and_actual_probe(self):
        source = (
            "from pathlib import Path\n"
            "import subprocess, sys\n"
            "def prepare(argv, probes):\n"
            "    from bilqis_mlx import consumer\n"
            "    probes.bind(Path('bilqis_mlx/consumer.py'), 'use', 'kernel')\n"
            "    def run():\n"
            "        value = consumer.use()\n"
            "        path = subprocess.check_output([sys.executable, '-B', '-c', "
            "'from bilqis_mlx import consumer; print(consumer.__file__)'], text=True)\n"
            "        Path(argv[0]).write_text(str(value) + '\\n' + path.strip())\n"
            "        return 0\n"
            "    return run\n")
        with patch.dict(os.environ, {"PYTHONPATH": str(self.source)}):
            result = self.launch(source)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = self.terminal_receipt()
        self.assertEqual(receipt["status"], "PASS", self.log.read_text())
        self.assertEqual(self.output.read_text().splitlines(), [
            "7", str((self.root / "snapshot/bilqis_mlx/consumer.py").resolve())])
        self.assertEqual(receipt["preflight_status"], "PASS")
        self.assertEqual(
            receipt["probe_results"]["bilqis_mlx.consumer.use:kernel"]["calls"], 1)
        self.assertIn("CHECKED_WITNESS_PREFLIGHT_PASS", self.log.read_text())
        self.assertIn("CHECKED_WITNESS_COMPLETE", self.log.read_text())


if __name__ == "__main__":
    unittest.main()
