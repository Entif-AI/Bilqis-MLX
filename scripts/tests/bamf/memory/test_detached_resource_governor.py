"""Detached Python workers must inherit Deh Guhbohnayhituh policy."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

from scripts.bamf.detached_long_run import _snapshot_workdir, _worker


class DetachedResourceGovernorTests(unittest.TestCase):
    def test_python_worker_forwards_custom_ceiling_to_child_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            snapshot = root / "snapshot"
            source.mkdir()
            (source / "subject.py").write_text("VALUE = 'before'\n", encoding="utf-8")
            snapshot_receipt = _snapshot_workdir(source, snapshot)
            receipt = root / "receipt.json"
            log = root / "run.log"
            args = SimpleNamespace(
                label="custom-resource-governor-test",
                workdir=snapshot,
                source_workdir=source,
                source_sha256=snapshot_receipt["source_sha256"],
                snapshot_sha256=snapshot_receipt["snapshot_sha256"],
                log=log,
                receipt=receipt,
                pid_file=root / "pid",
                no_notify=True,
                memory_ceiling_gib=14.0,
                command=[
                    sys.executable, "-B", "-c",
                    "import os; print('CEILING_ENV=' + str(os.environ.get("
                    "'BILQIS_TRAINER_MEMORY_CEILING_GIB')))",
                ],
            )

            self.assertEqual(_worker(args), 0)
            self.assertIn("CEILING_ENV=14.0", log.read_text(encoding="utf-8"))

    def test_python_worker_records_default_resource_governor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            snapshot = root / "snapshot"
            source.mkdir()
            (source / "subject.py").write_text("VALUE = 'before'\n", encoding="utf-8")
            snapshot_receipt = _snapshot_workdir(source, snapshot)
            receipt = root / "receipt.json"
            args = SimpleNamespace(
                label="resource-governor-test",
                workdir=snapshot,
                source_workdir=source,
                source_sha256=snapshot_receipt["source_sha256"],
                snapshot_sha256=snapshot_receipt["snapshot_sha256"],
                log=root / "run.log",
                receipt=receipt,
                pid_file=root / "pid",
                no_notify=True,
                command=[sys.executable, "-B", "-c", "print('bounded')"],
            )

            self.assertEqual(_worker(args), 0)
            result = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(result["resource_governor"]["model"], "CR-8s")
            self.assertEqual(
                result["resource_governor"]["policy"]["ceiling_bytes"],
                12 * 1024**3,
            )


if __name__ == "__main__":
    unittest.main()
