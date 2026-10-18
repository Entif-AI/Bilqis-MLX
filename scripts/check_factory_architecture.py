"""Fail-closed architecture checks for SPEC-0001 curriculum-factory invariants.

This checker is intentionally structural. It does not prove pedagogy. It makes
the previously common escape hatches mechanically expensive: future grade
runtime forks, grade-letter dispatch inside generic factory code, and live
training/admission paths that fail to bind a FactoryRelease.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
FUTURE_GRADE_FILE = re.compile(r"^(?:live_grade_|grade_)([d-z])(?:_trainer)?\.py$", re.I)
GENERIC_RUNTIME = (
    "bilqis_mlx/factory",
    "bilqis_mlx/live_curriculum.py",
)
GRADE_LITERAL = frozenset(chr(value) for value in range(ord("A"), ord("Z") + 1))


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_calls(path: Path, function_name: str) -> frozenset[str]:
    tree = ast.parse(_source(path), filename=str(path))
    function = next((node for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name == function_name), None)
    if function is None:
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
        if not isinstance(node, (ast.If, ast.IfExp, ast.Match, ast.While)):
            continue
        values = {item.value for item in ast.walk(node)
                  if isinstance(item, ast.Constant) and isinstance(item.value, str)}
        used = sorted(values & GRADE_LITERAL)
        if used:
            problems.append(
                f"{path.relative_to(root)}:{node.lineno} "
                f"GENERIC_GRADE_IDENTITY_DISPATCH {','.join(used)}")
    return tuple(problems)


def inspect_factory_architecture(root: Path) -> tuple[str, ...]:
    src = root / "bilqis_mlx"
    problems: list[str] = []
    if not (src / "factory").is_dir():
        return ("FACTORY_PACKAGE_MISSING",)

    # A/B/C remain compatibility/provider modules during migration. There is no
    # permission to repeat the pattern for D or any later grade.
    for path in sorted(src.glob("*.py")):
        match = FUTURE_GRADE_FILE.match(path.name)
        if match:
            problems.append(
                f"{path.relative_to(root)} FUTURE_GRADE_RUNTIME_FORK:{match.group(1).upper()}")

    for relative in GENERIC_RUNTIME:
        path = root / relative
        paths = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for candidate in paths:
            if candidate.name.startswith("test_") or not candidate.is_file():
                continue
            problems.extend(_grade_literal_dispatch(candidate, root))

    trainer = src / "trainer.py"
    operate_calls = _function_calls(trainer, "operate")
    if "_require_factory_admission" not in operate_calls:
        problems.append("bilqis_mlx/trainer.py OPERATE_BYPASSES_FACTORY_RELEASE")
    b_calls = _function_calls(trainer, "_activate_next_admitted_grade")
    if "_factory_admission" not in b_calls:
        problems.append("bilqis_mlx/trainer.py B_ADMISSION_BYPASSES_FACTORY_RELEASE")

    legacy = src / "grade_a_trainer.py"
    if legacy.is_file():
        tree = ast.parse(_source(legacy), filename=str(legacy))
        if any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
               for node in tree.body):
            problems.append("bilqis_mlx/grade_a_trainer.py LEGACY_RUNTIME_OWNS_BEHAVIOR")

    transition = src / "grade_transition.py"
    if "_factory_admission" not in _function_calls(transition, "activate_numeric_grade"):
        problems.append("bilqis_mlx/grade_transition.py C_ADMISSION_BYPASSES_FACTORY_RELEASE")
    staircase = src / "numeric_staircase.py"
    if "_factory_admission" not in _function_calls(staircase, "_rebind"):
        problems.append("bilqis_mlx/numeric_staircase.py SCOPE_RELEASE_BYPASSES_FACTORY_RELEASE")

    # Research/prototype packages cannot become dependencies of the canonical
    # released runtime. Keep this generic even before such a package exists.
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(src)
        if relative.parts and relative.parts[0] in {"research", "compatibility"}:
            continue
        tree = ast.parse(_source(path), filename=str(path))
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.ImportFrom):
                target = node.module or ""
            elif isinstance(node, ast.Import):
                for item in node.names:
                    if item.name.startswith("bilqis_mlx.research"):
                        problems.append(
                            f"{path.relative_to(root)}:{node.lineno} RUNTIME_IMPORTS_RESEARCH")
                continue
            if target is not None and (
                    target.startswith("bilqis_mlx.research") or
                    target.startswith(".research")):
                problems.append(
                    f"{path.relative_to(root)}:{node.lineno} RUNTIME_IMPORTS_RESEARCH")
    return tuple(problems)


if __name__ == "__main__":
    issues = inspect_factory_architecture(REPO_ROOT)
    for issue in issues:
        print(issue)
    if issues:
        raise SystemExit(1)
    print("FACTORY_ARCHITECTURE_OK")
