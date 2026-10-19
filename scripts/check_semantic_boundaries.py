"""Rerunnable import/status-ownership audit for the Bilqis semantic engine.

Usage: python3 -B scripts/check_semantic_boundaries.py
Run in CI/tests when reorganizing semantic, adapter, or verifier packages.
"""
from __future__ import annotations

import ast
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bilqis_mlx.verification.outcomes import CoverageStatus, LawCheckStatus, ProofStatus


OWNERS = frozenset({"semantics", "source_adapters", "verification"})
PERMITTED = {
    "semantics": frozenset({"semantics"}),
    "source_adapters": frozenset({"source_adapters", "semantics"}),
    "verification": frozenset({"verification", "semantics"}),
}
STATUS_STRINGS = frozenset(
    item.value for result_type in (ProofStatus, CoverageStatus, LawCheckStatus)
    for item in result_type
)
SHADOW_MODULES = frozenset({"health_shadow", "candidate_shadow"})


def _imports_shadow_policy(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(entry.name.startswith("bilqis_mlx.diagnostics." + name)
                   for entry in node.names for name in SHADOW_MODULES)
    if isinstance(node, ast.ImportFrom):
        parts = (node.module or "").split(".")
        if "diagnostics" in parts:
            tail = parts[parts.index("diagnostics") + 1:]
            return (bool(tail) and tail[0] in SHADOW_MODULES or
                    not tail and any(entry.name in SHADOW_MODULES for entry in node.names))
    return False


def inspect_semantic_boundaries(root: Path) -> tuple[str, ...]:
    """Report dependency/status-ownership violations without changing files."""
    src = root / "bilqis_mlx"
    problems = []
    if not all((src / name).is_dir() for name in OWNERS):
        return ("MISSING_SEMANTIC_DOMAIN_PACKAGE",)
    for owner in sorted(OWNERS):
        for path in sorted((src / owner).rglob("*.py")):
            if "tests" in path.relative_to(src).parts:
                continue
            module = ("bilqis_mlx", *path.relative_to(src).with_suffix("").parts)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    targets = (entry.name for entry in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        resolved = module[:-node.level]
                        targets = (".".join((*resolved, *(node.module or "").split("."))).rstrip("."),)
                    else:
                        targets = (node.module or "",)
                else:
                    targets = ()
                for target in targets:
                    parts = target.split(".")
                    if len(parts) > 1 and parts[0] == "bilqis_mlx":
                        if parts[1] in OWNERS and parts[1] not in PERMITTED[owner]:
                            problems.append(f"{path.relative_to(root)}:{node.lineno} IMPORT_BOUNDARY {target}")
                if (isinstance(node, ast.Constant) and isinstance(node.value, str) and
                        node.value in STATUS_STRINGS and path.name != "outcomes.py"):
                    problems.append(f"{path.relative_to(root)}:{node.lineno} RAW_RESULT_STATUS {node.value}")
    for path in sorted((src / "composition").rglob("*.py")) if (src / "composition").exists() else ():
        problems.append(f"{path.relative_to(root)} OBSOLETE_COMPOSITION_MODULE")
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(src)
        if relative.parts[0] == "diagnostics" and path.name != "__init__.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if _imports_shadow_policy(node):
                problems.append(f"{path.relative_to(root)}:{node.lineno} UNAPPROVED_SHADOW_POLICY_IMPORT")
    return tuple(problems)


if __name__ == "__main__":
    issues = inspect_semantic_boundaries(REPO_ROOT)
    for issue in issues:
        print(issue)
    if issues:
        raise SystemExit(1)
    print("SEMANTIC_BOUNDARIES_OK")
