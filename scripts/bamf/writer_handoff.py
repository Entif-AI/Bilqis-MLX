#!/usr/bin/env python3
"""Emit and verify local BAMF worktree-continuation evidence.

This is a compaction handoff, NOT a distributed lock or writer lease.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import errno
import hashlib
import json
import os
import stat
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
    return result.stdout if "-z" in args else result.stdout.strip()


def _hash_part(digest, payload: bytes) -> None:
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)


def _capture_path(root: Path, relative: str, *, allow_missing: bool) -> tuple[bytes, int, bytes]:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parts = Path(relative).parts
    with ExitStack() as descriptors:
        parent = os.open(root, directory_flags)
        descriptors.callback(os.close, parent)
        try:
            for component in parts[:-1]:
                try:
                    parent = os.open(component, directory_flags, dir_fd=parent)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise HandoffError(f"unsafe symlink or non-directory ancestor: {relative}") from exc
                    raise
                descriptors.callback(os.close, parent)
            name = parts[-1]
            metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                return b"symlink", stat.S_IMODE(metadata.st_mode), os.fsencode(os.readlink(name, dir_fd=parent))
            if not stat.S_ISREG(metadata.st_mode):
                raise HandoffError(f"unsupported captured entry: {relative}")
            try:
                descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise HandoffError(f"captured path changed to symlink before open: {relative}") from exc
                raise
            with os.fdopen(descriptor, "rb") as source:
                metadata = os.fstat(source.fileno())
                if not stat.S_ISREG(metadata.st_mode):
                    raise HandoffError(f"unsupported captured entry after open: {relative}")
                return b"file", stat.S_IMODE(metadata.st_mode), source.read()
        except FileNotFoundError:
            if not allow_missing:
                raise
            return b"absent", 0, b""


def _hash_path(digest, root: Path, relative: str, *, allow_missing: bool = False) -> None:
    kind, mode, payload = _capture_path(root, relative, allow_missing=allow_missing)
    for part in (os.fsencode(relative), kind, mode.to_bytes(4, "big"), payload):
        _hash_part(digest, part)


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
    dirty = hashlib.sha256(b"bilqis.bamf.worktree-fingerprint/v4\0")
    _hash_part(dirty, status.encode())
    _hash_part(dirty, diff)
    _hash_part(dirty, git(path, "ls-files", "--stage", "-z").encode())
    index_flags = git(path, "ls-files", "-v", "-z")
    _hash_part(dirty, index_flags.encode())
    for record in index_flags.split("\0"):
        if record and (record[0].islower() or record[0] == "S"):
            _hash_part(dirty, b"hidden-tracked")
            _hash_path(dirty, path, record[2:], allow_missing=True)
    untracked = git(path, "ls-files", "--others", "--exclude-standard", "-z")
    # git's text output strips only the final NUL; embedded NULs remain.
    for relative in sorted(item for item in untracked.split("\0") if item):
        _hash_part(dirty, b"untracked")
        _hash_path(dirty, path, relative)
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
