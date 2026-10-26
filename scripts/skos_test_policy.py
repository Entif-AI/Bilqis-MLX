#!/usr/bin/env python3
"""Content-addressed and differential verification policy for the Ithkuil/SKOS bundle."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys


RECEIPT_SCHEMA = "bilqis.skos-test-bundle/v1"
RECEIPT_PATH = Path("docs/evidence/development/skos_test_bundle_v1.json")

BUNDLE_PATHS = (
    Path("lib/ithkuil/src"),
    Path("lib/ithkuil/_data"),
    Path("lib/ithkuil/tests"),
    Path("lib/ithkuil/ingestion_contract.json"),
    Path("lib/ithkuil/requirements-extraction.txt"),
    Path("lib/ithkuil/requirements-falkor.txt"),
    Path("lib/ithkuil/requirements-semantic.txt"),
    Path("scripts/package_ithkuil_skill.py"),
    Path("scripts/run_tests.py"),
    Path("scripts/skos_test_policy.py"),
    Path("scripts/tests/test_run_tests.py"),
    Path("scripts/tests/test_skos_test_policy.py"),
    Path("skills/ithkuil-ingestion"),
)

CANARY_TESTS = (
    "lib/ithkuil/tests/test_skos_canonical.py",
    "lib/ithkuil/tests/test_skos_identity.py",
    "lib/ithkuil/tests/test_skos_shapes.py",
)

POLICY_SENSITIVE_PATHS = frozenset({
    str(RECEIPT_PATH),
    "scripts/skos_test_policy.py",
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

IGNORED_NAMES = frozenset({"__pycache__", ".DS_Store"})


@dataclass(frozen=True)
class BundleStatus:
    verified: bool
    sha256: str
    expected_sha256: str | None
    file_count: int
    byte_count: int
    reason: str


@dataclass(frozen=True)
class TestPlan:
    action: str
    tests: tuple[str, ...] = ()
    reason: str = ""
    sha256: str | None = None


def _files_under(root: Path, relative: Path) -> tuple[Path, ...]:
    path = root / relative
    if not path.exists():
        return ()
    if path.is_file():
        return (path,)
    return tuple(sorted(
        candidate for candidate in path.rglob("*")
        if candidate.is_file()
        and not any(part in IGNORED_NAMES for part in candidate.relative_to(root).parts)
        and candidate.suffix != ".pyc"
    ))


def bundle_files(root: Path) -> tuple[Path, ...]:
    files = []
    for relative in BUNDLE_PATHS:
        files.extend(_files_under(root, relative))
    return tuple(sorted(set(files)))


def bundle_fingerprint(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    files = bundle_files(root)
    byte_count = 0
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        byte_count += len(payload)
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(len(payload)).encode("ascii"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest(), len(files), byte_count


def bundle_status(root: Path, receipt_path: Path | None = None) -> BundleStatus:
    receipt_path = receipt_path or root / RECEIPT_PATH
    actual, file_count, byte_count = bundle_fingerprint(root)
    if not receipt_path.exists():
        return BundleStatus(False, actual, None, file_count, byte_count, "RECEIPT_MISSING")
    try:
        receipt = json.loads(receipt_path.read_text())
    except (OSError, json.JSONDecodeError):
        return BundleStatus(False, actual, None, file_count, byte_count, "RECEIPT_INVALID")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        return BundleStatus(
            False, actual, receipt.get("sha256"), file_count, byte_count,
            "RECEIPT_SCHEMA_MISMATCH")
    expected = receipt.get("sha256")
    verified = expected == actual
    return BundleStatus(
        verified, actual, expected, file_count, byte_count,
        "VERIFIED_BUNDLE_UNCHANGED" if verified else "BUNDLE_DIGEST_CHANGED")


def _is_bundle_path(path: str) -> bool:
    return (
        path.startswith("lib/ithkuil/")
        or path.startswith("skills/ithkuil-ingestion/")
        or path in {"scripts/package_ithkuil_skill.py", "scripts/run_tests.py",
                    "scripts/skos_test_policy.py"}
    )


def _fixture_owners(root: Path, changed: str) -> tuple[str, ...]:
    fixture = Path(changed)
    needles = {
        fixture.name,
        fixture.relative_to("lib/ithkuil/tests").as_posix()
        if changed.startswith("lib/ithkuil/tests/") else fixture.name,
    }
    owners = []
    for test in sorted((root / "lib/ithkuil/tests").glob("test_*.py")):
        text = test.read_text(errors="replace")
        if any(needle in text for needle in needles):
            owners.append(test.relative_to(root).as_posix())
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
        if changed.startswith("lib/ithkuil/tests/test_") and path.suffix == ".py":
            selected.add(changed)
            continue
        return TestPlan("FULL", reason=f"UNCLASSIFIED_SKOS_CHANGE:{changed}")

    if needs_canaries:
        selected.update(test for test in CANARY_TESTS if (root / test).exists())
    return TestPlan("DIFF", tuple(sorted(selected)), "OWNED_DIFFERENTIAL_TESTS")


def _git_lines(root: Path, *args: str) -> tuple[str, ...]:
    proc = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return tuple(line.strip() for line in proc.stdout.splitlines() if line.strip())


def changed_paths(root: Path, base_ref: str | None) -> tuple[str, ...]:
    paths = set()
    if base_ref:
        try:
            paths.update(_git_lines(root, "diff", "--name-only", base_ref, "HEAD"))
        except RuntimeError:
            return ()
    try:
        paths.update(_git_lines(root, "diff", "--name-only"))
        paths.update(_git_lines(root, "diff", "--cached", "--name-only"))
        paths.update(_git_lines(root, "ls-files", "--others", "--exclude-standard"))
    except RuntimeError:
        return ()
    return tuple(sorted(paths))


def plan(root: Path, *, base_ref: str | None = None) -> TestPlan:
    changed = changed_paths(root, base_ref)
    if base_ref and not changed:
        try:
            _git_lines(root, "rev-parse", "--verify", base_ref)
        except RuntimeError:
            return TestPlan("FULL", reason="BASE_REF_UNAVAILABLE")
    classification = classify_changes(root, changed)
    if classification.action == "FULL":
        return classification
    status = bundle_status(root)
    if status.verified:
        return TestPlan(
            "SKIP", reason="VERIFIED_BUNDLE_UNCHANGED", sha256=status.sha256)
    if classification.action == "DIFF":
        return TestPlan(
            "DIFF", classification.tests, classification.reason, status.sha256)
    return TestPlan("FULL", reason=status.reason, sha256=status.sha256)


def write_receipt(root: Path, *, release_commit: str, evidence: str) -> dict:
    digest, file_count, byte_count = bundle_fingerprint(root)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "sha256": digest,
        "file_count": file_count,
        "byte_count": byte_count,
        "release_commit": release_commit,
        "evidence": evidence,
    }
    path = root / RECEIPT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt


def _emit(plan_value: TestPlan, *, github_output: Path | None = None) -> None:
    sha = plan_value.sha256 or ""
    if plan_value.action == "SKIP" and sha:
        print(f"SKOS_VERIFIED_BUNDLE_UNCHANGED {sha} FULL_SUITE_SKIPPED")
    else:
        print(
            f"SKOS_TEST_PLAN {plan_value.action} {plan_value.reason}"
            + (f" {sha}" if sha else ""))
    if plan_value.tests:
        print("SKOS_TESTS " + " ".join(plan_value.tests))
    if github_output is not None:
        with github_output.open("a") as stream:
            stream.write(f"action={plan_value.action}\n")
            stream.write(f"sha256={sha}\n")
            stream.write(f"reason={plan_value.reason}\n")


def _run_plan(root: Path, plan_value: TestPlan) -> int:
    if plan_value.action == "SKIP":
        _emit(plan_value)
        return 0
    runner = [sys.executable, "-B", "scripts/run_tests.py"]
    if plan_value.action == "DIFF":
        runner.extend(plan_value.tests)
    else:
        runner.append("lib/ithkuil/tests")
    return subprocess.run(runner, cwd=root, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "plan", "run"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--base-ref")
        if command == "plan":
            sub.add_argument("--github-output", type=Path)
    write = subparsers.add_parser("write-receipt")
    write.add_argument("--release-commit", required=True)
    write.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]

    if args.command == "write-receipt":
        print(json.dumps(write_receipt(
            root, release_commit=args.release_commit, evidence=args.evidence),
            sort_keys=True))
        return 0
    if args.command == "status":
        status = bundle_status(root)
        print(json.dumps(status.__dict__, sort_keys=True))
        return 0 if status.verified else 1
    plan_value = plan(root, base_ref=args.base_ref or None)
    if args.command == "plan":
        _emit(plan_value, github_output=args.github_output)
        return 0
    return _run_plan(root, plan_value)


if __name__ == "__main__":
    raise SystemExit(main())
