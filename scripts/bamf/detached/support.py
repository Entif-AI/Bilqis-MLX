"""Support machinery for the BAMF detached long-run launcher."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


SNAPSHOT_IGNORED_NAMES = frozenset({
    ".git", ".local", ".pytest_cache", ".venv", "__pycache__",
    "node_modules", "venv",
})
MUTATION_IGNORED_NAMES = SNAPSHOT_IGNORED_NAMES | frozenset({
    ".testmondata", ".testmondata-journal", ".testmondata-shm", ".testmondata-wal",
    "_private", "runs",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _snapshot_ignore(_directory: str, names: list[str]) -> set[str]:
    return set(names).intersection(SNAPSHOT_IGNORED_NAMES)


def _snapshot_entries(root: Path, *, ignored_names=SNAPSHOT_IGNORED_NAMES):
    root = root.resolve()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in ignored_names for part in relative.parts):
            continue
        yield path, relative


def _tree_digest(root: Path, *, ignored_names=SNAPSHOT_IGNORED_NAMES) -> str:
    digest = hashlib.sha256()
    for path, relative in _snapshot_entries(root, ignored_names=ignored_names):
        identity = relative.as_posix().encode("utf-8")
        mode = f"{path.lstat().st_mode & 0o7777:o}".encode("ascii")
        if path.is_symlink():
            digest.update(b"L\0" + identity + b"\0" + mode + b"\0")
            digest.update(os.readlink(path).encode("utf-8") + b"\0")
            continue
        if path.is_dir():
            digest.update(b"D\0" + identity + b"\0" + mode + b"\0")
            continue
        if not path.is_file():
            raise RuntimeError(f"unsupported detached source entry: {path}")
        digest.update(b"F\0" + identity + b"\0" + mode + b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_snapshot_symlinks(root: Path) -> None:
    root = root.resolve()
    for path, _relative in _snapshot_entries(root):
        if not path.is_symlink():
            continue
        raw_target = Path(os.readlink(path))
        target = (path.parent / raw_target).resolve(strict=False)
        if not target.is_relative_to(root):
            raise RuntimeError(f"detached source symlink escapes workdir: {path}")


def _git_toplevel(source: Path) -> Path | None:
    completed = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False,
    )
    return None if completed.returncode else Path(completed.stdout.strip()).resolve()


def _prepare_git_snapshot(source: Path, snapshot: Path) -> bool:
    if _git_toplevel(source) != source:
        return False
    completed = subprocess.run(
        ["git", "-C", str(source), "worktree", "add", "--detach", str(snapshot), "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            "detached git worktree creation failed: " + completed.stderr.strip())
    for child in snapshot.iterdir():
        if child.name == ".git":
            continue
        shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
    shutil.copytree(
        source, snapshot, symlinks=True, ignore=_snapshot_ignore,
        copy_function=shutil.copy2, dirs_exist_ok=True,
    )
    return True


def _bind_local_runtime(source: Path, snapshot: Path) -> None:
    for name in (".venv", "node_modules"):
        source_runtime = source / name
        snapshot_runtime = snapshot / name
        if source_runtime.exists() and not snapshot_runtime.exists():
            snapshot_runtime.symlink_to(source_runtime, target_is_directory=True)


def _discard_snapshot(source: Path, snapshot: Path, *, git_snapshot: bool) -> None:
    if git_snapshot:
        subprocess.run(
            ["git", "-C", str(source), "worktree", "remove", "--force", str(snapshot)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    shutil.rmtree(snapshot, ignore_errors=True)


def _snapshot_workdir(source: Path, snapshot: Path) -> dict[str, str]:
    source = Path(source).resolve()
    snapshot = Path(snapshot).resolve()
    if not source.is_dir():
        raise RuntimeError(f"detached source workdir missing: {source}")
    if snapshot.exists():
        raise RuntimeError(f"detached source snapshot already exists: {snapshot}")
    if snapshot.is_relative_to(source):
        relative = snapshot.relative_to(source)
        if not relative.parts or relative.parts[0] not in SNAPSHOT_IGNORED_NAMES:
            raise RuntimeError("detached source snapshot must not recurse into its source")
    _validate_snapshot_symlinks(source)
    before = _tree_digest(source)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    git_snapshot = False
    try:
        git_snapshot = _prepare_git_snapshot(source, snapshot)
        if not git_snapshot:
            shutil.copytree(
                source, snapshot, symlinks=True, ignore=_snapshot_ignore,
                copy_function=shutil.copy2,
            )
        _bind_local_runtime(source, snapshot)
        after = _tree_digest(source)
        copied = _tree_digest(snapshot)
        if before != after:
            raise RuntimeError("detached source changed while snapshot was being copied")
        if copied != after:
            raise RuntimeError("detached source snapshot digest mismatch")
    except Exception:
        _discard_snapshot(source, snapshot, git_snapshot=git_snapshot)
        raise
    return {"source_sha256": after, "snapshot_sha256": copied}


def _notify(label: str, returncode: int) -> None:
    status = "PASS" if returncode == 0 else f"FAIL ({returncode})"
    script = (
        f"display notification {json.dumps(f'{label}: {status}')} "
        f"with title {json.dumps('Bilqis long run finished')} sound name \"Glass\""
    )
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode and Path("/System/Library/Sounds/Glass.aiff").is_file():
        subprocess.Popen(
            ["/usr/bin/afplay", "/System/Library/Sounds/Glass.aiff"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )


def _run_child_with_heartbeats(
    args, *, workdir: Path, stream, receipt: Path, initial: dict,
    heartbeat_seconds: float, environment: dict[str, str],
) -> int:
    process = subprocess.Popen(
        args.command, cwd=workdir, stdin=subprocess.DEVNULL,
        stdout=stream, stderr=subprocess.STDOUT, env=environment,
    )
    child_started = _utc_now()
    stream.write(
        (f"DETACHED_LONG_RUN_CHILD_STARTED {child_started} label={args.label!r} "
         f"child_pid={process.pid}\n").encode()
    )
    child_started_monotonic = time.monotonic()
    while True:
        try:
            return process.wait(timeout=heartbeat_seconds)
        except subprocess.TimeoutExpired:
            heartbeat_at = _utc_now()
            elapsed_seconds = time.monotonic() - child_started_monotonic
            stream.write(
                (f"DETACHED_LONG_RUN_HEARTBEAT {heartbeat_at} label={args.label!r} "
                 f"child_pid={process.pid} elapsed_seconds={elapsed_seconds:.1f}\n").encode()
            )
            _write_json(receipt, {
                **initial,
                "last_heartbeat_at": heartbeat_at,
                "elapsed_seconds": round(elapsed_seconds, 1),
            })
