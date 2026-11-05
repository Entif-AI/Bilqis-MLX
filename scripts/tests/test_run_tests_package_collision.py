"""Reject package contexts that would resolve test helpers from another root."""
import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts.tests.test_run_tests import _runner_module


class RunnerPackageCollisionTests(unittest.TestCase):
    def test_foreign_cached_parent_is_reported_without_replacing_it(self):
        self._collision('parent')

    def test_foreign_installed_package_is_reported_without_replacing_it(self):
        self._collision('installed')

    def test_foreign_cached_helper_is_reported_without_replacing_it(self):
        self._collision('helper')

    def test_local_extended_path_helper_remains_valid_across_files(self):
        runner = _runner_module()
        package = 'runner_local_extended_path'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            native = root / package
            secondary = root / 'alt' / package
            native.mkdir()
            secondary.mkdir(parents=True)
            (secondary / 'fixtures.py').write_text("VALUE = 'secondary'\n")
            paths = []
            for suffix in ('first', 'second'):
                path = native / f'test_{suffix}.py'
                path.write_text(
                    'from .fixtures import VALUE\nimport unittest\n'
                    "class Example(unittest.TestCase):\n"
                    "    def test_value(self): self.assertEqual(VALUE, 'secondary')\n")
                paths.append(path)
            try:
                with patch.object(sys, 'path', [str(root / 'alt'), *sys.path]):
                    result = unittest.TestResult()
                    runner.load_test_files(tuple(paths), root).run(result)
                self.assertEqual(result.testsRun, 2)
                self.assertFalse(result.errors)
                self.assertFalse(result.failures)
            finally:
                for name in tuple(sys.modules):
                    if name == package or name.startswith(package + '.'):
                        del sys.modules[name]

    def test_foreign_synthetic_module_is_not_replaced(self):
        runner = _runner_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            path = root / 'test_case.py'
            path.write_text('raise AssertionError("must not execute")\n')
            name = runner._module_name(path, root)
            retained = types.ModuleType(name)
            retained.__file__ = str(root / 'other.py')
            sys.modules[name] = retained
            try:
                with patch.object(sys, 'path', sys.path[:]):
                    result = unittest.TestResult()
                    runner.load_test_files((path,), root).run(result)
                self.assertEqual(len(result.errors), 1)
                self.assertIn('unsafe existing test module', result.errors[0][1])
                self.assertIs(sys.modules[name], retained)
            finally:
                sys.modules.pop(name, None)

    def _collision(self, kind):
        runner = _runner_module()
        package = 'runner_collision_' + kind
        with tempfile.TemporaryDirectory() as local, tempfile.TemporaryDirectory() as foreign:
            root = Path(local).resolve()
            other = Path(foreign).resolve()
            local_package = root / package
            local_package.mkdir()
            if kind != 'installed':
                (local_package / '__init__.py').write_text('')
            (local_package / 'fixtures.py').write_text("VALUE = 'local'\n")
            test = local_package / 'test_case.py'
            test.write_text(
                'from .fixtures import VALUE\nimport unittest\n'
                "class Example(unittest.TestCase):\n    def test_value(self): self.assertEqual(VALUE, 'local')\n")
            foreign_package = other / package
            foreign_package.mkdir()
            (foreign_package / '__init__.py').write_text('')
            (foreign_package / 'fixtures.py').write_text("VALUE = 'foreign'\n")
            try:
                with patch.object(sys, 'path', [str(other), *sys.path]):
                    if kind == 'parent':
                        retained = importlib.import_module(package)
                    elif kind == 'helper':
                        sys.path.insert(0, str(root))
                        importlib.import_module(package)
                        spec = importlib.util.spec_from_file_location(
                            package + '.fixtures', foreign_package / 'fixtures.py')
                        retained = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(retained)
                        sys.modules[package + '.fixtures'] = retained
                    else:
                        retained = None
                    suite = runner.load_test_files((test,), root)
                    result = unittest.TestResult()
                    suite.run(result)
                    self.assertEqual(result.testsRun, 1)
                    self.assertEqual(len(result.errors), 1)
                    self.assertIn('package', result.errors[0][1].lower())
                    if retained is not None:
                        key = package + '.fixtures' if kind == 'helper' else package
                        self.assertIs(sys.modules[key], retained)
            finally:
                for name in tuple(sys.modules):
                    if name == package or name.startswith(package + '.'):
                        del sys.modules[name]
