"""Differential SKOS test ownership and fail-closed change classification."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .skos_test_bundle import RECEIPT_PATH


CANARY_TESTS = (
    "lib/ithkuil/tests/skos/core_identity/test_skos_canonical.py",
    "lib/ithkuil/tests/skos/core_identity/test_skos_identity.py",
    "lib/ithkuil/tests/skos/core_identity/test_skos_shapes.py",
)

POLICY_MODULE_PATHS = frozenset({
    "scripts/skos_test_policy.py",
    "scripts/quality/skos_test_bundle.py",
    "scripts/quality/skos_test_selection.py",
})

POLICY_SENSITIVE_PATHS = frozenset({
    str(RECEIPT_PATH),
    *POLICY_MODULE_PATHS,
    "scripts/run_tests.py",
    ".github/workflows/quality.yml",
    "package.json",
})

CROSS_CUTTING_SKOS_MODULES = frozenset({
    "build",
    "builder",
    "canonical",
    "configuration",
    "conformance",
    "corpus",
    "coverage",
    "coverage_domains",
    "determinism",
    "identity",
    "ledger",
    "ledger_model",
    "no_omission",
    "preflight",
    "preflight_io",
    "preflight_manifest",
    "preflight_rules",
    "publication",
    "resolver",
    "shacl",
    "shapes",
    "source",
    "source_public",
    "source_types",
})


@dataclass(frozen=True)
class TestPlan:
    action: str
    tests: tuple[str, ...] = ()
    reason: str = ""
    sha256: str | None = None


def _is_bundle_path(path: str) -> bool:
    return (
        path.startswith("lib/ithkuil/")
        or path.startswith("skills/ithkuil-ingestion/")
        or path in {"scripts/package_ithkuil_skill.py", "scripts/run_tests.py"}
        or path in POLICY_MODULE_PATHS
    )


def _fixture_owners(root: Path, changed: str) -> tuple[str, ...]:
    fixture = Path(changed)
    needles = {
        fixture.name,
        fixture.relative_to("lib/ithkuil/tests").as_posix()
        if changed.startswith("lib/ithkuil/tests/") else fixture.name,
    }
    owners = []
    for test in sorted((root / "lib/ithkuil/tests").rglob("test_*.py")):
        text = test.read_text(errors="replace")
        if any(needle in text for needle in needles):
            owners.append(test.relative_to(root).as_posix())
    return tuple(owners)


def _direct_owner(root: Path, changed: str) -> str | None:
    path = Path(changed)
    test_root = root / "lib/ithkuil/tests"
    if changed.startswith("lib/ithkuil/src/skos/") and path.suffix == ".py":
        matches = tuple(test_root.rglob(f"test_skos_{path.stem}.py"))
        return matches[0].relative_to(root).as_posix() if len(matches) == 1 else None
    if changed.startswith("lib/ithkuil/src/") and path.suffix == ".py":
        matches = tuple(test_root.rglob(f"test_{path.stem}.py"))
        return matches[0].relative_to(root).as_posix() if len(matches) == 1 else None
    return None


def classify_changes(root: Path, changed_paths: tuple[str, ...]) -> TestPlan:
    relevant = tuple(sorted({path for path in changed_paths if _is_bundle_path(path)
                             or path in POLICY_SENSITIVE_PATHS}))
    if not relevant:
        return TestPlan("SKIP", reason="NO_SKOS_BUNDLE_CHANGES")
    if any(path in POLICY_SENSITIVE_PATHS for path in relevant):
        return TestPlan("FULL", reason="TEST_POLICY_OR_RECEIPT_CHANGED")
    if any(path.startswith("lib/ithkuil/_data/") for path in relevant):
        return TestPlan("FULL", reason="CANONICAL_CORPUS_CHANGED")
    if any(path.startswith("skills/ithkuil-ingestion/")
           or path == "scripts/package_ithkuil_skill.py"
           or path in {"lib/ithkuil/ingestion_contract.json",
                       "lib/ithkuil/requirements-extraction.txt",
                       "lib/ithkuil/requirements-falkor.txt",
                       "lib/ithkuil/requirements-semantic.txt"}
           for path in relevant):
        return TestPlan("FULL", reason="INGESTION_OR_PACKAGE_CONTRACT_CHANGED")

    selected = set()
    needs_canaries = False
    for changed in relevant:
        path = Path(changed)
        if changed.startswith("lib/ithkuil/src/skos/"):
            if path.suffix in {".json", ".ttl"}:
                return TestPlan("FULL", reason="SHARED_SKOS_CONFIGURATION_CHANGED")
            if path.stem in CROSS_CUTTING_SKOS_MODULES:
                return TestPlan("FULL", reason=f"CROSS_CUTTING_MODULE_CHANGED:{path.stem}")
            owner = _direct_owner(root, changed)
            if owner is None:
                return TestPlan("FULL", reason=f"UNKNOWN_SKOS_OWNER:{changed}")
            selected.add(owner)
            needs_canaries = True
            continue
        if changed.startswith("lib/ithkuil/src/"):
            owner = _direct_owner(root, changed)
            if owner is None:
                return TestPlan("FULL", reason=f"UNKNOWN_ITHKUIL_OWNER:{changed}")
            selected.add(owner)
            needs_canaries = True
            continue
        if changed.startswith("lib/ithkuil/tests/fixtures/"):
            owners = _fixture_owners(root, changed)
            if not owners:
                return TestPlan("FULL", reason=f"UNOWNED_FIXTURE:{changed}")
            selected.update(owners)
            needs_canaries = True
            continue
        if (changed.startswith("lib/ithkuil/tests/")
                and path.name.startswith("test_") and path.suffix == ".py"):
            selected.add(changed)
            continue
        return TestPlan("FULL", reason=f"UNCLASSIFIED_SKOS_CHANGE:{changed}")

    if needs_canaries:
        selected.update(test for test in CANARY_TESTS if (root / test).exists())
    return TestPlan("DIFF", tuple(sorted(selected)), "OWNED_DIFFERENTIAL_TESTS")
