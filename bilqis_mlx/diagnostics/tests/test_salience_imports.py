"""Fresh native import order must not depend on a warmed diagnostics module."""
from pathlib import Path
import subprocess
import sys
import unittest


class SalienceImportTests(unittest.TestCase):
    def test_fresh_native_teacher_and_operating_loop_import_without_neural_execution(self):
        root = Path(__file__).resolve().parents[3]
        for module in ('bilqis_mlx.learning.learning_experiment', 'bilqis_mlx.runtime.operating_loop'):
            with self.subTest(module=module):
                result = subprocess.run([sys.executable, '-B', '-c', 'import ' + module], cwd=root,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
