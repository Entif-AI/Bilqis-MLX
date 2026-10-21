#!/usr/bin/env python3
"""Run every repository test file without relying on package discovery."""

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest


IGNORED_DIRECTORIES = frozenset({
    ".git", ".venv", "__pycache__", "node_modules", "runs", "vendor", "venv",
})


def _install_source_only_legacy_geometry_shim() -> bool:
    """Keep symbolic source tests portable without changing admitted generator bytes."""
    name = "bilqis_logic.geometry"
    if name in sys.modules:
        return False
    try:
        torch_available = importlib.util.find_spec("torch") is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        torch_available = False
    if torch_available:
        return False
    module = types.ModuleType(name)

    def tensor_hash(*_args, **_kwargs):
        raise RuntimeError("SOURCE_ONLY_TEST_NEURAL_GEOMETRY_FORBIDDEN")

    module.tensor_hash = tensor_hash
    sys.modules[name] = module
    return True


class _LoadFailure(unittest.TestCase):
    def __init__(self, path: Path, error: Exception, traceback) -> None:
        super().__init__("runTest")
        self._path = path
        self._error = error
        self._traceback = traceback

    def runTest(self) -> None:
        raise self._error.with_traceback(self._traceback)

    def __str__(self) -> str:
        return f"load test module {self._path}"


def discover_test_files(root: Path) -> tuple[Path, ...]:
    """Return test files held in any repository test directory."""
    files = []
    for directory, children, names in os.walk(root):
        children[:] = sorted(child for child in children if child not in IGNORED_DIRECTORIES)
        path = Path(directory)
        if "tests" in path.relative_to(root).parts:
            files.extend(path / name for name in names if name.startswith("test_") and name.endswith(".py"))
    return tuple(sorted(files))


def _module_name(path: Path, root: Path) -> str:
    digest = hashlib.sha256(str(path.relative_to(root)).encode()).hexdigest()
    return f"_bilqis_test_{digest}"


def _local_test_suite(suite: unittest.TestSuite, module_name: str) -> unittest.TestSuite:
    local = unittest.TestSuite()
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            local.addTests(_local_test_suite(test, module_name))
        elif test.__class__.__module__ == module_name:
            local.addTest(test)
    return local


def load_test_files(paths: tuple[Path, ...], root: Path) -> unittest.TestSuite:
    """Load files under unique names so duplicate test basenames remain distinct."""
    suite = unittest.TestSuite()
    root_string = str(root)
    sys.path[:] = [root_string, *(entry for entry in sys.path if entry != root_string)]
    for path in paths:
        name = _module_name(path, root)
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load test module: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as error:
            suite.addTest(_LoadFailure(path, error, error.__traceback__))
            del sys.modules[name]
            continue
        suite.addTests(_local_test_suite(
            unittest.defaultTestLoader.loadTestsFromModule(module), name))
    return suite


def _load_targets(targets: tuple[str, ...], root: Path) -> unittest.TestSuite:
    paths = tuple(Path(target).resolve() for target in targets if target.endswith(".py"))
    suite = load_test_files(paths, root)
    for target in targets:
        if not target.endswith(".py"):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromName(target))
    return suite


def _print_totals(result: unittest.TestResult, stream) -> None:
    failed = len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses)
    skipped = len(result.skipped)
    passed = result.testsRun - failed - skipped
    print(
        f"TEST_TOTALS total={result.testsRun} passed={passed} failed={failed} "
        f"skipped={skipped} errors={len(result.errors)}",
        file=stream,
    )
    print(f"{passed} passed, {failed} failed, {skipped} skipped", file=stream)


def main(argv: list[str] | None = None, *, root: Path | None = None, stream=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", help="test file paths or dotted unittest names")
    arguments = parser.parse_args(argv)
    root = root or Path(__file__).resolve().parents[1]
    stream = stream or sys.stdout
    shimmed = _install_source_only_legacy_geometry_shim()
    try:
        suite = (_load_targets(tuple(arguments.targets), root)
                 if arguments.targets else
                 load_test_files(discover_test_files(root), root))
        if suite.countTestCases() == 0:
            print("TEST_TOTALS total=0 passed=0 failed=0 skipped=0 errors=0", file=stream)
            print("0 passed, 0 failed, 0 skipped", file=stream)
            return 2
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        _print_totals(result, stream)
        return 0 if result.wasSuccessful() else 1
    finally:
        if shimmed:
            sys.modules.pop("bilqis_logic.geometry", None)


if __name__ == "__main__":
    raise SystemExit(main())
