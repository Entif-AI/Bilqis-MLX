"""Resolve Bilqis source through the actual Python package search paths."""
from __future__ import annotations

import ast
import importlib
from importlib.machinery import PathFinder
from pathlib import Path
import sys


def _local(path, root):
    if not Path(path).resolve().is_relative_to(root):
        raise ImportError(f"module origin outside snapshot: {path} (expected {root})")


def _origin(module, root):
    path = getattr(module, "__file__", None)
    if path:
        _local(path, root)
    for search in getattr(module, "__path__", ()):
        _local(search, root)


def _project_modules():
    return ((name, module) for name, module in tuple(sys.modules.items())
            if module is not None
            and (name == "bilqis_mlx" or name.startswith("bilqis_mlx.")))


def validate_loaded(root: Path, required=()):
    """Check every project origin and identities of resolved/probed owners.

    Existing unrelated production alias families are outside the probe's
    authority. A measured binding must never have multiple module identities.
    """
    root = root.resolve()
    origins = {}
    for name, module in _project_modules():
        _origin(module, root)
        path = getattr(module, "__file__", None)
        if path:
            origins.setdefault(Path(path).resolve(), []).append((name, module))
    for module in required:
        if sys.modules.get(module.__name__) is not module:
            raise ImportError(f"module identity replaced: {module.__name__}")
        path = getattr(module, "__file__", None)
        if path:
            aliases = origins.get(Path(path).resolve(), ())
            if any(other is not module for _, other in aliases):
                raise ImportError(
                    f"duplicate module identity for {path}: "
                    + ", ".join(name for name, _ in aliases))


def _existing_identity(name, origin):
    current = sys.modules.get(name)
    for alias, module in _project_modules():
        path = getattr(module, "__file__", None)
        if path and Path(path).resolve() == origin and module is not current:
            raise ImportError(f"duplicate module identity for {origin}: "
                              f"already loaded as {alias}; requested {name}")


def _canonical_hint(name, root):
    physical = root.joinpath(*name.split("."))
    for candidate in (physical.with_suffix(".py"), physical / "__init__.py"):
        if candidate.is_file():
            break
    else:
        return ""
    candidates = []
    for package_name, module in _project_modules():
        for search in getattr(module, "__path__", ()):
            base = Path(search).resolve()
            if not candidate.resolve().is_relative_to(base):
                continue
            relative = candidate.resolve().relative_to(base)
            parts = list(relative.parts)
            if parts and parts[-1] == "__init__.py":
                parts.pop()
            elif parts and parts[-1].endswith(".py"):
                parts[-1] = Path(parts[-1]).stem
            if parts and all(part.isidentifier() for part in parts):
                suggestion = ".".join((package_name, *parts))
                if suggestion != name:
                    candidates.append((len(base.parts), suggestion))
    if candidates:
        return "; canonical import candidate: " + max(candidates)[1]
    return ""


def import_failure_hint(source: bytes, error: ModuleNotFoundError, root: Path):
    """Recover the full requested module from an import whose prefix failed."""
    missing = error.name or ""
    if not missing.startswith("bilqis_mlx"):
        return ""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    hints = {_canonical_hint(name, root) for name in names
             if name == missing or name.startswith(missing + ".")}
    return "".join(sorted(hint for hint in hints if hint))


def resolve_module(name: str, root: Path):
    """Use Python's actual package search path, never a filesystem-name map."""
    root = root.resolve()
    if not name.startswith("bilqis_mlx.") and name != "bilqis_mlx":
        raise ImportError(f"expected a Bilqis module name: {name}")
    if not all(part.isidentifier() for part in name.split(".")):
        raise ImportError(f"invalid module name: {name}")
    parent = None
    try:
        for length in range(1, len(name.split(".")) + 1):
            qualified = ".".join(name.split(".")[:length])
            paths = list(parent.__path__) if parent is not None else sys.path
            specs = [PathFinder.find_spec(qualified, [entry]) for entry in paths]
            origins = {Path(spec.origin).resolve() for spec in specs
                       if spec is not None and spec.origin and spec.has_location}
            if len(origins) > 1:
                raise ImportError(f"ambiguous module {qualified}: {sorted(map(str, origins))}")
            for origin in origins:
                _local(origin, root)
                _existing_identity(qualified, origin)
            parent = importlib.import_module(qualified)
            _origin(parent, root)
    except (ImportError, AttributeError) as error:
        raise ImportError(f"cannot resolve {name}: {error}{_canonical_hint(name, root)}") from error
    validate_loaded(root, (parent,))
    return parent


def resolve_source(source: Path, root: Path):
    """Resolve a relative physical Python source path without guessing its alias."""
    root = root.resolve()
    path = (root / source).resolve()
    _local(path, root)
    if not path.is_file() or path.suffix != ".py":
        raise ImportError(f"expected existing Python source: {path}")
    module = resolve_module("bilqis_mlx", root)
    while True:
        origin = getattr(module, "__file__", None)
        if origin and Path(origin).resolve() == path:
            return module
        bases = [Path(base).resolve() for base in getattr(module, "__path__", ())
                 if path.is_relative_to(Path(base).resolve())]
        if not bases:
            raise ImportError(f"no canonical package path for {path} under {module.__name__}")
        base = max(bases, key=lambda value: len(value.parts))
        relative = path.relative_to(base)
        name = relative.parts[0] if len(relative.parts) > 1 else relative.stem
        module = resolve_module(f"{module.__name__}.{name}", root)
