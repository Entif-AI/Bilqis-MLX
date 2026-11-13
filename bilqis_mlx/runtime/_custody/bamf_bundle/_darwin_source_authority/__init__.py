"""Darwin boundary for the fixed ordinary-user C09 authority files."""
from __future__ import annotations

import os
import pwd
import stat

from ..records import invalid


_INVALID = "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID"
_REQUIRED = "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED"
_AUTHORITY_DIR = (".entif-ai", "bilqis")
_REGISTRY_FILE = "source-authority-registry.json"
_SIGNER_FILE = "source-authority-signer.json"

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
    path = os.path.join(home, *_AUTHORITY_DIR, filename)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        _fail(_REQUIRED)
    except OSError:
        _fail()
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != euid
                or not 1 <= info.st_size <= max_bytes):
            _fail()
        return fd
    except BaseException:
        os.close(fd)
        raise


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
