"""Physical-parent claim for serialized BAMF run-root creation and fixture mutation."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat

from bilqis_mlx.errors import ErrorBus, SCHOOL


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_FIRST_STUDENT.INVALID, reason=reason)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _prepare_parent(parent: Path, *, create_parent: bool) -> Path:
    if create_parent:
        created: list[Path] = []
        ancestor = parent
        while not ancestor.exists():
            created.append(ancestor)
            ancestor = ancestor.parent
        if not ancestor.is_dir():
            raise OSError("unsafe run-root parent ancestor")
        parent.mkdir(parents=True, exist_ok=True)
        for directory in created:
            _fsync_directory(directory)
        if created:
            _fsync_directory(ancestor)
    elif not parent.exists() or not parent.is_dir():
        raise OSError("run-root parent unavailable")
    return parent.resolve(strict=True)


@contextmanager
def run_root_claim(target: Path, *, create_parent: bool):
    """Serialize one target under its physical parent without reserving a child path."""
    target = Path(target)
    descriptor = None
    locked = False
    try:
        try:
            parent = _prepare_parent(target.parent, create_parent=create_parent)
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(parent, flags)
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError("run-root parent is not a directory")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
        except BaseException:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            _invalid("BAMF_RUN_ROOT_CLAIM_UNAVAILABLE")

        body_error = None
        try:
            yield None
        except BaseException as error:
            body_error = error
            raise
        finally:
            release_failure = None
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    release_failure = "unlock"
            try:
                os.close(descriptor)
            except OSError:
                if release_failure is None:
                    release_failure = "close"
            if release_failure is not None:
                if body_error is not None:
                    body_error.add_note(
                        f"BAMF_RUN_ROOT_CLAIM_RELEASE_FAILED:{release_failure}")
                else:
                    _invalid("BAMF_RUN_ROOT_CLAIM_RELEASE_FAILED")
    finally:
        descriptor = None
