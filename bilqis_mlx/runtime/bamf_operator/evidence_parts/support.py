"""Shared custody helpers for persistent BAMF candidate evidence."""
from __future__ import annotations

import os
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime import state


EVIDENCE_SCHEMA = "bilqis.bamf.c16.3-candidate-evidence/v1"
REFERENCE_SCHEMA = "bilqis.bamf.c16.3-candidate-evidence-reference/v1"
PERSISTENCE_SCHEMA = "bilqis.bamf.c16.3-evidence-persistence/v1"
_SHA256_HEX_LENGTH = 64
_SIDECAR_ROOT = Path("teacher-observations/objects")
_ROLE_FIELDS = (
    ("option_rows", "selected_option"),
    ("priority", "weakness_replay"),
    ("preservation", "preservation"),
    ("support", "retention_support"),
    ("fresh_support", "fresh_support"),
    ("enrichment", "enrichment"),
    ("prior", "prior_rehearsal"),
)
_PREPARED_ROOTS: set[Path] = set()


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_FIRST_STUDENT.INVALID, reason=reason)


def _plain(value):
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_plain(item) for item in sorted(value)]
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def candidate_attempt_id(
        generation: int, accepted_manifest_sha256: str,
        visit_id: str, candidate_attempt_ordinal: int) -> str:
    if (type(generation) is not int or generation < 0
            or not isinstance(accepted_manifest_sha256, str)
            or len(accepted_manifest_sha256) != _SHA256_HEX_LENGTH
            or any(char not in "0123456789abcdef" for char in accepted_manifest_sha256)
            or not isinstance(visit_id, str) or not visit_id
            or type(candidate_attempt_ordinal) is not int
            or candidate_attempt_ordinal < 1):
        _invalid("BAMF_C16_3_EVIDENCE_ATTEMPT_INVALID")
    return state._fingerprint([
        "bilqis.bamf.c16.3-candidate-attempt/v1",
        generation, accepted_manifest_sha256, visit_id, candidate_attempt_ordinal,
    ])


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def prepare_candidate_evidence_root(run_dir: Path) -> Path:
    """Durably install the evidence hierarchy once before candidate execution."""
    run_dir = Path(run_dir)
    if run_dir.is_symlink() or not run_dir.is_dir():
        _invalid("BAMF_C16_3_EVIDENCE_ROOT_INVALID")
    if run_dir in _PREPARED_ROOTS:
        target = run_dir / _SIDECAR_ROOT
        if target.is_symlink() or not target.is_dir():
            _invalid("BAMF_C16_3_EVIDENCE_ROOT_INVALID")
        return target
    current = run_dir
    for part in _SIDECAR_ROOT.parts:
        child = current / part
        if child.is_symlink() or (child.exists() and not child.is_dir()):
            _invalid("BAMF_C16_3_EVIDENCE_ROOT_INVALID")
        child.mkdir(exist_ok=True)
        _fsync_directory(child)
        _fsync_directory(current)
        current = child
    _PREPARED_ROOTS.add(run_dir)
    return current


__all__ = (
    "EVIDENCE_SCHEMA", "PERSISTENCE_SCHEMA", "REFERENCE_SCHEMA",
    "candidate_attempt_id", "prepare_candidate_evidence_root",
)
