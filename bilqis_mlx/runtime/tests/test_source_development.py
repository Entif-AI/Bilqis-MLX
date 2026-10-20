from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.source_development import (
    prepare_source_frontier, persist_source_development,
)


class SourceDevelopmentTests(unittest.TestCase):
    def script(self, root):
        path = root / "lib/ithkuil/src/build_lexicon_chapters.py"
        path.parent.mkdir(parents=True)
        path.write_text('print(\'{"status":"TRACKED_SOURCE_QUEUE_EXHAUSTED"}\')\n')
        return path

    def test_source_child_runs_without_learner_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.script(root)
            result = prepare_source_frontier(root)
            self.assertEqual(result["status"], "TRACKED_SOURCE_QUEUE_EXHAUSTED")
            self.assertEqual(len(result["builder_sha256"]), 64)

    def test_timeout_records_deferred_source_work_with_unchanged_learner(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.script(root)
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("extract", 60)):
                result = prepare_source_frontier(root)
            self.assertEqual(result["reason"], "EXTRACTION_TIMEOUT")
            path = persist_source_development(root, result,
                proposal=SimpleNamespace(proposal_sha256="a" * 64),
                checkpoint=SimpleNamespace(sha256="b" * 64, optimizer_step=17))
            import json
            receipt = json.loads(path.read_text())
            self.assertEqual(receipt["actual_neural_updates"], 0)
            self.assertEqual(receipt["optimizer_step"], 17)
            self.assertEqual(receipt["checkpoint_sha256"], "b" * 64)

    def test_source_edit_during_child_execution_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = self.script(root)

            def execute(*args, **kwargs):
                script.write_text("changed\n")
                return subprocess.CompletedProcess(args, 0,
                    '{"status":"TRACKED_SOURCE_QUEUE_EXHAUSTED"}', "")

            with patch("subprocess.run", side_effect=execute):
                with self.assertRaisesRegex(ValueError, "BUILDER_CHANGED_DURING_EXTRACTION"):
                    prepare_source_frontier(root)
