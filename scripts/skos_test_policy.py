#!/usr/bin/env python3
"""Content-addressed and differential verification policy for the Ithkuil/SKOS bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

if __package__:
    from .quality.skos_test_bundle import (
        BUNDLE_PATHS,
        IGNORED_NAMES,
        RECEIPT_PATH,
        RECEIPT_SCHEMA,
        BundleStatus,
        _files_under,
        bundle_files,
        bundle_fingerprint,
        bundle_status,
        write_receipt,
    )
    from .quality.skos_test_selection import (
        CANARY_TESTS,
        CROSS_CUTTING_SKOS_MODULES,
        POLICY_SENSITIVE_PATHS,
        TestPlan,
        _direct_owner,
        _fixture_owners,
        _is_bundle_path,
        classify_changes,
    )
else:  # Direct CLI execution from scripts/.
    from quality.skos_test_bundle import (
        BUNDLE_PATHS,
        IGNORED_NAMES,
        RECEIPT_PATH,
        RECEIPT_SCHEMA,
        BundleStatus,
        _files_under,
        bundle_files,
        bundle_fingerprint,
        bundle_status,
        write_receipt,
    )
    from quality.skos_test_selection import (
        CANARY_TESTS,
        CROSS_CUTTING_SKOS_MODULES,
        POLICY_SENSITIVE_PATHS,
        TestPlan,
        _direct_owner,
        _fixture_owners,
        _is_bundle_path,
        classify_changes,
    )


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
        return subprocess.run(runner, cwd=root, check=False).returncode
    return subprocess.run([
        sys.executable, "-B", "-m", "unittest", "discover",
        "-s", "lib/ithkuil/tests", "-p", "test_skos_*.py", "-v",
    ], cwd=root, check=False).returncode


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


__all__ = (
    "BUNDLE_PATHS", "BundleStatus", "CANARY_TESTS", "CROSS_CUTTING_SKOS_MODULES",
    "IGNORED_NAMES", "POLICY_SENSITIVE_PATHS", "RECEIPT_PATH", "RECEIPT_SCHEMA",
    "TestPlan", "bundle_files", "bundle_fingerprint", "bundle_status",
    "changed_paths", "classify_changes", "main", "plan", "write_receipt",
)


if __name__ == "__main__":
    raise SystemExit(main())
