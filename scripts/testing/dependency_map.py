"""Static Python import graph used to bound cold differential test selection."""
from __future__ import annotations

import ast
from collections import defaultdict, deque
from pathlib import Path


IGNORED_PARTS = frozenset({".git", ".local", ".venv", "node_modules", "runs", "vendor"})


def _python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(
        path for path in root.rglob("*.py")
        if path.is_file()
        if not IGNORED_PARTS.intersection(path.relative_to(root).parts)
    ))


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = relative.parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports(path: Path, module_name: str) -> set[str]:
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
    except (OSError, SyntaxError):
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package = module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]
                parts = package.split(".") if package else []
                keep = max(0, len(parts) - (node.level - 1))
                prefix = ".".join(parts[:keep])
                base = ".".join(part for part in (prefix, node.module or "") if part)
            else:
                base = node.module or ""
            if base:
                imports.add(base)
                imports.update(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")
    return imports


def _resolve(import_name: str, modules: dict[str, Path]) -> Path | None:
    candidate = import_name
    while candidate:
        if candidate in modules:
            return modules[candidate]
        candidate = candidate.rpartition(".")[0]
    return None


def affected_test_map(root: Path, changed: tuple[Path, ...]) -> dict[Path, tuple[Path, ...]]:
    """Map each changed module to tests that import it directly or transitively."""
    files = _python_files(root)
    modules = {_module_name(root, path): path for path in files}
    reverse: dict[Path, set[Path]] = defaultdict(set)
    for importer in files:
        for import_name in _imports(importer, _module_name(root, importer)):
            dependency = _resolve(import_name, modules)
            if dependency is not None and dependency != importer:
                reverse[dependency].add(importer)

    result: dict[Path, tuple[Path, ...]] = {}
    for relative in changed:
        start = (root / relative).resolve()
        queue = deque((start,))
        seen = {start}
        tests: set[Path] = set()
        while queue:
            dependency = queue.popleft()
            for importer in reverse.get(dependency, ()):
                if "tests" in importer.relative_to(root).parts and importer.name.startswith("test_"):
                    tests.add(importer)
                if importer not in seen:
                    seen.add(importer)
                    queue.append(importer)
        result[relative] = tuple(sorted(tests))
    return result


def affected_tests(root: Path, changed: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return the union of tests affected by the changed modules."""
    mapped = affected_test_map(root, changed)
    return tuple(sorted({test for tests in mapped.values() for test in tests}))
