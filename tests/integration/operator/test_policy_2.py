"""Policy operator contracts preserve the human-run boundary."""
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bilqis_mlx.cli import main
from bilqis_mlx.presentation.dashboard import build


class PolicyTests(unittest.TestCase):
    def test_resume_terminal_clears_previous_session_stop_before_training(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True

        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            event = {"event": "SCHOOL_SESSION_STOPPED", "grade": "B",
                     "stop_reason": "TIME_LIMIT_REACHED", "generation": 6809,
                     "optimizer_step": 203880, "visits_this_command": 1599,
                     "elapsed_seconds": 5409.7}
            original = json.dumps(event) + "\n"
            (run / "events.jsonl").write_text(original)
            old_view = build(run, stream=io.StringIO())
            self.assertEqual(old_view.state["stop"], "TIME_LIMIT_REACHED")

            terminal = Terminal()
            with patch("bilqis_mlx.cli.sys.stdout", terminal), patch(
                    'bilqis_mlx.runtime.operating_loop.operate',
                    side_effect=ValueError("DISPOSABLE_TEST_NO_NEURAL_TRAINING")), \
                    redirect_stderr(io.StringIO()):
                result = main(["train", "--human-run", "--resume",
                               "--minutes", "90", "--run-dir", tmp])
            self.assertEqual(result, 2)  # Stub prevents any training call.
            self.assertIn("RUNTIME", terminal.getvalue())
            self.assertIn("MAX TIME", terminal.getvalue())
            self.assertNotIn("TIME_LIMIT_REACHED", terminal.getvalue())
            self.assertEqual((run / "events.jsonl").read_text(), original)
            # Historical dashboard continues to report the actual old stop.
            self.assertEqual(build(run, stream=io.StringIO()).state["stop"],
                             "TIME_LIMIT_REACHED")
