#!/usr/bin/env python3
"""Reversibly relocate the audited legacy Bilqis worktrees out of ~/Code.

Usage from ~/Code/bilqis-mlx, AFTER human training finishes:

    python3 -B scripts/relocate_legacy_worktrees.py plan
    python3 -B scripts/relocate_legacy_worktrees.py apply --confirm
    python3 -B scripts/relocate_legacy_worktrees.py status
    python3 -B scripts/relocate_legacy_worktrees.py restore --confirm

The destination is ~/Archives/Bilqis/worktrees; the manifest is beside it.
For partial batches, add --only bilqis-candidate-consolidation-v14, etc.
The default is a read-only plan; writes require --confirm. No training,
checkpoint pruning, Git worktree removal, or network transfer. Relocation on
the same disk organizes ~/Code but does NOT free storage; NAS backup is separate.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


# Audited on 2026-10-17. Intentionally NOT a wildcard: future active projects
# must never become relocation candidates just because they start with bilqis-.
LEGACY_NAMES = (
    "bilqis-adaptive-controller-v05",
    "bilqis-auto-curriculum50",
    "bilqis-candidate-consolidation-v14",
    "bilqis-curriculum-v2-design",
    "bilqis-formal-foundations",
    "bilqis-foundation-diagnostics-v2",
    "bilqis-foundation-math-v2",
    "bilqis-foundation-rehab-v2",
    "bilqis-foundation-rehab-v3",
    "bilqis-history-cleanup",
    "bilqis-learner-custody",
    "bilqis-mlx-160",
    "bilqis-next-training-integration",
    "bilqis-pr112-integration-audit",
    "bilqis-pr115-main-sync",
    "bilqis-primitive-staircase-v13",
    "bilqis-release-approval-cleanup",
    "bilqis-release-attestation-dispatch",
    "bilqis-release-check-attestation",
    "bilqis-release-check-run",
    "bilqis-release-ci-fix",
    "bilqis-release-foundation",
    "bilqis-school50-basic-arithmetic-v10",
    "bilqis-school50-best-candidate",
    "bilqis-school50-bridge-carry-forward-v9",
    "bilqis-school50-bridge-foundation-v4",
    "bilqis-school50-bridge-priority-v7",
    "bilqis-school50-bridge-priority-v8-recovery",
    "bilqis-school50-call-report",
    "bilqis-school50-cumulative-acquisition-v5",
    "bilqis-school50-g-primitives-v12",
    "bilqis-school50-hybrid-acquisition-v6",
    "bilqis-school50-mastery-v5",
    "bilqis-school50-numeric-answer-isolation",
    "bilqis-school50-numeric-capacity",
    "bilqis-school50-numeric-spiral",
    "bilqis-school50-operator-fixes",
    "bilqis-school50-primitive-bridge-v3",
    "bilqis-school50-ternary-p43",
    "bilqis-school50-time-first-v11",
    "bilqis-semantic-curriculum-v06",
    "bilqis-spiral-u6",
    "bilqis-standalone-first-v04",
    "bilqis-u7c",
    "bilqis-u7d",
    "bilqis-u7e-cumulative",
    "bilqis-v15-graduation",
    "bilqis-version-scaffold",
)
STANDALONE = "bilqis-learner-custody"
MANIFEST_NAME = "relocation-manifest.json"
SCHEMA = "bilqis.legacy-worktree-relocation/v1"


def command(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {args!r}\n"
                           f"{result.stderr.strip()}")
    return result


def registered_worktrees(repo: Path) -> dict[Path, dict[str, str]]:
    """Read Git's registration, rather than trusting the .git pointer alone."""
    result = command("git", "-C", str(repo), "worktree", "list", "--porcelain")
    entries: dict[Path, dict[str, str]] = {}
    for block in result.stdout.strip().split("\n\n"):
        fields = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            fields[key] = value
        if "worktree" in fields:
            entries[Path(fields.pop("worktree"))] = fields
    return entries


def checked_paths(code: Path, archive: Path) -> None:
    if not code.is_dir() or code.is_symlink():
        raise RuntimeError(f"Code root unavailable or symlinked: {code}")
    if archive == code or code in archive.parents:
        raise RuntimeError("Archive must be outside ~/Code")
    for ancestor in (archive.parent.parent, archive.parent, archive):
        if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()):
            raise RuntimeError(f"Unsafe archive ancestor: {ancestor}")


def inspect(name: str, code: Path, archive: Path,
            registrations: dict[Path, dict[str, str]],
            *, old_item: dict | None = None) -> dict:
    source, target = code / name, archive / name
    if source.is_symlink() or target.is_symlink():
        raise RuntimeError(f"Refusing symlink for {name}")
    has_source, has_target = source.exists(), target.exists()
    if has_source and has_target:
        raise RuntimeError(f"Collision: both original and archive exist for {name}")
    if not has_source and not has_target:
        raise RuntimeError(f"Missing both original and archive for {name}")
    present = source if has_source else target
    if not present.is_dir():
        raise RuntimeError(f"Not a directory: {present}")

    kind = "directory" if name == STANDALONE else "git-worktree"
    if kind == "git-worktree":
        entry = registrations.get(present)
        if entry is None or not (present / ".git").is_file():
            raise RuntimeError(f"Git registration / .git pointer mismatch: {name}")
        if "locked" in entry or "prunable" in entry or "detached" in entry:
            raise RuntimeError(f"Locked, prunable or detached Git worktree: {name}")
        head = entry.get("HEAD")
        branch = entry.get("branch")
        if not head or not branch:
            raise RuntimeError(f"Missing Git worktree identity: {name}")
    else:
        if (present / ".git").exists() or present in registrations:
            raise RuntimeError(f"Standalone custody gained unexpected Git identity: {name}")
        head, branch = None, None

    if old_item:
        if (old_item.get("kind") != kind or
                old_item.get("source") != str(source) or
                old_item.get("target") != str(target)):
            raise RuntimeError(f"Manifest identity mismatch: {name}")
        # An archived worktree can have legitimate new edits or commits. Preserve
        # those intact when restoring it; its Git identity remains authoritative.
    return {"name": name, "source": str(source), "target": str(target),
            "kind": kind, "original_head": (old_item or {}).get("original_head", head),
            "original_branch": (old_item or {}).get("original_branch", branch),
            "location": "original" if has_source else "archive",
            "current_head": head, "current_branch": branch}


def validate_manifest(manifest: dict, code: Path, archive: Path,
                      names: tuple[str, ...]) -> None:
    if (manifest.get("schema") != SCHEMA or
            manifest.get("code_root") != str(code) or
            manifest.get("archive_root") != str(archive) or
            set(manifest.get("items", {})) != set(names)):
        raise RuntimeError("Relocation manifest scope or schema does not match")


def read_manifest(archive: Path) -> dict | None:
    path = archive.parent / MANIFEST_NAME
    if path.is_symlink():
        raise RuntimeError("Relocation manifest may not be a symlink")
    return json.loads(path.read_text()) if path.exists() else None


def atomic_manifest(archive: Path, value: dict) -> None:
    folder = archive.parent
    fd, temp = tempfile.mkstemp(prefix=".relocation-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, folder / MANIFEST_NAME)
        directory_fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def path_contains(root: Path, child: Path) -> bool:
    return child == root or root in child.parents


def idle_guard(paths: list[Path]) -> None:
    """Fail closed for active human trainers and sessions rooted in old trees."""
    ps = command("ps", "-axo", "pid=,command=").stdout
    for row in ps.splitlines():
        if ("bilqis_mlx.cli train" in row or
                ("npm run train" in row and "--human-run" in row)):
            raise RuntimeError("Bilqis trainer appears active; retry after training stops")
        if any(str(path) in row for path in paths):
            raise RuntimeError("A running process references an archive candidate: " + row[:180])

    try:
        listing = command("lsof", "-n", "-d", "cwd", "-Fpn").stdout
    except (FileNotFoundError, RuntimeError) as exc:
        raise RuntimeError("Cannot verify candidate working directories with lsof") from exc
    pid = "unknown"
    for row in listing.splitlines():
        if row.startswith("p"):
            pid = row[1:]
        elif row.startswith("n") and row[1:].startswith("/"):
            cwd = Path(row[1:])
            if any(path_contains(path, cwd) for path in paths):
                raise RuntimeError(f"Process {pid} is working inside {cwd}")


def execute(operation: str, *, code: Path | None = None,
            archive: Path | None = None, names: tuple[str, ...] = LEGACY_NAMES,
            chosen: tuple[str, ...] | None = None, confirm: bool = False,
            guard=idle_guard) -> dict:
    code = code or Path.home() / "Code"
    archive = archive or Path.home() / "Archives" / "Bilqis" / "worktrees"
    # macOS's /var -> /private/var alias appears in Git worktree registration.
    # Normalize the existing Code root before comparing registered paths.
    code, archive = code.resolve(strict=True), archive.absolute()
    checked_paths(code, archive)
    if not names or len(set(names)) != len(names):
        raise RuntimeError("Invalid relocation allowlist")
    chosen = names if chosen is None else chosen
    if not chosen or len(set(chosen)) != len(chosen) or not set(chosen) <= set(names):
        raise RuntimeError("Selection includes unknown, duplicate or zero candidates")
    if operation not in ("plan", "status", "apply", "restore"):
        raise RuntimeError(f"Unknown operation: {operation}")
    if operation in ("apply", "restore") and not confirm:
        raise RuntimeError("No movement performed. Supply --confirm explicitly")
    repo = code / "Bilqis"
    registrations = registered_worktrees(repo)
    manifest = read_manifest(archive)
    if manifest is not None:
        validate_manifest(manifest, code, archive, names)
    if operation == "restore" and manifest is None:
        raise RuntimeError("No relocation manifest exists; cannot safely restore")

    current = {}
    for name in names:
        old_item = manifest["items"][name] if manifest is not None else None
        current[name] = inspect(name, code, archive, registrations, old_item=old_item)
        if manifest is None and current[name]["location"] != "original":
            raise RuntimeError("Already relocated without the manifest: " + name)

    result = {"operation": operation, "manifest": str(archive.parent / MANIFEST_NAME),
              "selected": len(chosen), "items": {name: current[name]["location"] for name in chosen}}
    if operation in ("plan", "status"):
        return result

    guard([code / name for name in chosen] + [archive / name for name in chosen])
    if archive.exists():
        if code.stat().st_dev != archive.stat().st_dev:
            raise RuntimeError("Archive must be on the same filesystem for atomic moves")
    else:
        if code.stat().st_dev != archive.parent.parent.parent.stat().st_dev:
            raise RuntimeError("Archive destination is on another filesystem")

    archive.mkdir(parents=True, exist_ok=True)
    if code.stat().st_dev != archive.stat().st_dev:
        raise RuntimeError("Archive must remain on the same filesystem")
    lock = archive.parent / ".relocation.lock"
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another relocation operation holds the lock") from exc
        # Refresh registration/state after acquiring the exclusive lock.
        registrations = registered_worktrees(repo)
        for name in names:
            old = manifest["items"][name] if manifest else None
            current[name] = inspect(name, code, archive, registrations, old_item=old)
        if manifest is None:
            manifest = {"schema": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(),
                        "code_root": str(code), "archive_root": str(archive),
                        "items": {name: current[name] for name in names}}
            atomic_manifest(archive, manifest)  # Crash recovery starts here.

        wanted = "archive" if operation == "apply" else "original"
        ordered = chosen if operation == "apply" else tuple(reversed(chosen))
        moves = 0
        for name in ordered:
            before = current[name]
            if before["location"] != wanted:
                src = Path(before["source"] if operation == "apply" else before["target"])
                dst = Path(before["target"] if operation == "apply" else before["source"])
                if dst.exists() or dst.is_symlink():
                    raise RuntimeError(f"Destination occupied; refusing overwrite: {dst}")
                if before["kind"] == "git-worktree":
                    command("git", "-C", str(repo), "worktree", "move", str(src), str(dst))
                else:
                    src.rename(dst)
                moves += 1
            registrations = registered_worktrees(repo)
            observed = inspect(name, code, archive, registrations,
                               old_item=manifest["items"][name])
            if observed["location"] != wanted:
                raise RuntimeError(f"Move verification failed: {name}")
            current[name] = observed
            manifest["items"][name] = observed
            atomic_manifest(archive, manifest)
            print(f"{name}: {wanted}", flush=True)
        result["moves_this_invocation"] = moves
        result["items"] = {name: current[name]["location"] for name in chosen}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", nargs="?", default="plan",
                        choices=("plan", "apply", "status", "restore"))
    parser.add_argument("--confirm", action="store_true",
                        help="Required for apply or restore")
    parser.add_argument("--only", action="append", metavar="FOLDER",
                        help="Relocate/restore one allowlisted folder (repeatable)")
    options = parser.parse_args()
    try:
        report = execute(options.operation, confirm=options.confirm,
                         chosen=tuple(options.only) if options.only else None)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"STOPPED, NO FURTHER MOVES: {exc}", file=sys.stderr)
        print("Partial operations can be resumed with the same command or reversed "
              "with 'restore --confirm'.", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    if options.operation == "plan":
        print("READ ONLY. Run 'apply --confirm' after stopping all Bilqis trainers "
              "and sessions using the old folders.")
    elif options.operation == "apply":
        print("Rollback: run 'restore --confirm' using this same script. "
              "Local relocation alone does not free disk space.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
