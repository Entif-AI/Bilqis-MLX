"""Write-once first-materialization anchor and synchronization for C05."""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
from pathlib import Path
import stat

from bilqis_mlx.runtime.capability_evaluation import _invalid
from bilqis_mlx.runtime.state import _durable_json

from ._factory_fixed_school_contract import is_hex

ANCHOR_SCHEMA = "bilqis.mlx.c05-bamf-fixed-school-anchor/v1"
ANCHOR_KEYS = {
    "schema", "run_id", "run_identity_sha256",
    "foundation_parent_manifest_sha256",
}


def _anchor_payload(parent, cache) -> dict:
    return {
        "schema": ANCHOR_SCHEMA,
        "run_id": parent.run_id,
        "run_identity_sha256": parent.run_identity.digest,
        "foundation_parent_manifest_sha256": cache.accepted_manifest_sha256,
    }


def foundation_anchor(run_dir: Path, parent, cache, *, receipt_exists: bool) -> str:
    path = Path(run_dir) / ".c05-fixed-school.anchor.json"
    expected = _anchor_payload(parent, cache)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        _invalid("BAMF_C05_FIXED_SCHOOL_ANCHOR_UNSAFE")
    if not path.exists():
        if receipt_exists:
            _invalid("BAMF_C05_FIXED_SCHOOL_ANCHOR_MISSING")
        _durable_json(path, expected)
        return expected["foundation_parent_manifest_sha256"]
    try:
        stored = json.loads(path.read_text())
    except (OSError, ValueError, TypeError):
        _invalid("BAMF_C05_FIXED_SCHOOL_ANCHOR_DRIFT")
        raise AssertionError
    if (not isinstance(stored, dict) or set(stored) != ANCHOR_KEYS
            or stored.get("schema") != ANCHOR_SCHEMA
            or stored.get("run_id") != parent.run_id
            or stored.get("run_identity_sha256") != parent.run_identity.digest
            or not is_hex(stored.get("foundation_parent_manifest_sha256"))):
        _invalid("BAMF_C05_FIXED_SCHOOL_ANCHOR_DRIFT")
    anchor = stored["foundation_parent_manifest_sha256"]
    if not receipt_exists and anchor != cache.accepted_manifest_sha256:
        _invalid("BAMF_C05_FIXED_SCHOOL_ANCHOR_PARENT_ADVANCED")
    return anchor


@contextlib.contextmanager
def fixed_school_lock(run_dir: Path):
    """Serialize materialization; the lock file itself contains no authority."""
    path = Path(run_dir) / ".c05-fixed-school.lock"
    if path.is_symlink():
        _invalid("BAMF_C05_FIXED_SCHOOL_LOCK_UNSAFE")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | nofollow, 0o600)
        opened = os.fstat(fd)
        named = os.stat(path, follow_symlinks=False)
        if (not stat.S_ISREG(opened.st_mode) or not stat.S_ISREG(named.st_mode)
                or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)):
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
