"""Legacy checkpoint metadata remains importable without the optional MLX backend."""
from pathlib import Path
import subprocess
import sys
import unittest


class CheckpointImportTests(unittest.TestCase):
    def test_cold_checkpoint_import_never_loads_mlx(self):
        script = '''
import importlib.abc
import sys

class NoMlx(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'mlx' or fullname.startswith('mlx.'):
            raise ModuleNotFoundError('MLX import forbidden for checkpoint metadata')
        return None

sys.meta_path.insert(0, NoMlx())
sys.path.insert(0, sys.argv[1])
from bilqis_mlx.runtime import checkpoints
assert callable(checkpoints._bundle_pointer)
assert not any(name == 'mlx' or name.startswith('mlx.') for name in sys.modules)
print('COLD_CHECKPOINT_IMPORT_OK')
'''
        result = subprocess.run(
            [sys.executable, '-I', '-B', '-c', script, str(Path(__file__).resolve().parents[4])],
            text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'COLD_CHECKPOINT_IMPORT_OK')
