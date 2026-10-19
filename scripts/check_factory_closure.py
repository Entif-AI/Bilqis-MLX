"""Detect split curriculum authority outside the compiled factory boundary.

SPEC-0001 requires curriculum meaning and executable scope to flow through one
factory artifact. This checker looks for the common ways a second handwritten
runtime ontology can reappear: concrete release dispatch, capability/grade
identity in generic control flow, and direct imports of concrete curriculum
providers from generic runtime modules.

It intentionally reports current migration debt. The final cutover gate should
assert that this script prints FACTORY_CLOSURE_OK.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERIC_ROOTS = (
    "bilqis_mlx/factory",
    "bilqis_mlx/runtime",
    "bilqis_mlx/curriculum",
    "bilqis_mlx/presentation",
    "bilqis_mlx/learning",
    "bilqis_mlx/live_curriculum.py",
    "bilqis_mlx/trainer.py",
    "bilqis_mlx/cli.py",
)
EXCLUDED_PARTS = frozenset({"tests", "compatibility", "research"})
CONCRETE_PROVIDER = re.compile(
    r"(?:^|\.)(?:live_grade_[a-z]|grade_[a-z]_release|grade_transition|"
    r"boolean_composite|boolean_identification|minimal_grade_b|numeric_staircase)$",
    re.I,
)
CAPABILITY_ID = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9_~-]*$")
GRADE_ID = re.compile(r"^[A-Z]$")
GRADE_EVENT = re.compile(r"(?:^|_)GRADE_[A-Z](?:_|$)")
RELEASE_NAME = re.compile(r"(?:^|_)(?:RELEASE|RELEASES)$")


def _generic_files(root: Path):
    src = root / "bilqis_mlx"
    files = []
    for relative in GENERIC_ROOTS:
        path = root / relative
        candidates = path.rglob("*.py") if path.is_dir() else (path,)
        for candidate in candidates:
            if not candidate.is_file():
                continue
            parts = candidate.relative_to(src).parts if src in candidate.parents else ()
            if set(parts) & EXCLUDED_PARTS:
                continue
            files.append(candidate)
    return tuple(sorted(set(files)))


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return ".".join(relative.parts)


def _import_target(node, current: str) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(item.name for item in node.names)
    if not isinstance(node, ast.ImportFrom):
        return ()
    if node.level:
        parent = current.split(".")[:-1]
        base = parent[:max(0, len(parent) - node.level + 1)]
        suffix = (node.module or "").split(".") if node.module else []
        return (".".join((*base, *suffix)),)
    return (node.module or "",)


def _decision_nodes(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            yield node, node.test
        elif isinstance(node, ast.Match):
            yield node, node


def _strings(node) -> set[str]:
    return {item.value for item in ast.walk(node)
            if isinstance(item, ast.Constant) and isinstance(item.value, str)}


def _names(node) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def inspect_factory_closure(root: Path) -> tuple[str, ...]:
    root = Path(root)
    problems = []
    for path in _generic_files(root):
        relative = path.relative_to(root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            problems.append(f"{relative}:{exc.lineno or 0} FACTORY_CLOSURE_SYNTAX_ERROR")
            continue
        current = _module_name(path, root)

        # Concrete source-domain implementations belong behind provider/compat
        # boundaries. Generic runtime importing them owns curriculum knowledge.
        if not str(relative).startswith("bilqis_mlx/source_adapters/"):
            for node in ast.walk(tree):
                for target in _import_target(node, current):
                    if CONCRETE_PROVIDER.search(target):
                        problems.append(
                            f"{relative}:{node.lineno} GENERIC_IMPORTS_CONCRETE_PROVIDER:{target}")

        # Track imported/assigned names that represent concrete release identity.
        release_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    local = alias.asname or alias.name
                    if RELEASE_NAME.search(local):
                        release_names.add(local)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and RELEASE_NAME.search(target.id):
                        release_names.add(target.id)

        for node, decision in _decision_nodes(tree):
            names = _names(decision)
            release_hits = sorted(names & release_names)
            if release_hits:
                problems.append(
                    f"{relative}:{node.lineno} GENERIC_RELEASE_IDENTITY_DISPATCH:"
                    + ",".join(release_hits))
            strings = _strings(decision)
            capability_hits = sorted(value for value in strings if CAPABILITY_ID.fullmatch(value))
            if capability_hits:
                problems.append(
                    f"{relative}:{node.lineno} GENERIC_CAPABILITY_IDENTITY_DISPATCH:"
                    + ",".join(capability_hits))
            grade_hits = sorted(value for value in strings if GRADE_ID.fullmatch(value))
            if grade_hits:
                problems.append(
                    f"{relative}:{node.lineno} GENERIC_GRADE_IDENTITY_DISPATCH:"
                    + ",".join(grade_hits))

        # Capability literals outside a provider/declaration boundary are a
        # synchronized roster waiting to happen even when hidden behind a bool.
        if str(relative).startswith((
                "bilqis_mlx/curriculum/", "bilqis_mlx/trainer.py",
                "bilqis_mlx/cli.py", "bilqis_mlx/learning/")):
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and \
                        CAPABILITY_ID.fullmatch(node.value):
                    problems.append(
                        f"{relative}:{node.lineno} GENERIC_CAPABILITY_LITERAL:{node.value}")

        # Canonical events should carry grade as data, not encode an A/B/C class.
        if str(relative).startswith(("bilqis_mlx/trainer.py", "bilqis_mlx/presentation/")):
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and \
                        GRADE_EVENT.search(node.value):
                    problems.append(
                        f"{relative}:{node.lineno} GRADE_SPECIFIC_EVENT_CLASS:{node.value}")

    return tuple(sorted(set(problems)))


def main(argv=None) -> int:
    root = Path(argv[0]).resolve() if argv else REPO_ROOT
    issues = inspect_factory_closure(root)
    for issue in issues:
        print(issue)
    if issues:
        print(f"FACTORY_CLOSURE_DEBT={len(issues)}")
        return 1
    print("FACTORY_CLOSURE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
