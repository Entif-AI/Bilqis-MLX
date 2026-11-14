"""The verification policy preserves no-MLX imports and bounds native imports."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class MemoryPolicyTests(unittest.TestCase):
    def test_policy_is_lazy_and_applies_before_native_work(self):
        env = {**os.environ, "BILQIS_GUI05_BOUNDED_TEST": "1",
               "PYTHONPATH": str(Path(__file__).parent)}
        source = ("import sys; assert 'mlx.core' not in sys.modules; "
                  "import mlx.core as mx; "
                  "assert mx.get_memory_limit() == 1024**3; "
                  "assert mx.set_cache_limit(0) == 0")
        result = subprocess.run([sys.executable, "-B", "-c", source], env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
