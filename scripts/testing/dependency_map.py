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


def _owner_roots(root: Path) -> tuple[tuple[Path, str], ...]:
    """Return package search-path extensions declared through ``_OWNER_GROUPS``."""
    owners: list[tuple[Path, str]] = []
    for package_init in _python_files(root):
        if package_init.name != "__init__.py":
            continue
        try:
            tree = ast.parse(package_init.read_text(errors="ignore"))
        except (OSError, SyntaxError):
            continue
        groups: tuple[str, ...] = ()
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "_OWNER_GROUPS"
                       for target in node.targets):
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            if isinstance(value, (tuple, list)) and all(isinstance(item, str) for item in value):
                groups = tuple(value)
        if not groups:
            continue
        package_module = _module_name(root, package_init)
        owners.extend(
            ((package_init.parent / group).resolve(), package_module)
            for group in groups
        )
    return tuple(owners)


def _module_aliases(root: Path, path: Path, owners: tuple[tuple[Path, str], ...]) -> tuple[str, ...]:
    aliases = {_module_name(root, path)}
    resolved = path.resolve()
    for owner_root, package_module in owners:
        if resolved != owner_root and owner_root not in resolved.parents:
            continue
        relative = resolved.relative_to(owner_root).with_suffix("")
        parts = relative.parts[:-1] if relative.parts and relative.parts[-1] == "__init__" else relative.parts
        aliases.add(".".join((package_module, *parts)))
    return tuple(sorted(alias for alias in aliases if alias))


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
    owners = _owner_roots(root)
    modules: dict[str, Path] = {}
    for path in files:
        for module in _module_aliases(root, path, owners):
            modules.setdefault(module, path)
    reverse: dict[Path, set[Path]] = defaultdict(set)
    for importer in files:
        for import_name in _imports(importer, _module_name(root, importer)):
            dependency = _resolve(import_name, modules)
            if dependency is not None and dependency != importer:
                reverse[dependency].add(importer)

    result: dict[Path, tuple[Path, ...]] = {}
    for relative in changed:
        start = root / relative
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
