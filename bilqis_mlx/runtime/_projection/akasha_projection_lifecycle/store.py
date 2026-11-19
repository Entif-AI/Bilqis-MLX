"""Durable create-only Akasha projection versions with atomic selection."""
from __future__ import annotations

from pathlib import Path
from bilqis_mlx.runtime.akasha_domains import (
    AkashaDomain,
    DOMAIN_CONTRACTS,
    rebuild_projection_identity,
)
from .common import _invalid
from .contracts import ProjectionBuildIntent, ProjectionVersion
from .persistence import (
    active_digest,
    connection,
    previously_selected,
    read_version,
    stored_build,
)
from .selection import ProjectionSelectionKind, ProjectionSelectionReceipt


def begin_projection_rebuild(
    path: Path, domain: AkashaDomain, *, projection_version: int,
    rebuild_source: str, source_records: tuple[dict, ...],
    expected_active_sha256: str | None,
) -> ProjectionBuildIntent:
    intent = ProjectionBuildIntent.create(
        domain, projection_version=projection_version,
        rebuild_source=rebuild_source, source_records=source_records,
        expected_active_sha256=expected_active_sha256)
    with connection(path) as database:
        current = active_digest(database, domain)
        if current != expected_active_sha256:
            _invalid("AKASHA_PROJECTION_POINTER_CONFLICT")
        prior = database.execute(
            "SELECT canonical_json FROM akasha_projection_builds WHERE build_sha256=?",
            (intent.build_sha256,)).fetchone()
        if prior is None:
            database.execute(
                "INSERT INTO akasha_projection_builds "
                "(build_sha256, domain, canonical_json) VALUES (?, ?, ?)",
                (intent.build_sha256, domain.value, intent.canonical_json))
        elif prior[0] != intent.canonical_json:
            _invalid("AKASHA_PROJECTION_BUILD_HISTORY_CONFLICT")
    return intent


def complete_projection_rebuild(
    path: Path, intent: ProjectionBuildIntent, *,
    source_records: tuple[dict, ...], payload: object,
) -> ProjectionVersion:
    expected = rebuild_projection_identity(intent.domain, source_records)
    if expected.source_frontier_sha256 != intent.source_frontier_sha256:
        _invalid("AKASHA_PROJECTION_SOURCE_FRONTIER_DRIFT")
    version = ProjectionVersion.from_payload(intent, payload)
    with connection(path) as database:
        stored = stored_build(database, intent.build_sha256)
        if stored != intent:
            _invalid("AKASHA_PROJECTION_BUILD_STORED_INVALID")
        prior = database.execute(
            "SELECT version_sha256, canonical_json FROM akasha_projection_versions "
            "WHERE build_sha256=?", (intent.build_sha256,)).fetchone()
        if prior is None:
            database.execute(
                "INSERT INTO akasha_projection_versions "
                "(version_sha256, build_sha256, domain, canonical_json) "
                "VALUES (?, ?, ?, ?)",
                (version.version_sha256, intent.build_sha256,
                 intent.domain.value, version.canonical_json))
        elif prior != (version.version_sha256, version.canonical_json):
            _invalid("AKASHA_PROJECTION_VERSION_HISTORY_CONFLICT")
    return version


def read_projection_version(path: Path, version_sha256: str) -> ProjectionVersion:
    with connection(path) as database:
        return read_version(database, version_sha256)


def select_projection_version(
    path: Path, version: ProjectionVersion, *,
    expected_active_sha256: str | None,
    kind: ProjectionSelectionKind, evidence_sha256: str,
) -> ProjectionSelectionReceipt:
    if not isinstance(version, ProjectionVersion) or not isinstance(kind, ProjectionSelectionKind):
        _invalid("AKASHA_PROJECTION_SELECTION_ARGUMENT_INVALID")
    with connection(path) as database:
        database.execute("BEGIN IMMEDIATE")
        stored = read_version(database, version.version_sha256)
        if stored != version:
            _invalid("AKASHA_PROJECTION_STORED_CORRUPT")
        build = stored_build(database, version.build_sha256)
        current = active_digest(database, version.domain)
        if current != expected_active_sha256:
            _invalid("AKASHA_PROJECTION_POINTER_CONFLICT")
        current_version = read_version(database, current) if current is not None else None
        if kind is ProjectionSelectionKind.INITIAL:
            if current is not None:
                _invalid("AKASHA_PROJECTION_INITIAL_REQUIRES_EMPTY")
        elif kind is not ProjectionSelectionKind.ROLLBACK:
            if build.expected_active_sha256 != expected_active_sha256:
                _invalid("AKASHA_PROJECTION_BUILD_PRECONDITION_DRIFT")
            if (kind is ProjectionSelectionKind.MIGRATION
                    and (current_version is None
                         or version.projection_version
                         <= current_version.projection_version)):
                _invalid("AKASHA_PROJECTION_MIGRATION_VERSION_INVALID")
            if (kind is ProjectionSelectionKind.REBUILD
                    and (current_version is None
                         or version.projection_version
                         != current_version.projection_version)):
                _invalid("AKASHA_PROJECTION_REBUILD_VERSION_INVALID")
        receipt = ProjectionSelectionReceipt.create(
            kind, version.domain, current, version.version_sha256, evidence_sha256)
        database.execute(
            "INSERT INTO akasha_projection_selections "
            "(selection_sha256, domain, canonical_json) VALUES (?, ?, ?)",
            (receipt.selection_sha256, version.domain.value, receipt.canonical_json))
        database.execute(
            "INSERT INTO akasha_projection_active (domain, version_sha256) VALUES (?, ?) "
            "ON CONFLICT(domain) DO UPDATE SET version_sha256=excluded.version_sha256",
            (version.domain.value, version.version_sha256))
    return receipt


def read_active_projection(
    path: Path, domain: AkashaDomain, *, source_records: tuple[dict, ...],
    expected_projection_version: int | None = None,
) -> ProjectionVersion:
    contract = DOMAIN_CONTRACTS.get(domain)
    if contract is None:
        _invalid("AKASHA_PROJECTION_DOMAIN_UNKNOWN")
    expected = rebuild_projection_identity(domain, source_records)
    with connection(path) as database:
        active = active_digest(database, domain)
        if active is None:
            _invalid("AKASHA_PROJECTION_ACTIVE_MISSING")
        version = read_version(database, active)
    if (version.domain is not domain
            or version.contract_sha256 != contract.digest
            or version.projection_schema != contract.projection_schema
            or version.source_frontier_sha256 != expected.source_frontier_sha256
            or (expected_projection_version is not None
                and version.projection_version != expected_projection_version)):
        _invalid("AKASHA_PROJECTION_STALE")
    return version


def rollback_projection_version(
    path: Path, domain: AkashaDomain, target_version_sha256: str, *,
    expected_active_sha256: str, evidence_sha256: str,
) -> ProjectionSelectionReceipt:
    target = read_projection_version(path, target_version_sha256)
    if target.domain is not domain:
        _invalid("AKASHA_PROJECTION_DOMAIN_MISMATCH")
    with connection(path) as database:
        if not previously_selected(database, domain, target_version_sha256):
            _invalid("AKASHA_PROJECTION_ROLLBACK_TARGET_UNPROVEN")
    return select_projection_version(
        path, target, expected_active_sha256=expected_active_sha256,
        kind=ProjectionSelectionKind.ROLLBACK, evidence_sha256=evidence_sha256)


def list_projection_versions(path: Path, domain: AkashaDomain) -> tuple[ProjectionVersion, ...]:
    with connection(path) as database:
        rows = database.execute(
            "SELECT version_sha256 FROM akasha_projection_versions "
            "WHERE domain=? ORDER BY rowid", (domain.value,)).fetchall()
        return tuple(read_version(database, row[0]) for row in rows)


def selection_history(path: Path, domain: AkashaDomain) -> tuple[ProjectionSelectionReceipt, ...]:
    with connection(path) as database:
        rows = database.execute(
            "SELECT canonical_json FROM akasha_projection_selections "
            "WHERE domain=? ORDER BY seq", (domain.value,)).fetchall()
    return tuple(ProjectionSelectionReceipt.from_canonical_json(row[0]) for row in rows)
