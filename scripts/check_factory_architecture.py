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
FUTURE_GRADE_FILE = re.compile(r"^(?:live_grade_|grade_)([d-z])(?:_(?:trainer|evaluator|admission|dashboard))?\.py$", re.I)
GENERIC_RUNTIME = (
    "bilqis_mlx/factory",
    "bilqis_mlx/runtime",
    "bilqis_mlx/curriculum",
    "bilqis_mlx/presentation",
    "bilqis_mlx/live_curriculum.py",
    "bilqis_mlx/trainer.py",
    "bilqis_mlx/cli.py",
)
GRADE_LITERAL = frozenset(chr(value) for value in range(ord("A"), ord("Z") + 1))


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
        if used:
            problems.append(
                f"{path.relative_to(root)}:{node.lineno} "
                f"GENERIC_GRADE_IDENTITY_DISPATCH {','.join(used)}")
    return tuple(problems)


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


def inspect_factory_architecture(root: Path) -> tuple[str, ...]:
    src = root / "bilqis_mlx"
    problems: list[str] = []
    if not (src / "factory").is_dir():
        return ("FACTORY_PACKAGE_MISSING",)

    # A/B/C remain compatibility/provider modules during migration. There is no
    # permission to repeat the pattern for D or any later grade.
    for path in sorted(src.rglob("*.py")):
        if "tests" in path.relative_to(src).parts:
            continue
        if path.name not in {"trainer.py", "cli.py"}:
            for node in ast.walk(ast.parse(_source(path))):
                imports_trainer = (
                    isinstance(node, ast.Import) and
                    any(alias.name == "bilqis_mlx.trainer" for alias in node.names) or
                    isinstance(node, ast.ImportFrom) and (
                        (node.module or "").split(".")[-1] == "trainer" or
                        any(alias.name == "trainer" for alias in node.names)))
                if imports_trainer:
                    problems.append(f"{path.relative_to(root)} LEAF_IMPORTS_TRAINER")
        if set(path.relative_to(src).parts) & {"compatibility", "research"}:
            continue
        match = FUTURE_GRADE_FILE.match(path.name)
        if match:
            problems.append(
                f"{path.relative_to(root)} FUTURE_GRADE_RUNTIME_FORK:{match.group(1).upper()}")

    for relative in GENERIC_RUNTIME:
        path = root / relative
        paths = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for candidate in paths:
            if "tests" in candidate.relative_to(src).parts or not candidate.is_file():
                continue
            problems.extend(_grade_literal_dispatch(candidate, root))
            problems.extend(_legacy_course_usage(candidate, root))

    trainer = src / "trainer.py"
    operate_calls = _function_calls(trainer, "operate")
    if not operate_calls & {
            "_require_executable_factory_admission",
            "_ensure_executable_release"}:
        problems.append("bilqis_mlx/trainer.py OPERATE_BYPASSES_FACTORY_RELEASE")
    b_calls = _function_calls(trainer, "_adopt_executable_profile")
    if not b_calls & {
            "_require_executable_factory_admission",
            "_executable_factory_admission"}:
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

    problems.extend(_research_imports(src, root))
    return tuple(problems)


def _research_imports(src, root):
    problems = []
    # Research/prototype packages cannot become dependencies of the canonical
    # released runtime. Keep this generic even before such a package exists.
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(src)
        if set(relative.parts) & {"research", "compatibility", "tests"}:
            continue
        tree = ast.parse(_source(path), filename=str(path))
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.ImportFrom):
                module = ("bilqis_mlx", *relative.with_suffix("").parts)
                target = ".".join((*module[:-node.level], *(node.module or "").split("."))) if node.level else node.module or ""
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
    return problems


if __name__ == "__main__":
    issues = inspect_factory_architecture(REPO_ROOT)
    for issue in issues:
        print(issue)
    if issues:
        raise SystemExit(1)
    print("FACTORY_ARCHITECTURE_OK")
