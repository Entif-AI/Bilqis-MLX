"""Regression coverage for detached-run source isolation."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest

from scripts.bamf.detached_long_run import (
    SOURCE_MUTATED_EXIT, _snapshot_workdir, _worker,
)


class DetachedLongRunTests(unittest.TestCase):
    def test_snapshot_preserves_internal_broken_symlink_but_rejects_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "internal.py").symlink_to("missing.py")

            snapshot = root / "snapshot"
            _snapshot_workdir(source, snapshot)
            self.assertTrue((snapshot / "internal.py").is_symlink())
            self.assertEqual((snapshot / "internal.py").readlink(), Path("missing.py"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "escape.py").symlink_to("../outside.py")
            with self.assertRaisesRegex(RuntimeError, "escapes workdir"):
                _snapshot_workdir(source, root / "snapshot")

    def test_snapshot_child_cannot_see_later_worktree_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            snapshot = root / "snapshot"
            source.mkdir()
            (source / "subject.py").write_text("VALUE = 'before'\n", encoding="utf-8")
            (source / "probe.py").write_text(
                "from subject import VALUE\nprint(VALUE)\n", encoding="utf-8")

            receipt = _snapshot_workdir(source, snapshot)
            (source / "subject.py").write_text("VALUE = 'after'\n", encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, "-B", "probe.py"],
                cwd=snapshot,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.strip(), "before")
            self.assertEqual(receipt["source_sha256"], receipt["snapshot_sha256"])

    def test_worker_fails_if_command_mutates_snapshot_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            snapshot = root / "snapshot"
            source.mkdir()
            (source / "subject.py").write_text("VALUE = 'before'\n", encoding="utf-8")
            snapshot_receipt = _snapshot_workdir(source, snapshot)
            receipt = root / "receipt.json"
            args = SimpleNamespace(
                label="mutation-test",
                workdir=snapshot,
                source_workdir=source,
                source_sha256=snapshot_receipt["source_sha256"],
                snapshot_sha256=snapshot_receipt["snapshot_sha256"],
                log=root / "run.log",
                receipt=receipt,
                pid_file=root / "pid",
                no_notify=True,
                command=[
                    sys.executable, "-B", "-c",
                    "from pathlib import Path; Path('subject.py').write_text('changed\\n')",
                ],
            )

            self.assertEqual(_worker(args), SOURCE_MUTATED_EXIT)
            result = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(result["source_mutated"])
            self.assertEqual(result["command_returncode"], 0)


if __name__ == "__main__":
    unittest.main()
