"""Changed-path impact analysis for differential semantic-profile verification."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from .bundle import CANARY_TESTS, RECEIPT_PATH, TestPlan, is_bundle_path, semantic_test_files


POLICY_SENSITIVE_PATHS = frozenset({
    "scripts/run_tests.py",
    ".github/workflows/quality.yml",
    ".github/workflows/semantic-profile-full.yml",
    "package.json",
})

CROSS_CUTTING_SKOS_MODULES = frozenset({
    "build", "builder", "canonical", "configuration", "conformance",
    "corpus", "coverage", "coverage_domains", "determinism", "identity",
    "ledger", "ledger_model", "no_omission", "preflight", "preflight_io",
    "preflight_manifest", "preflight_rules", "publication", "resolver",
    "shacl", "shapes", "source", "source_public", "source_types",
})


def is_policy_path(path: str) -> bool:
    return (
        path == "scripts/skos_test_policy.py"
        or path.startswith("scripts/skos_policy/")
        or path in POLICY_SENSITIVE_PATHS
    )


def _fixture_owners(root: Path, changed: str) -> tuple[str, ...]:
    fixture = Path(changed)
    needles = {
        fixture.name,
        fixture.relative_to("lib/ithkuil/tests").as_posix()
        if changed.startswith("lib/ithkuil/tests/") else fixture.name,
    }
    owners = []
    for test_path in semantic_test_files(root):
        text = (root / test_path).read_text(errors="replace")
        if any(needle in text for needle in needles):
            owners.append(test_path)
    return tuple(owners)


def _direct_owner(root: Path, changed: str) -> str | None:
    path = Path(changed)
    if changed.startswith("lib/ithkuil/src/skos/") and path.suffix == ".py":
        candidate = root / "lib/ithkuil/tests" / f"test_skos_{path.stem}.py"
        return candidate.relative_to(root).as_posix() if candidate.exists() else None
    if changed.startswith("lib/ithkuil/src/") and path.suffix == ".py":
        candidate = root / "lib/ithkuil/tests" / f"test_{path.stem}.py"
        return candidate.relative_to(root).as_posix() if candidate.exists() else None
    return None


def _module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imported_modules(root: Path, path: Path) -> frozenset[str]:
    try:
        tree = ast.parse(path.read_text(errors="replace"), filename=str(path))
    except (OSError, SyntaxError):
        return frozenset()
    current = _module_name(root, path)
    package = current if path.name == "__init__.py" else current.rpartition(".")[0]
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if node.level:
            relative_name = "." * node.level + module
            try:
                base = importlib.util.resolve_name(relative_name, package)
            except (ImportError, ValueError):
                base = ""
        else:
            base = module
        if base:
            imported.add(base)
        for alias in node.names:
            if alias.name != "*" and base:
                imported.add(f"{base}.{alias.name}")
    return frozenset(imported)


def _impact_import_graph(root: Path) -> dict[str, frozenset[str]]:
    graph: dict[str, frozenset[str]] = {}
    for relative_root in (Path("lib/ithkuil/src"), Path("lib/ithkuil/tests")):
        for path in sorted((root / relative_root).rglob("*.py")):
            graph[_module_name(root, path)] = _imported_modules(root, path)
    return graph


def _depends_on(
    graph: dict[str, frozenset[str]], starts: frozenset[str], target: str,
) -> bool:
    pending = list(starts)
    seen = set()
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        if module == target or module.startswith(target + "."):
            return True
        pending.extend(dep for dep in graph.get(module, ()) if dep not in seen)
    return False


def _transitive_owners(root: Path, changed: str) -> tuple[str, ...]:
    path = root / changed
    if path.suffix != ".py" or not path.exists():
        return ()
    target = _module_name(root, path)
    graph = _impact_import_graph(root)
    return tuple(
        test_path
        for test_path in semantic_test_files(root)
        if _depends_on(graph, _imported_modules(root, root / test_path), target)
    )


def _source_owners(root: Path, changed: str) -> set[str]:
    owners = set(_transitive_owners(root, changed))
    direct = _direct_owner(root, changed)
    if direct:
        owners.add(direct)
    return owners


def classify_changes(root: Path, changed_paths: tuple[str, ...]) -> TestPlan:
    relevant = tuple(sorted({
        path for path in changed_paths
        if is_bundle_path(path) or is_policy_path(path) or path == str(RECEIPT_PATH)
    }))
    if not relevant:
        return TestPlan("SKIP", reason="NO_SEMANTIC_PROFILE_CHANGES")
    if any(is_policy_path(path) for path in relevant):
        return TestPlan("FULL", reason="TEST_POLICY_CHANGED")
    bundle_changes = tuple(path for path in relevant if is_bundle_path(path))
    if not bundle_changes and str(RECEIPT_PATH) in relevant:
        return TestPlan("FULL", reason="RECEIPT_ONLY_CHANGED")
    if any(path.startswith("lib/ithkuil/_data/") for path in bundle_changes):
        return TestPlan("FULL", reason="CANONICAL_CORPUS_CHANGED")
    if any(
        path.startswith("skills/ithkuil-ingestion/")
        or path == "scripts/package_ithkuil_skill.py"
        or path in {
            "lib/ithkuil/ingestion_contract.json",
            "lib/ithkuil/requirements-extraction.txt",
            "lib/ithkuil/requirements-falkor.txt",
            "lib/ithkuil/requirements-semantic.txt",
        }
        for path in bundle_changes
    ):
        return TestPlan("FULL", reason="INGESTION_OR_PACKAGE_CONTRACT_CHANGED")

    selected: set[str] = set()
    needs_canaries = False
    for changed in bundle_changes:
        path = Path(changed)
        if changed.startswith("lib/ithkuil/src/skos/"):
            if path.suffix in {".json", ".ttl"}:
                return TestPlan("FULL", reason="SHARED_SKOS_CONFIGURATION_CHANGED")
            if path.stem in CROSS_CUTTING_SKOS_MODULES:
                return TestPlan("FULL", reason=f"CROSS_CUTTING_MODULE_CHANGED:{path.stem}")
            owners = _source_owners(root, changed)
            if not owners:
                return TestPlan("FULL", reason=f"UNKNOWN_SKOS_OWNER:{changed}")
            selected.update(owners)
            needs_canaries = True
            continue
        if changed.startswith("lib/ithkuil/src/"):
            owners = _source_owners(root, changed)
            if not owners:
                return TestPlan("FULL", reason=f"UNKNOWN_ITHKUIL_OWNER:{changed}")
            selected.update(owners)
            needs_canaries = True
            continue
        if changed.startswith("lib/ithkuil/tests/fixtures/"):
            owners = _fixture_owners(root, changed)
            if not owners:
                return TestPlan("FULL", reason=f"UNOWNED_FIXTURE:{changed}")
            selected.update(owners)
            needs_canaries = True
            continue
        if changed.startswith("lib/ithkuil/tests/test_skos_") and path.suffix == ".py":
            selected.add(changed)
            continue
        if changed.startswith("lib/ithkuil/tests/") and path.suffix == ".py":
            owners = _transitive_owners(root, changed)
            if not owners:
                return TestPlan("FULL", reason=f"UNOWNED_TEST_SUPPORT:{changed}")
            selected.update(owners)
            continue
        return TestPlan("FULL", reason=f"UNCLASSIFIED_SEMANTIC_CHANGE:{changed}")

    if needs_canaries:
        selected.update(test for test in CANARY_TESTS if (root / test).exists())
    return TestPlan("DIFF", tuple(sorted(selected)), "IMPACT_CLOSURE_PLUS_CANARIES")
