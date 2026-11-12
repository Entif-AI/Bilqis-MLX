#!/usr/bin/env python3
"""Run every repository test file without relying on package discovery."""

import argparse
import ast
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest


IGNORED_DIRECTORIES = frozenset({
    ".git", ".local", ".venv", "__pycache__", "node_modules", "runs", "vendor", "venv",
})
LEAF_GATE_POLICY_NAME = "BILQIS_LEAF_GATE_POLICY"
DETACHED_ONLY_POLICY = "DETACHED_ONLY"


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


def _default_schedulable(path: Path) -> bool:
    """Exclude explicit detached-only witnesses from aggregate discovery."""
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
    except (OSError, SyntaxError):
        return True
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        if any(isinstance(target, ast.Name) and target.id == LEAF_GATE_POLICY_NAME
               for target in targets):
            return value.value != DETACHED_ONLY_POLICY
    return True


def discover_test_files(root: Path) -> tuple[Path, ...]:
    """Return test files held in any repository test directory."""
    files = []
    for directory, children, names in os.walk(root):
        children[:] = sorted(child for child in children if child not in IGNORED_DIRECTORIES)
        path = Path(directory)
        if "tests" in path.relative_to(root).parts:
            files.extend(
                candidate for name in names
                if name.startswith("test_") and name.endswith(".py")
                and _default_schedulable(candidate := path / name)
            )
    return tuple(sorted(files))


def exclude_ithkuil_tests(paths: tuple[Path, ...], root: Path) -> tuple[Path, ...]:
    ithkuil_tests = (root / "lib" / "ithkuil" / "tests").resolve()
    return tuple(path for path in paths
                 if not path.resolve().is_relative_to(ithkuil_tests))


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    digest = hashlib.sha256(str(relative).encode()).hexdigest()
    name = f"_bilqis_test_{digest}"
    package = relative.parent.parts
    if package and all(part.isidentifier() for part in package):
        return ".".join((*package, name))
    return name


def _verify_package_context(name: str, root: Path) -> None:
    """Require native package resolution and cached descendants to stay local."""
    parts = name.split(".")[:-1]
    for index in range(len(parts)):
        package = ".".join(parts[:index + 1])
        expected = root.joinpath(*parts[:index + 1]).resolve()
        spec = importlib.util.find_spec(package)
        locations = None if spec is None else spec.submodule_search_locations
        paths = [] if locations is None else [Path(p).resolve() for p in locations]
        if not paths or paths[0] != expected or any(not p.is_relative_to(root.resolve()) for p in paths):
            raise ImportError(f"unsafe test package context: {package}")
        loaded = importlib.import_module(package)
        actual = [Path(p).resolve() for p in getattr(loaded, "__path__", ())]
        if not actual or actual[0] != expected or any(not p.is_relative_to(root.resolve()) for p in actual):
            raise ImportError(f"unsafe loaded test package context: {package}")
    if not parts:
        return
    parent = ".".join(parts)
    for key, module in tuple(sys.modules.items()):
        if not key.startswith(parent + "."):
            continue
        spec = getattr(module, "__spec__", None)
        locations = None if spec is None else spec.submodule_search_locations
        origin = None if spec is None else spec.origin
        sources = list(locations) if locations is not None else ([origin] if origin else [])
        if not sources or any(
            not any(Path(p).resolve().is_relative_to(location) for location in actual)
            for p in sources
        ):
            raise ImportError(f"unsafe cached test package member: {key}")


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
        try:
            _verify_package_context(name, root)
            existing = sys.modules.get(name)
            if existing is not None and Path(getattr(existing, "__file__", "")).resolve() != path.resolve():
                raise ImportError(f"unsafe existing test module: {name}")
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load test module: {path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                if sys.modules.get(name) is module:
                    if existing is None:
                        del sys.modules[name]
                    else:
                        sys.modules[name] = existing
                raise
        except Exception as error:
            suite.addTest(_LoadFailure(path, error, error.__traceback__))
            continue
        suite.addTests(_local_test_suite(
            unittest.defaultTestLoader.loadTestsFromModule(module), name))
    return suite


def _load_targets(targets: tuple[str, ...], root: Path) -> unittest.TestSuite:
    root = root.resolve()
    paths = []
    names = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            paths.extend(
                candidate for candidate in path.resolve().rglob("test_*.py")
                if candidate.is_file()
                and not any(part in IGNORED_DIRECTORIES
                            for part in candidate.relative_to(path.resolve()).parts)
            )
        elif target.endswith(".py"):
            paths.append(path.resolve())
        else:
            names.append(target)
    paths = tuple(sorted(set(paths)))
    suite = load_test_files(paths, root)
    for target in names:
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
        if arguments.targets:
            suite = _load_targets(tuple(arguments.targets), root)
        else:
            paths = discover_test_files(root)
            try:
                from scripts.skos_test_policy import plan
                skos = plan(root)
            except Exception as error:
                print(f"SKOS_TEST_POLICY_UNAVAILABLE {type(error).__name__}: {error}",
                      file=stream)
            else:
                if skos.action == "SKIP":
                    paths = exclude_ithkuil_tests(paths, root)
                    print(
                        f"SKOS_VERIFIED_BUNDLE_UNCHANGED {skos.sha256} "
                        "FULL_SUITE_SKIPPED",
                        file=stream)
                else:
                    print(f"SKOS_TEST_PLAN {skos.action} {skos.reason}", file=stream)
            suite = load_test_files(paths, root)
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
