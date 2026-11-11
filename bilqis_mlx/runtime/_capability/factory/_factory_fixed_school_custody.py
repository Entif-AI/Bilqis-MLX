"""Synchronization for C05 fixed-school custody."""
from __future__ import annotations

import contextlib
import fcntl
import os
import stat

from bilqis_mlx.runtime.capability_evaluation import _invalid


@contextlib.contextmanager
def fixed_school_lock(root_fd: int):
    """Serialize materialization; the lock file itself contains no authority."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(
            ".c05-fixed-school.lock", os.O_RDWR | os.O_CREAT | nofollow,
            0o600, dir_fd=root_fd)
        opened = os.fstat(fd)
        named = os.stat(
            ".c05-fixed-school.lock", dir_fd=root_fd, follow_symlinks=False)
        if (not stat.S_ISREG(opened.st_mode) or not stat.S_ISREG(named.st_mode)
                or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)):
            os.close(fd)
            _invalid("BAMF_C05_FIXED_SCHOOL_LOCK_UNSAFE")
        fcntl.flock(fd, fcntl.LOCK_EX)
    except OSError:
        try:
            os.close(fd)
        except (OSError, UnboundLocalError):
            pass
        _invalid("BAMF_C05_FIXED_SCHOOL_LOCK_UNSAFE")
        raise AssertionError
    try:
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass
