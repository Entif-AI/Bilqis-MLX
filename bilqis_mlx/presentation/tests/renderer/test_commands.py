"""The historical module entry point works in a fresh interpreter."""
from pathlib import Path
import subprocess
import sys
import unittest


class CommandTests(unittest.TestCase):
    def test_module_help_does_not_reenter_a_partially_initialized_facade(self):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "bilqis_mlx.presentation.spiral_dashboard", "--help"],
            cwd=Path(__file__).resolve().parents[4], capture_output=True, text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("{train,watch}", result.stdout)
        self.assertNotIn("Traceback", result.stderr)
