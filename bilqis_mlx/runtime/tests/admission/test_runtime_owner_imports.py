"""Admission owners retain one discoverable runtime module identity."""
import importlib
from pkgutil import iter_modules
import subprocess
import sys
import unittest

import bilqis_mlx.runtime as runtime


class RuntimeOwnerImportsTests(unittest.TestCase):
    def test_established_imports_and_discovery(self):
        available = {item.name for item in iter_modules(runtime.__path__)}
        for name in ('atlas_admission_policy', 'atlas_debt', 'jit_adoption',
                     'frontier_refresh', 'autonomy_loop', 'autonomy_state'):
            with self.subTest(name=name):
                self.assertIn(name, available)
                self.assertEqual(importlib.import_module('bilqis_mlx.runtime.' + name).__name__,
                                 'bilqis_mlx.runtime.' + name)

    def test_physical_directory_does_not_supply_alternate_module_names(self):
        probe = '''
import importlib, sys
import bilqis_mlx.factory, bilqis_mlx.semantics
sys.modules["bilqis_mlx.runtime.factory"] = bilqis_mlx.factory
sys.modules["bilqis_mlx.runtime.semantics"] = bilqis_mlx.semantics
for name in ("atlas_admission_policy", "atlas_debt", "jit_adoption", "frontier_refresh", "autonomy_loop", "autonomy_state"):
    alternate = "bilqis_mlx.runtime._admission." + name
    try:
        importlib.import_module(alternate)
    except ModuleNotFoundError as error:
        assert error.name == alternate, (alternate, error.name)
    else:
        raise AssertionError("alternate module identity loaded: " + alternate)
'''
        completed = subprocess.run([sys.executable, '-B', '-c', probe], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
