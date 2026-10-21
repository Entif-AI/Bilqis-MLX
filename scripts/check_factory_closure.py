"""Detect split curriculum authority outside the compiled factory boundary.

This is a structural tripwire, not the decisive conformance proof. The decisive
proof is behavioral: unfamiliar curriculum + profile + providers must execute
through the same runtime without generic source edits. This checker prevents
common ways a second handwritten curriculum ontology can creep back in.
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
PROVIDER_ROOTS = ("bilqis_mlx/source_adapters",)
EXCLUDED_PARTS = frozenset({"tests", "compatibility", "research"})
CONSUMER_PREFIXES = (
    "bilqis_mlx/runtime/",
    "bilqis_mlx/presentation/",
    "bilqis_mlx/learning/",
    "bilqis_mlx/curriculum/scheduler.py",
    "bilqis_mlx/trainer.py",
    "bilqis_mlx/cli.py",
)
CONCRETE_PROVIDER = re.compile(
    r"(?:^|\.)(?:live_grade_[a-z]|grade_[a-z]_release|grade_transition|"
    r"boolean_composite|boolean_identification|minimal_grade_b|numeric_staircase)$",
    re.I,
)
PROFILE_SPECIFIC_PROVIDER = re.compile(
    r"(?:^|\.)(?:minimal|compact|profile)[a-z0-9_.-]*(?:grade|boolean)|"
    r"(?:^|\.)minimal_grade_[a-z]",
    re.I,
)
CAPABILITY_ID = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9_~-]*$")
GRADE_ID = re.compile(r"^[A-Z]$")
GRADE_EVENT = re.compile(r"(?:^|_)GRADE_[A-Z](?:_|$)")
RELEASE_SYMBOL = re.compile(r"(?:^|_)(?:RELEASE|RELEASES)$")
PROFILE_PROVIDER_LITERAL = re.compile(r"(?:minimal|compact|profile)", re.I)


def _files(root: Path, roots):
    src = root / "bilqis_mlx"
    files = []
    for relative in roots:
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


def _generic_files(root: Path):
    return _files(root, GENERIC_ROOTS)


def _provider_files(root: Path):
    return _files(root, PROVIDER_ROOTS)


def _module_name(path: Path, root: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


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


def _is_consumer(relative: Path) -> bool:
    value = str(relative)
    return any(value.startswith(prefix) for prefix in CONSUMER_PREFIXES)


def _release_aliases(tree) -> set[str]:
    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                # Match the authoritative imported symbol, not just its local
                # alias, so `MINIMAL_BOOLEAN_RELEASE as MODE` cannot hide it.
                if RELEASE_SYMBOL.search(alias.name):
                    aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and RELEASE_SYMBOL.search(target.id):
                    aliases.add(target.id)
    return aliases


def _lineage_of_attribute(node: ast.Attribute) -> str:
    parts = [node.attr]
    current = node.value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _parse(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _generic_import_problems(tree, relative: Path, current: str) -> list[str]:
    problems = []
    for node in ast.walk(tree):
        for target in _import_target(node, current):
            if CONCRETE_PROVIDER.search(target):
                problems.append(
                    f"{relative}:{node.lineno} GENERIC_IMPORTS_CONCRETE_PROVIDER:{target}")
    return problems


def _generic_identity_problems(tree, relative: Path) -> list[str]:
    problems = []
    release_aliases = _release_aliases(tree)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name) and node.id in release_aliases and
                not isinstance(getattr(node, "ctx", None), ast.Store)):
            problems.append(
                f"{relative}:{node.lineno} GENERIC_RELEASE_IDENTITY_REFERENCE:{node.id}")
        if (isinstance(node, ast.Constant) and isinstance(node.value, str) and
                CAPABILITY_ID.fullmatch(node.value)):
            problems.append(
                f"{relative}:{node.lineno} GENERIC_CAPABILITY_LITERAL:{node.value}")
    for node, decision in _decision_nodes(tree):
        release_hits = sorted(_names(decision) & release_aliases)
        if release_hits:
            problems.append(
                f"{relative}:{node.lineno} GENERIC_RELEASE_IDENTITY_DISPATCH:" +
                ",".join(release_hits))
        strings = _strings(decision)
        capability_hits = sorted(
            value for value in strings if CAPABILITY_ID.fullmatch(value))
        if capability_hits:
            problems.append(
                f"{relative}:{node.lineno} GENERIC_CAPABILITY_IDENTITY_DISPATCH:" +
                ",".join(capability_hits))
        grade_hits = sorted(value for value in strings if GRADE_ID.fullmatch(value))
        if grade_hits:
            problems.append(
                f"{relative}:{node.lineno} GENERIC_GRADE_IDENTITY_DISPATCH:" +
                ",".join(grade_hits))
    return problems


def _consumer_problems(tree, relative: Path) -> list[str]:
    if not _is_consumer(relative):
        return []
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == "Course" for alias in node.names):
                problems.append(f"{relative}:{node.lineno} GENERIC_RUNTIME_IMPORTS_COURSE")
        if isinstance(node, ast.Attribute) and node.attr in {"grades", "capability_map"}:
            lineage = _lineage_of_attribute(node)
            if "course" in lineage.lower():
                problems.append(
                    f"{relative}:{node.lineno} GENERIC_RUNTIME_RECONSTRUCTS_COURSE:{lineage}")
    return problems


def _grade_event_problems(tree, relative: Path) -> list[str]:
    if not str(relative).startswith((
            "bilqis_mlx/trainer.py", "bilqis_mlx/presentation/")):
        return []
    return [
        f"{relative}:{node.lineno} GRADE_SPECIFIC_EVENT_CLASS:{node.value}"
        for node in ast.walk(tree)
        if (isinstance(node, ast.Constant) and isinstance(node.value, str) and
            GRADE_EVENT.search(node.value))
    ]


def _generic_file_problems(path: Path, root: Path) -> list[str]:
    relative = path.relative_to(root)
    try:
        tree = _parse(path)
    except SyntaxError as exc:
        return [f"{relative}:{exc.lineno or 0} FACTORY_CLOSURE_SYNTAX_ERROR"]
    current = _module_name(path, root)
    return [
        *_generic_import_problems(tree, relative, current),
        *_generic_identity_problems(tree, relative),
        *_consumer_problems(tree, relative),
        *_grade_event_problems(tree, relative),
    ]


def _provider_file_problems(path: Path, root: Path) -> list[str]:
    relative = path.relative_to(root)
    try:
        tree = _parse(path)
    except SyntaxError:
        return []
    current = _module_name(path, root)
    problems = []
    for node in ast.walk(tree):
        for target in _import_target(node, current):
            if PROFILE_SPECIFIC_PROVIDER.search(target):
                problems.append(
                    f"{relative}:{node.lineno} PROFILE_SPECIFIC_PROVIDER_IMPORT:{target}")
        if (isinstance(node, ast.Constant) and isinstance(node.value, str) and
                "source." in node.value and PROFILE_PROVIDER_LITERAL.search(node.value)):
            problems.append(
                f"{relative}:{node.lineno} PROFILE_SPECIFIC_PROVIDER_ID:{node.value}")
    return problems


def inspect_factory_closure(root: Path) -> tuple[str, ...]:
    root = Path(root)
    problems = [
        problem
        for path in _generic_files(root)
        for problem in _generic_file_problems(path, root)
    ]
    problems.extend(
        problem
        for path in _provider_files(root)
        for problem in _provider_file_problems(path, root)
    )
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
