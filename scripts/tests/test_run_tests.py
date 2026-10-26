import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


def _runner_module():
    path = Path(__file__).parents[1] / "run_tests.py"
    spec = importlib.util.spec_from_file_location("bilqis_run_tests", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RunTestsTests(unittest.TestCase):
    def test_repository_root_precedes_script_local_helper_names(self):
        runner = _runner_module()
        name = "runner_root_precedence_fixture"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            scripts = root / "scripts"
            scripts.mkdir()
            (root / (name + ".py")).write_text("VALUE = 'root'\n")
            (scripts / (name + ".py")).write_text("VALUE = 'shadow'\n")
            test = root / "runner_precedence_test.py"
            test.write_text(
                f"from {name} import VALUE\nimport unittest\n"
                "class RootTest(unittest.TestCase):\n"
                "    def test_source(self): self.assertEqual(VALUE, 'root')\n")
            for targets in ((str(test),), (test.stem,)):
                with self.subTest(targets=targets), patch.object(
                        sys, "path", [str(scripts), str(root), *sys.path]):
                    try:
                        suite = runner._load_targets(targets, root)
                        result = unittest.TestResult()
                        suite.run(result)
                        self.assertEqual(result.testsRun, 1)
                        self.assertFalse(result.errors)
                        self.assertFalse(result.failures)
                    finally:
                        sys.modules.pop(name, None)
                        sys.modules.pop(test.stem, None)

    def test_source_only_geometry_shim_is_fail_closed_and_temporary(self):
        runner = _runner_module()
        sys.modules.pop("bilqis_logic.geometry", None)
        with patch.object(runner.importlib.util, "find_spec", return_value=None):
            self.assertTrue(runner._install_source_only_legacy_geometry_shim())
        module = sys.modules["bilqis_logic.geometry"]
        with self.assertRaisesRegex(
                RuntimeError, "SOURCE_ONLY_TEST_NEURAL_GEOMETRY_FORBIDDEN"):
            module.tensor_hash("not-a-tensor")
        sys.modules.pop("bilqis_logic.geometry", None)

    def test_discovers_each_test_directory_without_basename_collisions(self):
        runner = _runner_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = (
                root / "tests" / "test_shared.py",
                root / "bilqis_mlx" / "factory" / "tests" / "test_shared.py",
                root / "scripts" / "tests" / "test_runner.py",
                root / "other" / "tests" / "test_future.py",
            )
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("import unittest\n\nclass Example(unittest.TestCase):\n    def test_ok(self): pass\n")
            (root / "other" / "not_a_test.py").write_text("")
            for ignored in (root / "vendor" / "tests" / "test_vendor.py",
                            root / "runs" / "tests" / "test_run.py",
                            root / ".local" / "source-archive" / "tests" / "test_old.py"):
                ignored.parent.mkdir(parents=True)
                ignored.write_text("")

            paths = tuple(sorted(paths))
            self.assertEqual(runner.discover_test_files(root), paths)
            suite = runner.load_test_files(paths, root)
            result = unittest.TestResult()
            suite.run(result)
            self.assertEqual(result.testsRun, 4)
            self.assertFalse(result.errors)
            self.assertFalse(result.failures)

    def test_empty_discovery_fails_closed_with_totals(self):
        runner = _runner_module()
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            exit_code = runner.main([], root=Path(temporary), stream=output)

        self.assertEqual(exit_code, 2)
        self.assertIn("TEST_TOTALS total=0 passed=0 failed=0 skipped=0", output.getvalue())
        self.assertIn("0 passed, 0 failed, 0 skipped", output.getvalue())

    def test_default_discovery_can_exclude_verified_ithkuil_suite(self):
        runner = _runner_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            normal = root / "tests" / "test_normal.py"
            skos = root / "lib" / "ithkuil" / "tests" / "test_skos_big.py"
            for path in (normal, skos):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "import unittest\nclass Example(unittest.TestCase):\n"
                    "    def test_ok(self): pass\n")
            discovered = runner.discover_test_files(root)
            filtered = runner.exclude_ithkuil_tests(discovered, root)
            self.assertEqual(filtered, (normal,))

    def test_directory_target_loads_all_tests_below_that_directory(self):
        runner = _runner_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tests = root / "lib" / "ithkuil" / "tests"
            for name in ("test_one.py", "test_two.py"):
                path = tests / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "import unittest\nclass Example(unittest.TestCase):\n"
                    "    def test_ok(self): pass\n")
            suite = runner._load_targets((str(tests),), root)
            result = unittest.TestResult()
            suite.run(result)
            self.assertEqual(result.testsRun, 2)
            self.assertFalse(result.errors)
            self.assertFalse(result.failures)

    def test_import_errors_are_reported_by_unittest(self):
        runner = _runner_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "tests" / "test_broken.py"
            path.parent.mkdir()
            path.write_text("raise RuntimeError('broken fixture')\n")
            output = io.StringIO()
            exit_code = runner.main([], root=root, stream=output)

        self.assertEqual(exit_code, 1)
        self.assertIn("RuntimeError: broken fixture", output.getvalue())
        self.assertIn("TEST_TOTALS total=1 passed=0 failed=1 skipped=0 errors=1", output.getvalue())
        self.assertIn("0 passed, 1 failed, 0 skipped", output.getvalue())

    def test_imported_test_case_is_not_duplicated_but_local_subclass_is_loaded(self):
        runner = _runner_module()
        package = "runner_fixture_suite"
        original_path = sys.path[:]
        original_modules = {
            name: module for name, module in sys.modules.items()
            if name == package or name.startswith(f"{package}.")
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tests = root / package / "tests"
            tests.mkdir(parents=True)
            (root / package / "__init__.py").write_text("")
            (tests / "__init__.py").write_text("")
            provider = tests / "test_provider.py"
            provider.write_text(
                "import unittest\n\nclass Provider(unittest.TestCase):\n"
                "    def test_provider(self): pass\n")
            consumer = tests / "test_consumer.py"
            consumer.write_text(
                f"from {package}.tests.test_provider import Provider\n\nclass Local(Provider):\n"
                "    def test_local(self): pass\n")
            try:
                paths = runner.discover_test_files(root)
                suite = runner.load_test_files(paths, root)
                result = unittest.TestResult()
                suite.run(result)
            finally:
                sys.path[:] = original_path
                for name in tuple(sys.modules):
                    if name == package or name.startswith(f"{package}."):
                        del sys.modules[name]
                sys.modules.update(original_modules)

        self.assertEqual(result.testsRun, 3)
        self.assertFalse(result.errors)
        self.assertFalse(result.failures)


if __name__ == "__main__":
    unittest.main()
