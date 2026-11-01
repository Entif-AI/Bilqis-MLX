"""AST rules shared by the curriculum factory architecture checker."""
from __future__ import annotations

import ast
from pathlib import Path
import re

FUTURE_GRADE_FILE = re.compile(r"^(?:live_grade_|grade_)([d-z])(?:_(?:trainer|evaluator|admission|dashboard))?\.py$", re.I)
GENERIC_RUNTIME = (
    "bilqis_mlx/factory",
    "bilqis_mlx/runtime",
    "bilqis_mlx/curriculum",
    "bilqis_mlx/presentation",
    "bilqis_mlx/live_curriculum.py",
    "bilqis_mlx/_release_views/live_curriculum.py",
    "bilqis_mlx/trainer.py",
    "bilqis_mlx/cli.py",
)
GRADE_LITERAL = frozenset(chr(value) for value in range(ord("A"), ord("Z") + 1))
CURRENT_WRITERS = frozenset({
    "bilqis_mlx.runtime.admission._factory_admission",
    "bilqis_mlx.runtime.admission._executable_factory_admission",
    "bilqis_mlx.runtime.checkpoints._advance",
    "bilqis_mlx.runtime.checkpoints._persist",
    "bilqis_mlx.runtime.checkpoints._reconcile_delivery_outbox",
    "bilqis_mlx.runtime.release_adoption._adopt_executable_profile",
    "bilqis_mlx.runtime.release_adoption._adopt_catalog_profile",
})


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_calls(path: Path, function_name: str, seen=frozenset()) -> frozenset[str]:
    key = (path, function_name)
    if key in seen or not path.is_file():
        return frozenset()
    tree = ast.parse(_source(path), filename=str(path))
    function = next((node for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name == function_name), None)
    if function is None:
        # Follow the facade statically: importing code would execute the runtime.
        root = next((parent for parent in path.parents if parent.name == "bilqis_mlx"), None)
        for statement in tree.body:
            if not isinstance(statement, ast.ImportFrom) or not statement.module:
                continue
            for alias in statement.names:
                if (alias.asname or alias.name) != function_name:
                    continue
                if root is None or not statement.module.startswith("bilqis_mlx."):
                    return frozenset()
                owner = root.parent.joinpath(*statement.module.split(".")).with_suffix(".py")
                return _function_calls(owner, alias.name, seen | {key})
        return frozenset()
    names = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return frozenset(names)


def _grade_literal_dispatch(path: Path, root: Path) -> tuple[str, ...]:
    """Find grade identity in generic control decisions, not data declarations."""
    problems = []
    tree = ast.parse(_source(path), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            decision = node.test
        elif isinstance(node, ast.Match):
            decision = ast.Tuple(elts=[case.pattern for case in node.cases])
        else:
            continue
        values = {item.value for item in ast.walk(decision)
                  if isinstance(item, ast.Constant) and isinstance(item.value, str)}
        used = sorted(values & GRADE_LITERAL)
        if used and _is_adapter_factor_suffix_decision(decision):
            continue
        if used:
            problems.append(
                f"{path.relative_to(root)}:{node.lineno} "
                f"GENERIC_GRADE_IDENTITY_DISPATCH {','.join(used)}")
    return tuple(problems)


def _is_adapter_factor_suffix_decision(decision: ast.AST) -> bool:
    """Recognize BAMF adapter matrix factor names without treating them as grades.

    The topology schema has long used ``plastic.group.<id>.A`` and ``.B`` as the
    two matrix-factor wire suffixes.  They are parameter names, not curriculum
    identities.  Keep this exception structural and narrow so ordinary grade
    comparisons such as ``grade == 'B'`` remain forbidden.
    """
    has_plastic_prefix = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "startswith"
        and any(isinstance(arg, ast.Constant) and arg.value == "plastic.group."
                for arg in node.args)
        for node in ast.walk(decision)
    )
    has_factor_membership = any(
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "suffix"
        and any(isinstance(op, ast.In) for op in node.ops)
        and any(
            isinstance(comp, (ast.Tuple, ast.List, ast.Set))
            and {item.value for item in comp.elts
                 if isinstance(item, ast.Constant)} == {"A", "B"}
            for comp in node.comparators
        )
        for node in ast.walk(decision)
    )
    return has_plastic_prefix and has_factor_membership


def _legacy_course_usage(path: Path, root: Path) -> tuple[str, ...]:
    tree = ast.parse(_source(path), filename=str(path))
    lines = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.arg) and node.arg == "legacy_course" or
                isinstance(node, ast.Name) and node.id == "legacy_course" or
                isinstance(node, ast.keyword) and node.arg == "legacy_course" or
                isinstance(node, ast.Attribute) and node.attr == "legacy_course"):
            lines.add(node.lineno)
    return tuple(f"{path.relative_to(root)}:{line} CURRENT_API_USES_LEGACY_COURSE"
                 for line in sorted(lines))


def _import_from_module(node: ast.ImportFrom, path: Path, src: Path) -> str:
    module = node.module or ""
    if node.level:
        package = ("bilqis_mlx", *path.relative_to(src).parts[:-1])
        if node.level > len(package):
            return ""
        parent = package[:len(package) - node.level + 1]
        module = ".".join((*parent, *module.split("."))) if module else ".".join(parent)
    return module


def _imports_trainer_facade(node: ast.AST, path: Path, src: Path) -> bool:
    facade = "bilqis_mlx.trainer"
    if isinstance(node, ast.Import):
        return any(alias.name == facade for alias in node.names)
    if not isinstance(node, ast.ImportFrom):
        return False
    module = _import_from_module(node, path, src)
    return module == facade or (
        module == "bilqis_mlx" and any(alias.name == "trainer" for alias in node.names))


def _compatibility_writer_calls(tree: ast.AST, path: Path, src: Path) -> tuple[str, ...]:
    bindings = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                bindings[name] = alias.name if alias.asname else name
        elif isinstance(node, ast.ImportFrom):
            module = _import_from_module(node, path, src)
            for alias in node.names:
                if alias.name == "*":
                    bindings.update({target.rsplit(".", 1)[1]: target
                                     for target in CURRENT_WRITERS
                                     if target.rsplit(".", 1)[0] == module})
                else:
                    bindings[alias.asname or alias.name] = f"{module}.{alias.name}"
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        suffix = []
        while isinstance(target, ast.Attribute):
            suffix.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            name = ".".join((bindings.get(target.id, target.id), *reversed(suffix)))
            if name in CURRENT_WRITERS:
                problems.append(f"{path.relative_to(src.parent)}:{node.lineno} "
                                f"COMPATIBILITY_CALLS_CURRENT_WRITER:{name}")
    return tuple(problems)


