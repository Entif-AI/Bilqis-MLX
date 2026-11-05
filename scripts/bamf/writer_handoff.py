#!/usr/bin/env python3
"""Emit and verify local BAMF worktree-continuation evidence.

This is a compaction handoff, NOT a distributed lock or writer lease.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCHEMA = "bilqis.bamf.writer-handoff/v1"


class HandoffError(ValueError):
    pass


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise HandoffError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def observed(root: Path) -> dict[str, str | None]:
    path = Path(git(root, "rev-parse", "--show-toplevel")).resolve()
    branch = git(path, "symbolic-ref", "--quiet", "--short", "HEAD")
    local_sha = git(path, "rev-parse", "HEAD")
    upstream = git(path, "for-each-ref", "--format=%(upstream:short)", f"refs/heads/{branch}") or None
    remote_sha = None
    if upstream is not None:
        remote_sha = git(path, "rev-parse", "@{upstream}")
        remote_name, _, remote_branch = upstream.partition("/")
        remote_lines = git(path, "ls-remote", "--heads", remote_name, f"refs/heads/{remote_branch}")
        if not remote_lines:
            raise HandoffError(f"upstream branch {upstream} missing on remote")
        actual_remote_sha = remote_lines.split()[0]
        if actual_remote_sha != remote_sha:
            raise HandoffError(
                f"remote changed after last fetch: tracked={remote_sha}, live={actual_remote_sha}; fetch and reconcile"
            )
    status = git(path, "status", "--porcelain=v1", "--untracked-files=all")
    diff = subprocess.run(
        ["git", "diff", "HEAD", "--binary"], cwd=path, capture_output=True, check=True
    ).stdout
    dirty = hashlib.sha256(status.encode() + diff)
    untracked = git(path, "ls-files", "--others", "--exclude-standard", "-z")
    # git's text output strips only the final NUL; embedded NULs remain.
    for relative in sorted(item for item in untracked.split("\0") if item):
        file = path / relative
        if file.is_file():
            dirty.update(relative.encode() + b"\0" + file.read_bytes())
    return {
        "worktree": str(path),
        "branch": branch,
        "head": local_sha,
        "upstream": upstream,
        "observed_remote_head": remote_sha,
        "worktree_status_sha256": dirty.hexdigest(),
    }


def emit(root: Path, issue: int, epoch: str) -> dict[str, object]:
    if issue <= 0 or not epoch.strip():
        raise HandoffError("positive issue number and stable epoch are required")
    snapshot = observed(root)
    result = {"schema": SCHEMA, "issue": issue, "epoch": epoch, **snapshot}
    if snapshot["upstream"] is None:
        result.update(status="UNVERIFIED", reason="NO_UPSTREAM")
    return result


def verify(root: Path, payload: dict[str, object]) -> dict[str, object]:
    if payload.get("schema") != SCHEMA or not isinstance(payload.get("issue"), int) or not payload.get("epoch"):
        raise HandoffError("invalid handoff schema, issue or epoch")
    current = observed(root)
    for key, value in current.items():
        if payload.get(key) != value:
            raise HandoffError(f"continuation mismatch on {key}: expected {payload.get(key)!r}, observed {value!r}")
    if current["upstream"] is None:
        return {"status": "UNVERIFIED", "reason": "NO_UPSTREAM",
                "issue": payload["issue"], "epoch": payload["epoch"], **current}
    # Remote head is checked live; neither this nor a payload is an exclusive process lease.
    return {"status": "CONTINUATION_MATCH", "issue": payload["issue"], "epoch": payload["epoch"], **current}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["emit", "verify"])
    parser.add_argument("--worktree", type=Path, default=Path.cwd())
    parser.add_argument("--issue", type=int)
    parser.add_argument("--epoch")
    parser.add_argument("--payload", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "emit":
            if args.issue is None or args.epoch is None:
                parser.error("emit requires --issue and --epoch")
            result = emit(args.worktree, args.issue, args.epoch)
        else:
            if args.payload is None:
                parser.error("verify requires --payload")
            result = verify(args.worktree, json.loads(args.payload.read_text(encoding="utf-8")))
    except (HandoffError, OSError, json.JSONDecodeError) as exc:
        print(f"BAMF_HANDOFF_HOLD: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result.get("status") == "UNVERIFIED" and args.action == "verify" else 0


if __name__ == "__main__":
    raise SystemExit(main())
