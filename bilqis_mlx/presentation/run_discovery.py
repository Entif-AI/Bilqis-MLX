"""Read-only selection of a *running* school across Git worktrees.

Never infer that the freshest saved checkpoint represents a live operator.
The trainer owns .grade-a-operator.lock with an exclusive advisory flock.
An immediate, nonblocking shared-lock probe distinguishes that lock from a
stale file without modifying its contents or interrupting the trainer.
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import subprocess
from typing import Callable, Iterable

from bilqis_mlx.paths import REPO_ROOT


OPERATOR_LOCKFILE = ".grade-a-operator.lock"


class AmbiguousActiveRun(Exception):
    """Several independent students are running; explicit selection required."""


def repository_worktrees(root: Path = REPO_ROOT) -> tuple[Path, ...]:
    """Only discover checkouts registered to this exact Git repository."""
    try:
        command = subprocess.run(
            ["git", "-C", str(root), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=True, timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return (root.resolve(),)
    paths = [root.resolve()]
    for line in command.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree "):]).resolve())
    return tuple(dict.fromkeys(paths))


def operator_lock_held(lock_path: Path) -> bool:
    """True only when another process owns the trainer's exclusive lock."""
    if not lock_path.is_file() or lock_path.is_symlink():
        return False
    try:
        fd = os.open(lock_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except (FileNotFoundError, PermissionError, OSError):
        return False
    acquired = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            return True
        return False
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def candidate_runs(roots: Iterable[Path]) -> tuple[Path, ...]:
    """Find known run layouts without scanning arbitrary learner bundle trees."""
    candidates = set()
    for root in roots:
        runs_root = Path(root) / "runs"
        for pattern in ("*/state.json", "*/*/state.json"):
            for state in runs_root.glob(pattern):
                if state.is_file() and not state.is_symlink():
                    candidates.add(state.parent.resolve())
    return tuple(sorted(candidates))


def select_run(
    default_run: Path, *, worktrees: Iterable[Path] | None = None,
    lock_probe: Callable[[Path], bool] = operator_lock_held,
) -> tuple[Path, bool]:
    """Auto-attach only when exactly one run has a proven live owner."""
    default_run = Path(default_run).resolve()
    roots = repository_worktrees() if worktrees is None else tuple(worktrees)
    candidates = set(candidate_runs(roots))
    if (default_run / "state.json").is_file():
        candidates.add(default_run)
    active = sorted(path for path in candidates if lock_probe(path / OPERATOR_LOCKFILE))
    if len(active) > 1:
        raise AmbiguousActiveRun(
            "Multiple active Bilqis trainers; specify --run-dir:\n" +
            "\n".join(f"  {path}" for path in active))
    return (active[0], True) if active else (default_run, False)
