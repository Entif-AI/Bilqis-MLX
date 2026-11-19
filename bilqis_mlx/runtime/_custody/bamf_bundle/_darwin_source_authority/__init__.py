"""Darwin boundary for the fixed ordinary-user C09 authority files."""
from __future__ import annotations

import fcntl
import os
import pwd
import stat

from ..records import invalid


_INVALID = "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID"
_REQUIRED = "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED"
_AUTHORITY_DIR = (".entif-ai", "bilqis")
_REGISTRY_FILE = "source-authority-registry.json"
_SIGNER_FILE = "source-authority-signer.json"
_TRANSACTION_FILE = ".authority-store-transaction.json"
_LIFECYCLE_LOCK_FILE = ".authority-store-lifecycle.lock"
_LIFECYCLE_STATE_FILE = ".authority-store-state.json"
_NON_OWNER_PERMISSION_MASK = stat.S_IRWXG | stat.S_IRWXO

HOST_SOURCE_AUTHORITY_LOGICAL_PATH = (
    "<account-home>/.entif-ai/bilqis/source-authority-registry.json"
)
HOST_SALIENCE_SIGNER_LOGICAL_PATH = (
    "<account-home>/.entif-ai/bilqis/source-authority-signer.json"
)


def _fail(reason: str = _INVALID):
    invalid(reason)


def _effective_account_home() -> tuple[int, str]:
    """Resolve the effective account home without consulting caller-controlled env."""
    try:
        euid = os.geteuid()
        home = pwd.getpwuid(euid).pw_dir
    except (AttributeError, KeyError, OSError):
        _fail()
    if euid == 0 or not isinstance(home, str) or not home or not os.path.isabs(home):
        _fail()
    return euid, home


def _open_account_file(filename: str, *, max_bytes: int) -> int:
    if type(max_bytes) is not int or max_bytes <= 0:
        _fail()
    euid, home = _effective_account_home()
    authority_dir = os.path.join(home, *_AUTHORITY_DIR)
    try:
        lock_fd = os.open(
            os.path.join(authority_dir, _LIFECYCLE_LOCK_FILE),
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
    except FileNotFoundError:
        _fail(_REQUIRED)
    except OSError:
        _fail()
    try:
        # The lock is metadata, not authority. Runtime may create this fixed file so
        # every read serializes with BAMF-0.3 operator publication without gaining
        # any ability to create/replace the registry or signer themselves.
        lock_info = os.fstat(lock_fd)
        if (not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != euid
                or lock_info.st_mode & _NON_OWNER_PERMISSION_MASK):
            _fail()
        fcntl.flock(lock_fd, fcntl.LOCK_SH)
        transaction_path = os.path.join(authority_dir, _TRANSACTION_FILE)
        # Lifecycle-managed writes publish a transaction marker before replacing any
        # authority file. Holding the shared lock makes marker-check + file-open one
        # serialized read boundary against the operator's exclusive writer lock.
        if os.path.lexists(transaction_path):
            _fail()
        path = os.path.join(authority_dir, filename)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            _fail(_REQUIRED)
        except OSError:
            _fail()
        try:
            info = os.fstat(fd)
            managed = os.path.lexists(os.path.join(authority_dir, _LIFECYCLE_STATE_FILE))
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != euid
                    or managed and info.st_mode & _NON_OWNER_PERMISSION_MASK
                    or not 1 <= info.st_size <= max_bytes):
                _fail()
            return fd
        except BaseException:
            os.close(fd)
            raise
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def open_host_source_authority_registry_fd(*, max_bytes: int) -> int:
    """Open the fixed per-account registry; callers cannot provide a path."""
    return _open_account_file(_REGISTRY_FILE, max_bytes=max_bytes)


def open_host_source_authority_signer_fd(*, max_bytes: int) -> int:
    """Open the fixed per-account signer; callers cannot provide a path."""
    return _open_account_file(_SIGNER_FILE, max_bytes=max_bytes)


__all__ = (
    "HOST_SALIENCE_SIGNER_LOGICAL_PATH",
    "HOST_SOURCE_AUTHORITY_LOGICAL_PATH",
    "open_host_source_authority_registry_fd",
    "open_host_source_authority_signer_fd",
)
