"""BAMF-native single-writer lock for persistent human operation."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path


LOCKFILE = ".bamf-operator.lock"


@contextmanager
def bamf_operator_lock(run_dir: Path):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(run_dir / LOCKFILE, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("BAMF_OPERATOR_ANOTHER_WRITER_ACTIVE") from exc
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


__all__ = ("LOCKFILE", "bamf_operator_lock")
