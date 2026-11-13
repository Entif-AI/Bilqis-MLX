"""Git-diff planning, exhaustive sharding, and receipt maintenance."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from .bundle import (
    DEFAULT_FULL_SHARD_COUNT,
    RECEIPT_PATH,
    RECEIPT_SCHEMA,
    TestPlan,
    bundle_fingerprint,
    bundle_status,
    is_bundle_path,
    semantic_test_files,
)
from .impact import classify_changes


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


def plan_for_changes(
    root: Path, changed: tuple[str, ...], *, force_full: bool = False,
) -> TestPlan:
    status = bundle_status(root)
    if force_full:
        return TestPlan("FULL", reason="FORCED_EXHAUSTIVE", sha256=status.sha256)
    classification = classify_changes(root, changed)
    if classification.action == "SKIP":
        return TestPlan("SKIP", reason=classification.reason, sha256=status.sha256)
    bundle_changed = any(is_bundle_path(path) for path in changed)
    receipt_changed = str(RECEIPT_PATH) in changed
    if (bundle_changed or receipt_changed) and not status.verified:
        return TestPlan(
            "ERROR",
            reason=f"SEMANTIC_RECEIPT_NOT_CURRENT:{status.reason}",
            sha256=status.sha256,
        )
    return TestPlan(
        classification.action,
        classification.tests,
        classification.reason,
        status.sha256,
    )


def plan(
    root: Path, *, base_ref: str | None = None, force_full: bool = False,
) -> TestPlan:
    changed = changed_paths(root, base_ref)
    if base_ref and not changed:
        try:
            _git_lines(root, "rev-parse", "--verify", base_ref)
        except RuntimeError:
            status = bundle_status(root)
            return TestPlan("FULL", reason="BASE_REF_UNAVAILABLE", sha256=status.sha256)
    return plan_for_changes(root, changed, force_full=force_full)


def full_test_shards(root: Path, shard_count: int) -> tuple[tuple[str, ...], ...]:
    if shard_count < 1:
        raise ValueError("shard_count must be at least 1")
    tests = semantic_test_files(root)
    buckets: list[list[str]] = [[] for _ in range(shard_count)]
    weights = [0 for _ in range(shard_count)]
    weighted = sorted(
        [((root / test).stat().st_size, test) for test in tests],
        key=lambda item: (-item[0], item[1]),
    )
    for size, test in weighted:
        shard = min(range(shard_count), key=lambda index: (weights[index], index))
        buckets[shard].append(test)
        weights[shard] += size
    return tuple(tuple(sorted(bucket)) for bucket in buckets)


def shard_manifest(root: Path, shard_count: int) -> tuple[dict, ...]:
    return tuple({
        "index": index,
        "tests": list(tests),
        "test_count": len(tests),
        "source_bytes": sum((root / test).stat().st_size for test in tests),
    } for index, tests in enumerate(full_test_shards(root, shard_count)))


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
