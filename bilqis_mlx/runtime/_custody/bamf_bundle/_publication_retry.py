"""Exact generation-zero retry and interrupted-pointer recovery."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest

from .records import (
    BAMF_POINTER_SCHEMA, BamfBundleCandidate, canonical, invalid, sidecar_records,
)
from ._publication_storage import ACCEPTANCE_DIR


def _same_initial_candidate(student, candidate: BamfBundleCandidate) -> bool:
    return (
        student.run_id == candidate.run_id
        and student.generation == candidate.generation == 0
        and student.parent_manifest_sha256 is candidate.parent_manifest_sha256 is None
        and student.implementation_sha256 == candidate.implementation_sha256
        and student.topology == candidate.topology
        and student.extents == candidate.extents
        and candidate_identity_digest(student.retained_state)
        == candidate_identity_digest(candidate.retained_state)
        and student.provenance == candidate.provenance
        and student.transition == candidate.transition
        and student.run_identity == candidate.run_identity
        and student.optimizer_hyperparameters == candidate.optimizer_hyperparameters
        and sidecar_records(student) == sidecar_records(candidate)
    )


def _recovery_pointer(run_dir: Path, manifest_sha256: str, prepared) -> dict:
    return {
        "schema": BAMF_POINTER_SCHEMA,
        "run_id": prepared.candidate.run_id,
        "generation": 0,
        "parent_manifest_sha256": None,
        "bundle": f"bamf-bundles/{manifest_sha256}",
        "manifest_sha256": manifest_sha256,
        "acceptance_sha256": prepared.binding.digest,
    }


def _unpointed_initial_generation_retry(
        run_dir: Path, prepared, *, load_bundle, require_published_acceptance,
        atomic_pointer, reconcile):
    """Recover an exact durable genesis whose pointer install was interrupted."""
    acceptance_root = run_dir / ACCEPTANCE_DIR
    if not acceptance_root.exists() and not acceptance_root.is_symlink():
        return None
    if acceptance_root.is_symlink() or not acceptance_root.is_dir():
        invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
    entries = sorted(acceptance_root.iterdir(), key=lambda path: path.name)
    if not entries:
        return None
    expected = canonical(prepared.binding.to_record())
    exact = []
    for path in entries:
        if path.is_symlink() or not path.is_file():
            invalid(DataPlaneError.BUNDLE_ENTRY_UNSAFE)
        if path.read_bytes() == expected:
            exact.append(path)
    if len(exact) != 1:
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    manifest_sha256 = exact[0].stem
    if exact[0].name != f"{manifest_sha256}.json":
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    target = run_dir / "bamf-bundles" / manifest_sha256
    student = load_bundle(target, expected_manifest_sha256=manifest_sha256)
    pointer = _recovery_pointer(run_dir, manifest_sha256, prepared)
    acceptance = require_published_acceptance(run_dir, pointer, student)
    if (acceptance.digest != prepared.binding.digest
            or not _same_initial_candidate(student, prepared.candidate)):
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    atomic_pointer(run_dir / "bamf-state.json", pointer)
    reconcile(run_dir, student)
    return pointer


def existing_initial_generation_retry(
        run_dir: Path, candidate: BamfBundleCandidate, prepared, *,
        pointer_lock, read_pointer, load_generation_locked,
        require_published_acceptance, load_bundle, atomic_pointer, reconcile):
    """Converge only the exact live-capability genesis already sealed by B13."""
    run_dir = Path(run_dir)
    pointer_path = run_dir / "bamf-state.json"
    with pointer_lock(run_dir):
        current = read_pointer(pointer_path)
        if current is None:
            return _unpointed_initial_generation_retry(
                run_dir, prepared, load_bundle=load_bundle,
                require_published_acceptance=require_published_acceptance,
                atomic_pointer=atomic_pointer, reconcile=reconcile)
        if (current.get("schema") != BAMF_POINTER_SCHEMA
                or current.get("run_id") != candidate.run_id
                or current.get("generation") != 0
                or current.get("parent_manifest_sha256") is not None
                or current.get("acceptance_sha256") != prepared.binding.digest):
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        student, locked_pointer = load_generation_locked(pointer_path)
        if locked_pointer != current:
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        acceptance = require_published_acceptance(run_dir, current, student)
        if (acceptance.digest != prepared.binding.digest
                or not _same_initial_candidate(student, candidate)):
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        return current
