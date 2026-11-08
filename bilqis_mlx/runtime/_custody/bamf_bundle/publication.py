"""Crash-idempotent, serialized B13.1 pointer publication and outbox recovery."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError
from bilqis_mlx.learning.atlas_acceptance import AcceptedCandidateBinding

from .codec import load_bamf_bundle, save_bamf_bundle
from .records import (
    BAMF_POINTER_SCHEMA, BamfBundleCandidate, CompleteStudent, invalid,
    sidecar_records,
)
from ._publication_authority import (
    _UNBOUND_RETRY,
    load_generation_locked as _load_generation_locked_impl,
    parent_acceptance_for_publication as _parent_acceptance_for_publication_impl,
    require_acceptance as _require_acceptance,
    require_accepted_parent as _require_accepted_parent_impl,
    require_published_acceptance as _require_published_acceptance_impl,
    validate_parent_transition as _validate_parent_transition_impl,
)
from ._publication_events import record_bamf_rejection
from ._publication_storage import (
    ACCEPTANCE_DIR, _acceptance_path, _atomic_pointer, _live_bundle_manifest,
    _pointer_lock, _read_pointer, _require_bundle_root, _require_run_root,
    _stage, _write_acceptance,
)


def reconcile_bamf_outbox(
        run_dir: Path, student: CompleteStudent, *, publish_missing=True) -> bool:
    """Reconcile while the caller holds the generation pointer writer lock."""
    from bilqis_mlx.runtime import checkpoints
    return checkpoints._reconcile_delivery_outbox(
        Path(run_dir), {"run_id": student.run_id, "generation": student.generation,
                        "delivery_outbox": list(student.outbox)},
        publish_missing=publish_missing)


def _require_published_acceptance(
        run_dir: Path, pointer: dict, student: CompleteStudent):
    return _require_published_acceptance_impl(
        run_dir, pointer, student,
        load_bundle=load_bamf_bundle, live_manifest=_live_bundle_manifest)


def _load_generation_locked(pointer_path: Path) -> tuple[CompleteStudent, dict]:
    return _load_generation_locked_impl(
        pointer_path, read_pointer=_read_pointer,
        live_manifest=_live_bundle_manifest, load_bundle=load_bamf_bundle)


def _parent_acceptance_for_publication(
        run_dir: Path, candidate: BamfBundleCandidate,
        accepted: AcceptedCandidateBinding):
    return _parent_acceptance_for_publication_impl(
        run_dir, candidate, accepted,
        pointer_lock=_pointer_lock, read_pointer=_read_pointer,
        live_manifest=_live_bundle_manifest, load_bundle=load_bamf_bundle,
        require_published_acceptance=_require_published_acceptance)


def _save_publication_bundle(candidate: BamfBundleCandidate, stage: Path,
                             parent_acceptance, *, reserve_gib: float):
    """Use the acceptance-bound writer when available; preserve pinned old-writer replay."""
    if parent_acceptance is _UNBOUND_RETRY:
        return save_bamf_bundle(candidate, stage, reserve_gib=reserve_gib)
    try:
        return save_bamf_bundle(
            candidate, stage, reserve_gib=reserve_gib,
            parent_acceptance_sha256=parent_acceptance)
    except TypeError as exc:
        if "unexpected keyword argument 'parent_acceptance_sha256'" not in str(exc):
            raise
        if candidate.generation > 0:
            invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
        return save_bamf_bundle(candidate, stage, reserve_gib=reserve_gib)


def publish_bamf_generation(
        run_dir: Path, candidate: BamfBundleCandidate, *,
        acceptance: AcceptedCandidateBinding | None = None,
        reserve_gib: float = 100.0) -> dict:
    """Publish one retained successor; generation zero has a separate B13 gate."""
    accepted = _require_acceptance(candidate, acceptance)
    return _publish_authorized_generation(
        run_dir, candidate, accepted, reserve_gib=reserve_gib)


def _existing_initial_generation_retry(
        run_dir: Path, candidate: BamfBundleCandidate, prepared):
    """Converge an exact sealed genesis retry without depending on mutable upstream."""
    run_dir = Path(run_dir)
    pointer_path = run_dir / "bamf-state.json"
    with _pointer_lock(run_dir):
        current = _read_pointer(pointer_path)
        if current is None:
            return None
        if (current.get("schema") != BAMF_POINTER_SCHEMA
                or current.get("run_id") != candidate.run_id
                or current.get("generation") != 0
                or current.get("parent_manifest_sha256") is not None
                or current.get("acceptance_sha256") != prepared.binding.digest):
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        student, locked_pointer = _load_generation_locked(pointer_path)
        if locked_pointer != current:
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        acceptance = _require_published_acceptance(run_dir, current, student)
        if (acceptance.digest != prepared.binding.digest
                or student.implementation_sha256 != candidate.implementation_sha256
                or student.topology != candidate.topology
                or student.extents != candidate.extents
                or student.provenance != candidate.provenance
                or student.transition != candidate.transition
                or student.run_identity != candidate.run_identity
                or student.optimizer_hyperparameters != candidate.optimizer_hyperparameters
                or sidecar_records(student) != sidecar_records(candidate)):
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        return current


def _publish_authorized_generation(
        run_dir: Path, candidate: BamfBundleCandidate, authority, *,
        reserve_gib: float) -> dict:
    """Shared crash-safe transaction after generation-specific authority validates."""
    if candidate.generation == 0:
        from .genesis import (
            PreparedInitialGeneration, validate_initial_generation_preparation,
        )
        if (type(authority) is not PreparedInitialGeneration
                or authority.candidate is not candidate):
            invalid("BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
        authority.__post_init__()
        existing = _existing_initial_generation_retry(run_dir, candidate, authority)
        if existing is not None:
            return existing
        validate_initial_generation_preparation(authority)
        authority = authority.binding
    else:
        authority = _require_acceptance(candidate, authority)
    run_dir = Path(run_dir)
    parent_acceptance = _parent_acceptance_for_publication(
        run_dir, candidate, authority)
    stage = _stage(run_dir)
    try:
        manifest = _save_publication_bundle(
            candidate, stage, parent_acceptance, reserve_gib=reserve_gib)
        digest = manifest["manifest_sha256"]
        target = _require_bundle_root(run_dir, create=True) / digest
        pointer_path = run_dir / "bamf-state.json"
        with _pointer_lock(run_dir):
            current = _read_pointer(pointer_path)
            if candidate.generation > 0:
                _require_accepted_parent_impl(
                    run_dir, candidate, authority, load_bundle=load_bamf_bundle)
            if current is not None and current["generation"] == candidate.generation:
                if (current["run_id"] != candidate.run_id
                        or current["manifest_sha256"] != digest
                        or current["parent_manifest_sha256"] != candidate.parent_manifest_sha256
                        or current["schema"] != BAMF_POINTER_SCHEMA
                        or current["acceptance_sha256"] != authority.digest):
                    invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
                shutil.rmtree(stage)
                student = load_bamf_bundle(
                    run_dir / current["bundle"], expected_manifest_sha256=digest)
                _write_acceptance(run_dir, digest, authority)
                reconcile_bamf_outbox(run_dir, student)
                return current
            _validate_parent_transition_impl(
                run_dir, current, candidate,
                load_bundle=load_bamf_bundle, reconcile=reconcile_bamf_outbox)
            if candidate.generation > 0:
                parent = load_bamf_bundle(
                    run_dir / current["bundle"],
                    expected_manifest_sha256=current["manifest_sha256"])
                live_parent_acceptance = _require_published_acceptance(
                    run_dir, current, parent)
                if live_parent_acceptance.digest != parent_acceptance:
                    invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_dir():
                    invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
                load_bamf_bundle(target, expected_manifest_sha256=digest)
                shutil.rmtree(stage)
            else:
                stage.rename(target)
                directory = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            _write_acceptance(run_dir, digest, authority)
            pointer = {
                "schema": BAMF_POINTER_SCHEMA, "run_id": candidate.run_id,
                "generation": candidate.generation,
                "parent_manifest_sha256": candidate.parent_manifest_sha256,
                "bundle": str(target.relative_to(run_dir)),
                "manifest_sha256": digest, "acceptance_sha256": authority.digest,
            }
            _atomic_pointer(pointer_path, pointer)
            student = load_bamf_bundle(target, expected_manifest_sha256=digest)
            reconcile_bamf_outbox(run_dir, student)
            return pointer
    except BaseException:
        if stage.exists() and stage.is_dir() and not stage.is_symlink():
            shutil.rmtree(stage)
        raise


def load_bamf_generation_authority(
        pointer_path: Path) -> tuple[CompleteStudent, str]:
    """Read current accepted B13 authority without mutating delivery state."""
    pointer_path = Path(pointer_path)
    with _pointer_lock(pointer_path.parent):
        student, pointer = _load_generation_locked(pointer_path)
        _require_published_acceptance(pointer_path.parent, pointer, student)
        return student, pointer["manifest_sha256"]


def load_bamf_generation(
        pointer_path: Path, *, publish_missing_outbox: bool = True) -> CompleteStudent:
    pointer_path = Path(pointer_path)
    with _pointer_lock(pointer_path.parent):
        student, _ = _load_generation_locked(pointer_path)
        reconcile_bamf_outbox(
            pointer_path.parent, student, publish_missing=publish_missing_outbox)
        return student
