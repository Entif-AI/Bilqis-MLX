#!/usr/bin/env python3
"""Content-addressed and differential verification policy for Ithkuil/SKOS."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

try:
    from .skos_policy import (
        BUNDLE_PATHS,
        CANARY_TESTS,
        CROSS_CUTTING_SKOS_MODULES,
        DEFAULT_FULL_SHARD_COUNT,
        RECEIPT_PATH,
        RECEIPT_SCHEMA,
        BundleStatus,
        TestPlan,
        bundle_files,
        bundle_fingerprint,
        bundle_status,
        changed_paths,
        classify_changes,
        full_test_shards,
        is_bundle_path,
        is_policy_path,
        plan,
        plan_for_changes,
        semantic_test_files,
        shard_manifest,
        write_receipt,
    )
except ImportError:  # direct script execution
    from skos_policy import (
        BUNDLE_PATHS,
        CANARY_TESTS,
        CROSS_CUTTING_SKOS_MODULES,
        DEFAULT_FULL_SHARD_COUNT,
        RECEIPT_PATH,
        RECEIPT_SCHEMA,
        BundleStatus,
        TestPlan,
        bundle_files,
        bundle_fingerprint,
        bundle_status,
        changed_paths,
        classify_changes,
        full_test_shards,
        is_bundle_path,
        is_policy_path,
        plan,
        plan_for_changes,
        semantic_test_files,
        shard_manifest,
        write_receipt,
    )


def _emit(plan_value: TestPlan, *, github_output: Path | None = None) -> None:
    sha = plan_value.sha256 or ""
    print(
        f"SKOS_TEST_PLAN {plan_value.action} {plan_value.reason}"
        + (f" {sha}" if sha else ""))
    if plan_value.tests:
        print("SKOS_TESTS " + " ".join(plan_value.tests))
    if plan_value.action == "ERROR":
        print(
            "SKOS_RECEIPT_REFRESH_REQUIRED: run "
            "python3 -B scripts/skos_test_policy.py write-receipt "
            "--release-commit HEAD --evidence '<proof context>'"
        )
    if github_output is not None:
        with github_output.open("a") as stream:
            stream.write(f"action={plan_value.action}\n")
            stream.write(f"sha256={sha}\n")
            stream.write(f"reason={plan_value.reason}\n")


def _run_tests(root: Path, tests: tuple[str, ...]) -> int:
    if not tests:
        return 0
    return subprocess.run(
        [sys.executable, "-B", "scripts/run_tests.py", *tests],
        cwd=root,
        check=False,
    ).returncode


def _run_plan(
    root: Path,
    plan_value: TestPlan,
    *,
    full_shard_index: int | None = None,
    full_shard_count: int = DEFAULT_FULL_SHARD_COUNT,
) -> int:
    if plan_value.action == "ERROR":
        _emit(plan_value)
        return 2
    if plan_value.action == "SKIP":
        _emit(plan_value)
        return 0
    if plan_value.action == "DIFF":
        if full_shard_index is not None:
            print("DIFF_PLAN_DOES_NOT_ACCEPT_FULL_SHARD")
            return 2
        return _run_tests(root, plan_value.tests)
    if full_shard_index is not None:
        shards = full_test_shards(root, full_shard_count)
        if not 0 <= full_shard_index < len(shards):
            print("FULL_SHARD_INDEX_OUT_OF_RANGE")
            return 2
        tests = shards[full_shard_index]
        print(
            f"SKOS_FULL_SHARD {full_shard_index + 1}/{full_shard_count} "
            f"tests={len(tests)}")
        return _run_tests(root, tests)
    return _run_tests(root, semantic_test_files(root))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "plan", "run"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--base-ref")
        sub.add_argument("--force-full", action="store_true")
        if command == "plan":
            sub.add_argument("--github-output", type=Path)
        if command == "run":
            sub.add_argument("--full-shard-index", type=int)
            sub.add_argument(
                "--full-shard-count", type=int, default=DEFAULT_FULL_SHARD_COUNT)
    shards = subparsers.add_parser("shards")
    shards.add_argument("--shard-count", type=int, default=DEFAULT_FULL_SHARD_COUNT)
    write = subparsers.add_parser("write-receipt")
    write.add_argument("--release-commit", required=True)
    write.add_argument("--evidence", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.command == "write-receipt":
        print(json.dumps(write_receipt(
            root, release_commit=args.release_commit, evidence=args.evidence),
            sort_keys=True))
        return 0
    if args.command == "shards":
        print(json.dumps(shard_manifest(
            root, args.shard_count), sort_keys=True, indent=2))
        return 0
    if args.command == "status":
        status = bundle_status(root)
        print(json.dumps(status.__dict__, sort_keys=True))
        return 0 if status.verified else 1
    plan_value = plan(
        root, base_ref=args.base_ref or None, force_full=args.force_full)
    if args.command == "plan":
        _emit(plan_value, github_output=args.github_output)
        return 2 if plan_value.action == "ERROR" else 0
    return _run_plan(
        root,
        plan_value,
        full_shard_index=args.full_shard_index,
        full_shard_count=args.full_shard_count,
    )


if __name__ == "__main__":
    raise SystemExit(main())
