import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.testing import pytest_gate_runner


class PytestGateRunnerTests(unittest.TestCase):
    def test_pin_repository_tests_prefers_requested_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "tests"
            package.mkdir()
            (package / "__init__.py").write_text("MARKER = 'local'\n")
            previous = sys.modules.pop("tests", None)
            try:
                pytest_gate_runner._pin_repository_tests(root)
                import tests
                self.assertEqual(Path(tests.__file__).resolve(), (package / "__init__.py").resolve())
                self.assertEqual(tests.MARKER, "local")
            finally:
                sys.modules.pop("tests", None)
                if previous is not None:
                    sys.modules["tests"] = previous

    def test_pin_repository_tests_rejects_preloaded_foreign_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "tests"
            package.mkdir()
            (package / "__init__.py").write_text("")
            foreign = type(sys)("tests")
            foreign.__file__ = "/tmp/foreign-tests/__init__.py"
            with patch.dict(sys.modules, {"tests": foreign}):
                with self.assertRaisesRegex(ImportError, "unsafe pytest test package context"):
                    pytest_gate_runner._pin_repository_tests(root)


if __name__ == "__main__":
    unittest.main()
