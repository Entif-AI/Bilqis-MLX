"""Crash-idempotent, serialized B13.1 pointer publication and outbox recovery."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError
from bilqis_mlx.learning.atlas_acceptance import AcceptedCandidateBinding

from ..codec import load_bamf_bundle, save_bamf_bundle
from ..records import (
    BAMF_POINTER_SCHEMA, BamfBundleCandidate, CompleteStudent, invalid,
)
from .authority import (
    _UNBOUND_RETRY,
    load_generation_locked as _load_generation_locked_impl,
    parent_acceptance_for_publication as _parent_acceptance_for_publication_impl,
    require_acceptance as _require_acceptance,
    require_accepted_parent as _require_accepted_parent_impl,
    require_published_acceptance as _require_published_acceptance_impl,
    validate_parent_transition as _validate_parent_transition_impl,
)
from .events import record_bamf_rejection
from .genesis_trust import publish_initial_generation_trust_root
from .retry import existing_initial_generation_retry
from .storage import (
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
    return existing_initial_generation_retry(
        run_dir, candidate, prepared,
        pointer_lock=_pointer_lock, read_pointer=_read_pointer,
        load_generation_locked=_load_generation_locked,
        require_published_acceptance=_require_published_acceptance,
        load_bundle=load_bamf_bundle, atomic_pointer=_atomic_pointer,
        reconcile=reconcile_bamf_outbox)


def _publish_authorized_generation(
        run_dir: Path, candidate: BamfBundleCandidate, authority, *,
        reserve_gib: float) -> dict:
    """Shared crash-safe transaction after generation-specific authority validates."""
    prepared = None
    initial_preparation = None
    if candidate.generation == 0:
        from ..genesis import (
            PreparedInitialGeneration, validate_initial_generation_binding,
            validate_initial_generation_preparation,
        )
        if (type(authority) is not PreparedInitialGeneration
                or authority.candidate is not candidate):
            invalid("BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
        prepared = authority
        authority.__post_init__()
        validate_initial_generation_binding(candidate, authority.binding)
        existing = _existing_initial_generation_retry(run_dir, candidate, authority)
        if existing is not None:
            return existing
        validate_initial_generation_preparation(authority)
        initial_preparation = authority
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
                if prepared is not None:
                    publish_initial_generation_trust_root(prepared, digest)
                _write_acceptance(run_dir, digest, authority)
                reconcile_bamf_outbox(run_dir, student)
                return current
            if initial_preparation is not None:
                validate_initial_generation_preparation(initial_preparation)
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
            if prepared is not None:
                publish_initial_generation_trust_root(prepared, digest)
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
