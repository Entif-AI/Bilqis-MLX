"""Current accepted-state hydration and publication-parent witness ownership.

This module owns the bounded proof that one accepted BAMF generation is the
current B13 state. Execution-cache construction is deliberately separate.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .accepted_runtime import (
    _published_in_memory_identity_locked, _read_accepted_locked,
)
from .bundle_currentness import (
    bind_bamf_bundle_currentness, require_bamf_bundle_currentness,
)
from .records import CompleteStudent, canonical, invalid, sha


def _require_initial_foundation_authority(
        run_dir: Path, student: CompleteStudent) -> None:
    if student.run_identity is None:
        return
    from .publication.factory_release import require_initial_factory_release
    require_initial_factory_release(run_dir, student)


def _acceptance_file_sha256(run_dir: Path, manifest_sha256: str) -> str:
    path = Path(run_dir) / "bamf-acceptance" / f"{manifest_sha256}.json"
    if path.is_symlink() or not path.is_file():
        invalid("BAMF_GENERATION_ACCEPTANCE_REQUIRED")
    return sha(path.read_bytes())


@dataclass(frozen=True)
class AcceptedHydration:
    manifest_sha256: str
    pointer_sha256: str
    acceptance_sha256: str
    acceptance_file_sha256: str
    student: CompleteStudent
    correction_frontier_canonical: bytes
    candidate_identity_sha256: str
    currentness: object


_PUBLICATION_PARENT_ISSUER = object()


@dataclass(frozen=True, init=False, eq=False)
class AcceptedPublicationParent:
    """Non-serializable proof that one hydrated parent is current B13 custody."""

    manifest_sha256: str
    acceptance_sha256: str
    student: CompleteStudent
    _pointer_sha256: str
    _acceptance_file_sha256: str
    _hydration: AcceptedHydration
    _currentness: object
    _issuance: object

    def __init__(self, *args, **kwargs):
        invalid("B13_PUBLICATION_PARENT_REQUIRED")


def require_current_hydration(
        run_dir: Path, pointer: dict | None, hydration: AcceptedHydration):
    if hydration is None:
        invalid("B13_EXECUTION_CACHE_REQUIRED")
    student = hydration.student
    if (pointer is None
            or sha(canonical(pointer)) != hydration.pointer_sha256
            or pointer.get("manifest_sha256") != hydration.manifest_sha256
            or pointer.get("run_id") != student.run_id
            or pointer.get("generation") != student.generation
            or pointer.get("acceptance_sha256") != hydration.acceptance_sha256
            or _acceptance_file_sha256(run_dir, hydration.manifest_sha256)
            != hydration.acceptance_file_sha256):
        invalid("B13_EXECUTION_CACHE_STALE")
    require_bamf_bundle_currentness(hydration.currentness)
    return hydration


def _new_hydration(
        run_dir: Path, pointer: dict, student: CompleteStudent,
        candidate_identity_sha256: str) -> AcceptedHydration:
    currentness = bind_bamf_bundle_currentness(
        Path(run_dir) / "bamf-bundles" / pointer["manifest_sha256"],
        expected_manifest_sha256=pointer["manifest_sha256"])
    return AcceptedHydration(
        pointer["manifest_sha256"], sha(canonical(pointer)),
        pointer["acceptance_sha256"],
        _acceptance_file_sha256(run_dir, pointer["manifest_sha256"]), student,
        canonical(dict(student.correction_frontier)), candidate_identity_sha256,
        currentness)


def current_hydration_locked(
        lock, hydrations, run_dir: Path, key: str, pointer: dict | None, *,
        metrics=None) -> tuple[AcceptedHydration, bool]:
    with lock:
        retained = hydrations.get(key)
    if (retained is not None and pointer is not None
            and pointer.get("manifest_sha256") == retained.manifest_sha256):
        return require_current_hydration(run_dir, pointer, retained), False
    accepted_parent = (
        (retained.manifest_sha256, retained.student)
        if retained is not None else None)
    pointer, student = _read_accepted_locked(
        run_dir, accepted_parent=accepted_parent)
    _require_initial_foundation_authority(run_dir, student)
    identity = _published_in_memory_identity_locked(
        run_dir, student, pointer, accepted_parent=accepted_parent,
        acceptance_verified=True)
    if metrics is not None:
        metrics.increment("full_candidate_identity_hashes")
    hydration = _new_hydration(
        run_dir, pointer, student, identity.candidate_identity_sha256)
    if metrics is not None:
        metrics.increment("bundle_tree_scans", 2)
    with lock:
        hydrations[key] = hydration
    return hydration, True


def new_publication_parent(
        run_dir: Path, hydration: AcceptedHydration) -> AcceptedPublicationParent:
    result = object.__new__(AcceptedPublicationParent)
    currentness = require_bamf_bundle_currentness(hydration.currentness)
    for name, value in (
        ("manifest_sha256", hydration.manifest_sha256),
        ("acceptance_sha256", hydration.acceptance_sha256),
        ("student", hydration.student),
        ("_pointer_sha256", hydration.pointer_sha256),
        ("_acceptance_file_sha256", hydration.acceptance_file_sha256),
        ("_hydration", hydration), ("_currentness", currentness),
        ("_issuance", _PUBLICATION_PARENT_ISSUER),
    ):
        object.__setattr__(result, name, value)
    return result


def require_publication_parent_locked(
        lock, hydrations, run_dir: Path, pointer: dict | None,
        witness: AcceptedPublicationParent):
    run_dir = Path(run_dir).resolve()
    key = str(run_dir)
    if (type(witness) is not AcceptedPublicationParent
            or getattr(witness, "_issuance", None) is not _PUBLICATION_PARENT_ISSUER):
        invalid("B13_PUBLICATION_PARENT_REQUIRED")
    with lock:
        retained = hydrations.get(key)
    if retained is not witness._hydration:
        invalid("B13_PUBLICATION_PARENT_STALE")
    if (pointer is None
            or sha(canonical(pointer)) != witness._pointer_sha256
            or pointer.get("manifest_sha256") != witness.manifest_sha256
            or pointer.get("acceptance_sha256") != witness.acceptance_sha256
            or _acceptance_file_sha256(run_dir, witness.manifest_sha256)
            != witness._acceptance_file_sha256):
        invalid("B13_PUBLICATION_PARENT_STALE")
    require_bamf_bundle_currentness(witness._currentness)
    return witness


__all__ = ("AcceptedHydration", "AcceptedPublicationParent")
