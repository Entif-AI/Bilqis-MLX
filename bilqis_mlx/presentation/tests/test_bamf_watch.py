"""Detached BAMF observation commands never mutate the viewed run."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bilqis_mlx.presentation.dashboard_watch import watch
from bilqis_mlx.presentation.tests.test_bamf_metrics import receipt


class BamfWatchTests(unittest.TestCase):
    def test_real_snapshot_command_parses_details_and_keeps_journal_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            journal = run / "events.jsonl"
            payload = json.dumps({"event": "BAMF_OPERATOR_STATUS_OBSERVED",
                                  "receipt": receipt()}) + "\n"
            journal.write_text(payload)
            before = journal.stat()
            result = subprocess.run(
                [sys.executable, "-B", "-m", "bilqis_mlx.presentation.dashboard_watch",
                 "--run-dir", str(run), "--once", "--atlas-details"],
                cwd=Path(__file__).resolve().parents[3], text=True, capture_output=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ATLAS source " + "a" * 64, result.stdout)
            self.assertIn("census " + "e" * 64, result.stdout)
            self.assertEqual(journal.read_text(), payload)
            self.assertEqual(journal.stat().st_mtime_ns, before.st_mtime_ns)
            self.assertEqual(sorted(p.name for p in run.iterdir()), ["events.jsonl"])

    def test_followed_observations_replace_view_without_restarting_watcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            journal = run / "events.jsonl"
            journal.write_text(json.dumps({"event": "BAMF_OPERATOR_STATUS_OBSERVED",
                                           "receipt": receipt()}) + "\n")
            updated = receipt()
            updated["observations"]["active_concepts"] = 5
            def append(_seconds):
                with journal.open("a") as log:
                    log.write(json.dumps({"event": "BAMF_OPERATOR_STATUS_OBSERVED",
                                          "receipt": updated}) + "\n")
            view = watch(run, stream=io.StringIO(), wait=append, max_polls=1,
                         atlas_details=True)
            self.assertEqual(dict(view.bamf_operator_view.observations)["active_concepts"], 5)
            self.assertTrue(view.atlas_expanded)
