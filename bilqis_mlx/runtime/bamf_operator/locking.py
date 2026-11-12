"""BAMF-native single-writer lock for persistent human operation."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL


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
            try:
                ErrorBus.raise_(
                    SCHOOL.BAMF_FIRST_STUDENT.INVALID,
                    reason="BAMF_OPERATOR_ANOTHER_WRITER_ACTIVE")
            except Exception as error:
                raise error from exc
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


__all__ = ("LOCKFILE", "bamf_operator_lock")
