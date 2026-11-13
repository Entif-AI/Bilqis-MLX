"""Read the one declared legacy-trainer adaptation authority fail-closed.

The legacy trainer is an adaptation oracle only.  This module never resumes it
and never imports its model or optimizer state into BAMF.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from bilqis_mlx.errors import ErrorBus, SCHOOL


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PATH = ROOT / "docs/tasks/bamf-0.2/legacy-trainer-authority.json"
SCHEMA = "bilqis.bamf.legacy-trainer-authority/v1"
GIT_SHA1_HEX_LENGTH = 40


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_FIRST_STUDENT.INVALID, reason=reason)


def authority_record(path: Path = AUTHORITY_PATH) -> dict:
    """Return the checked-in authority record after structural validation."""
    try:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        try:
            _invalid("LEGACY_TRAINER_AUTHORITY_READ_FAILED")
        except Exception as error:
            raise error from exc
    required = {
        "schema", "version", "source_branch", "source_worktree",
        "source_run", "source_state",
    }
    if (
        not isinstance(record, dict)
        or not required.issubset(record)
        or record.get("schema") != SCHEMA
        or any(not isinstance(record.get(name), str) or not record[name]
               for name in required - {"schema"})
    ):
        _invalid("LEGACY_TRAINER_AUTHORITY_RECORD_INVALID")
    return record


def _git(worktree: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=worktree, capture_output=True, text=True)
    if result.returncode:
        _invalid("LEGACY_TRAINER_AUTHORITY_GIT_CHECK_FAILED")
    return result.stdout.strip()


def live_authority(record: dict | None = None) -> tuple[dict, str, dict]:
    """Return exact authority, observed source head, and current source receipt.

    The source worktree/run are intentionally external to BAMF custody.  Missing
    or drifted authority therefore blocks the first C03 bootstrap rather than
    falling back to an older local trainer.
    """
    record = authority_record() if record is None else dict(record)
    if record.get("schema") != SCHEMA:
        _invalid("LEGACY_TRAINER_AUTHORITY_SCHEMA_INVALID")
    worktree = Path(record["source_worktree"])
    run = Path(record["source_run"])
    if not worktree.is_dir() or not run.is_dir():
        _invalid("LEGACY_TRAINER_AUTHORITY_SOURCE_UNAVAILABLE")
    branch = _git(worktree, "branch", "--show-current")
    head = _git(worktree, "rev-parse", "HEAD")
    if branch != record["source_branch"]:
        _invalid("LEGACY_TRAINER_AUTHORITY_BRANCH_DRIFT")
    if (len(head) != GIT_SHA1_HEX_LENGTH
            or any(char not in "0123456789abcdef" for char in head)):
        _invalid("LEGACY_TRAINER_AUTHORITY_HEAD_INVALID")
    from bilqis_mlx.state_dag import read_current
    current = read_current(run)
    teacher = current.get("teacher") if isinstance(current, dict) else None
    if (
        not isinstance(teacher, dict)
        or not isinstance(teacher.get("strategies"), dict)
        or not teacher["strategies"]
    ):
        _invalid("LEGACY_TRAINER_AUTHORITY_TEACHER_INVALID")
    return record, head, current


__all__ = ("AUTHORITY_PATH", "SCHEMA", "authority_record", "live_authority")
