"""Structural extraction from akasha_staging.py; behavior preserved."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from .akasha_staging_contracts import PromotionReceipt, StagingProjection, _invalid, _sha
from .akasha_staging_queries import VerifiedStage, verify_staging_projection

_STAGE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS akasha_stages (
    stage_digest TEXT PRIMARY KEY,
    canonical_json TEXT NOT NULL,
    census_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS akasha_active_pointer (
    id INTEGER PRIMARY KEY CHECK (id=1),
    stage_digest TEXT NOT NULL REFERENCES akasha_stages(stage_digest)
);
CREATE TRIGGER IF NOT EXISTS akasha_stages_no_update
BEFORE UPDATE ON akasha_stages
BEGIN SELECT RAISE(ABORT, 'AKASHA_STAGE_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_stages_no_delete
BEFORE DELETE ON akasha_stages
BEGIN SELECT RAISE(ABORT, 'AKASHA_STAGE_APPEND_ONLY'); END;
"""

@contextmanager
def _stage_connection(path: Path):
    if not isinstance(path, Path) or not path.parent.is_dir():
        _invalid("BAMF_C10_STAGING_PATH_INVALID")
    connection = sqlite3.connect(path, timeout=10)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(_STAGE_SCHEMA_SQL)
        with connection:
            yield connection
    finally:
        connection.close()

def promote_staging_projection(
    path: Path, verified: VerifiedStage,
    *, expected_active_digest: str | None,
) -> PromotionReceipt:
    if (not isinstance(verified, VerifiedStage)
            or (expected_active_digest is not None
                and not _sha(expected_active_digest))):
        _invalid("BAMF_C10_STAGING_PROMOTION_ARGUMENT_INVALID")
    stage = verified.stage
    # Recompute the proof immediately before the active-pointer transaction.
    if verified != verify_staging_projection(stage):
        _invalid("BAMF_C10_STAGING_PROOF_INVALID")
    with _stage_connection(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT stage_digest FROM akasha_active_pointer WHERE id=1"
        ).fetchone()
        previous = row[0] if row is not None else None
        if previous != expected_active_digest:
            _invalid("BAMF_C10_STAGING_POINTER_CONFLICT")
        prior = connection.execute(
            "SELECT canonical_json, census_digest FROM akasha_stages "
            "WHERE stage_digest=?", (stage.stage_digest,)).fetchone()
        if prior is None:
            connection.execute(
                "INSERT INTO akasha_stages "
                "(stage_digest, canonical_json, census_digest) "
                "VALUES (?, ?, ?)",
                (stage.stage_digest, stage.canonical_json,
                 verified.census_digest))
        elif prior != (stage.canonical_json, verified.census_digest):
            _invalid("BAMF_C10_STAGING_HISTORY_CONFLICT")
        connection.execute(
            "INSERT INTO akasha_active_pointer (id, stage_digest) "
            "VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET "
            "stage_digest=excluded.stage_digest", (stage.stage_digest,))
    return PromotionReceipt(
        previous, stage.stage_digest, verified.census_digest)

def read_staging_projection(
    path: Path, stage_digest: str,
) -> StagingProjection | None:
    if not isinstance(path, Path) or not _sha(stage_digest):
        _invalid("BAMF_C10_STAGING_DIGEST_INVALID")
    if not path.exists():
        return None
    with _stage_connection(path) as connection:
        row = connection.execute(
            "SELECT canonical_json FROM akasha_stages "
            "WHERE stage_digest=?", (stage_digest,)).fetchone()
    return (StagingProjection.from_canonical_json(row[0])
            if row is not None else None)

def read_active_projection(path: Path) -> StagingProjection | None:
    if not isinstance(path, Path):
        _invalid("BAMF_C10_STAGING_PATH_INVALID")
    if not path.exists():
        return None
    with _stage_connection(path) as connection:
        row = connection.execute(
            "SELECT stage_digest FROM akasha_active_pointer WHERE id=1"
        ).fetchone()
    return (read_staging_projection(path, row[0])
            if row is not None else None)
