"""Human root commands must not accidentally begin optimization."""
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import signal
import tempfile
import unittest
from bilqis_mlx import cli
from bilqis_mlx.cli import main


class OperatorTests(unittest.TestCase):
    def test_human_sigint_guard_raises_once_then_ignores_duplicate_cleanup_signal(self):
        previous = signal.getsignal(signal.SIGINT)
        with cli._human_sigint_guard():
            handler = signal.getsignal(signal.SIGINT)
            with self.assertRaises(KeyboardInterrupt):
                handler(signal.SIGINT, None)
            handler(signal.SIGINT, None)
        self.assertEqual(signal.getsignal(signal.SIGINT), previous)

    def test_no_retention_cannot_target_default_run_or_protected_history(self):
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(main(["train", "--dry-run", "--no-retention"]), 2)
        self.assertIn("NO_RETENTION_REQUIRES_INDEPENDENT_RUN_DIR", errors.getvalue())
        with tempfile.TemporaryDirectory() as tmp:
            saved={"learning_experiment":{"version":"existing-protected-policy"}}
            path=Path(tmp)/"state.json"
            original=json.dumps(saved).encode()
            path.write_bytes(original)
            with redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(main(["train", "--dry-run", "--resume",
                                       "--no-retention", "--run-dir", tmp]), 2)
            self.assertIn("LEARNING_EXPERIMENT_RESUME_REQUIRES_IDENTICAL_OPT_IN",
                          errors.getvalue())
            self.assertEqual(path.read_bytes(),original)
