"""SQLite custody helpers for projection lifecycle records."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from bilqis_mlx.runtime.akasha_domains import AkashaDomain
from .common import _invalid, _sha
from .contracts import ProjectionBuildIntent, ProjectionVersion


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS akasha_projection_builds (
    build_sha256 TEXT PRIMARY KEY, domain TEXT NOT NULL, canonical_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS akasha_projection_versions (
    version_sha256 TEXT PRIMARY KEY,
    build_sha256 TEXT NOT NULL UNIQUE REFERENCES akasha_projection_builds(build_sha256),
    domain TEXT NOT NULL, canonical_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS akasha_projection_active (
    domain TEXT PRIMARY KEY,
    version_sha256 TEXT NOT NULL REFERENCES akasha_projection_versions(version_sha256));
CREATE TABLE IF NOT EXISTS akasha_projection_selections (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    selection_sha256 TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL, canonical_json TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS akasha_projection_builds_no_update
BEFORE UPDATE ON akasha_projection_builds
BEGIN SELECT RAISE(ABORT, 'AKASHA_PROJECTION_BUILD_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_projection_builds_no_delete
BEFORE DELETE ON akasha_projection_builds
BEGIN SELECT RAISE(ABORT, 'AKASHA_PROJECTION_BUILD_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_projection_versions_no_update
BEFORE UPDATE ON akasha_projection_versions
BEGIN SELECT RAISE(ABORT, 'AKASHA_PROJECTION_VERSION_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_projection_versions_no_delete
BEFORE DELETE ON akasha_projection_versions
BEGIN SELECT RAISE(ABORT, 'AKASHA_PROJECTION_VERSION_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_projection_selections_no_update
BEFORE UPDATE ON akasha_projection_selections
BEGIN SELECT RAISE(ABORT, 'AKASHA_PROJECTION_SELECTION_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS akasha_projection_selections_no_delete
BEFORE DELETE ON akasha_projection_selections
BEGIN SELECT RAISE(ABORT, 'AKASHA_PROJECTION_SELECTION_APPEND_ONLY'); END;
"""


@contextmanager
def connection(path: Path):
    if not isinstance(path, Path) or not path.parent.is_dir():
        _invalid("AKASHA_PROJECTION_STORE_PATH_INVALID")
    database = sqlite3.connect(path, timeout=10)
    try:
        database.execute("PRAGMA foreign_keys=ON")
        database.execute("PRAGMA journal_mode=WAL")
        database.executescript(SCHEMA_SQL)
        with database:
            yield database
    finally:
        database.close()


def active_digest(database, domain: AkashaDomain) -> str | None:
    row = database.execute(
        "SELECT version_sha256 FROM akasha_projection_active WHERE domain=?",
        (domain.value,)).fetchone()
    return row[0] if row is not None else None


def stored_build(database, build_sha256: str) -> ProjectionBuildIntent:
    row = database.execute(
        "SELECT canonical_json FROM akasha_projection_builds WHERE build_sha256=?",
        (build_sha256,)).fetchone()
    if row is None:
        _invalid("AKASHA_PROJECTION_BUILD_UNKNOWN")
    build = ProjectionBuildIntent.from_canonical_json(row[0])
    if build.build_sha256 != build_sha256:
        _invalid("AKASHA_PROJECTION_BUILD_STORED_INVALID")
    return build


def read_version(database, version_sha256: str) -> ProjectionVersion:
    if not _sha(version_sha256):
        _invalid("AKASHA_PROJECTION_VERSION_DIGEST_INVALID")
    row = database.execute(
        "SELECT canonical_json FROM akasha_projection_versions WHERE version_sha256=?",
        (version_sha256,)).fetchone()
    if row is None:
        _invalid("AKASHA_PROJECTION_VERSION_UNKNOWN")
    version = ProjectionVersion.from_canonical_json(row[0])
    if version.version_sha256 != version_sha256:
        _invalid("AKASHA_PROJECTION_STORED_CORRUPT")
    return version


def previously_selected(database, domain: AkashaDomain, version_sha256: str) -> bool:
    rows = database.execute(
        "SELECT canonical_json FROM akasha_projection_selections WHERE domain=?",
        (domain.value,)).fetchall()
    from .selection import ProjectionSelectionReceipt
    return any(
        ProjectionSelectionReceipt.from_canonical_json(row[0]).selected_version_sha256
        == version_sha256
        for row in rows)
