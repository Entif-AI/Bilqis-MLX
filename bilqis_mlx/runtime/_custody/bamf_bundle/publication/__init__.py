"""Crash-idempotent, serialized B13.1 pointer publication and outbox recovery."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError
from bilqis_mlx.learning.atlas_acceptance import (
    AcceptedCandidateBinding, ParsedAcceptedCandidateBinding,
)

from ..atlas_admission import (
    AtlasAdmissionBinding, ParsedAtlasAdmissionBinding,
    require_atlas_admission_binding,
)
from ..codec import load_bamf_bundle, save_bamf_bundle
from ..records import (
    BAMF_POINTER_SCHEMA, BamfBundleCandidate, CompleteStudent, invalid,
)
from .authority import (
    _UNBOUND_RETRY,
    authenticate_current_successor_retry,
    load_generation_locked as _load_generation_locked_impl,
    parent_acceptance_for_publication as _parent_acceptance_for_publication_impl,
    require_acceptance as _require_acceptance,
    require_accepted_parent as _require_accepted_parent_impl,
    require_published_acceptance as _require_published_acceptance_impl,
    validate_parent_transition as _validate_parent_transition_impl,
)
from .events import record_bamf_rejection
from .genesis_trust import (
    publish_initial_generation_trust_root, require_initial_generation_trust_root,
    sealed_initial_generation_manifest, _stored_trust,
)
from .retry import existing_initial_generation_retry
from .storage import (
    ACCEPTANCE_DIR, _acceptance_path, _atomic_pointer, _live_bundle_manifest,
    _pointer_lock, _read_pointer, _require_bundle_root, _require_run_root,
    _stage, _write_acceptance, _write_parsed_initial_generation_acceptance,
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
        accepted):
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


def publish_atlas_admission_generation(
        run_dir: Path, candidate: BamfBundleCandidate, *,
        admission: AtlasAdmissionBinding, reserve_gib: float = 100.0) -> dict:
    """Publish one C07-authorized parameter extension through B13 custody."""
    admitted = require_atlas_admission_binding(candidate, admission)
    return _publish_authorized_generation(
        run_dir, candidate, admitted, reserve_gib=reserve_gib)


def _existing_initial_generation_retry(
        run_dir: Path, candidate: BamfBundleCandidate, prepared):
    """Converge an exact sealed genesis retry without depending on mutable upstream."""
    return existing_initial_generation_retry(
        run_dir, candidate, prepared,
        pointer_lock=_pointer_lock, read_pointer=_read_pointer,
        load_generation_locked=_load_generation_locked,
        require_published_acceptance=_require_published_acceptance,
        load_bundle=load_bamf_bundle, atomic_pointer=_atomic_pointer,
        reconcile=reconcile_bamf_outbox,
        sealed_manifest=sealed_initial_generation_manifest,
        write_acceptance=_write_acceptance)


def recover_prepared_initial_generation(run_dir: Path, prepared):
    """Converge an already sealed generation zero from the exact prepared authority."""
    return _existing_initial_generation_retry(
        Path(run_dir), prepared.candidate, prepared)


def recover_sealed_initial_generation(
        run_dir: Path, *, expected_run_id: str, expected_run_seed: int,
        expected_topology_digest: str, expected_atlas_artifact,
        expected_optimizer_hyperparameters_sha256: str):
    """Recover sealed generation zero without replaying mutable Factory authority."""
    import json
    from ..genesis import validate_initial_generation_source_authority
    from ..genesis.records import (
        INITIAL_BINDING_SCHEMA, InitialGenerationBinding,
        initial_generation_candidate_identity_digest,
        optimizer_hyperparameters_digest,
    )
    from ..records import canonical, sha

    run_dir = Path(run_dir)
    pointer_path = run_dir / "bamf-state.json"
    with _pointer_lock(run_dir):
        if _read_pointer(pointer_path) is not None:
            return None
        stored = _stored_trust(expected_run_id)
        if stored is None:
            return None
        generation, manifest_sha256, payload_sha256, raw = stored
        if generation != 0 or payload_sha256 != sha(raw):
            invalid("BAMF_INITIAL_GENERATION_TRUST_ROOT_INVALID")
        try:
            trust = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            invalid("BAMF_INITIAL_GENERATION_TRUST_ROOT_INVALID")
        target = run_dir / "bamf-bundles" / manifest_sha256
        if target.is_symlink() or not target.is_dir():
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        student = load_bamf_bundle(
            target, expected_manifest_sha256=manifest_sha256)
        identity = student.run_identity
        feature_source = student.compiler_features.get("feature_source")
        if (identity is None or student.generation != 0
                or student.run_id != expected_run_id
                or identity.run_seed != expected_run_seed
                or student.topology.digest != expected_topology_digest
                or optimizer_hyperparameters_digest(student.optimizer_hyperparameters)
                != expected_optimizer_hyperparameters_sha256
                or not isinstance(feature_source, dict)
                or feature_source.get("atlas_bundle_id")
                != expected_atlas_artifact.bundle_id
                or feature_source.get("release_sha256")
                != expected_atlas_artifact.release_sha256
                or feature_source.get("source_bundle_id")
                != expected_atlas_artifact.source_bundle_id):
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        validate_initial_generation_source_authority(student)
        fields = {
            "run_id": student.run_id,
            "generation": 0,
            "run_identity_sha256": identity.digest,
            "candidate_identity_sha256":
                initial_generation_candidate_identity_digest(student),
            "optimizer_hyperparameters_sha256":
                optimizer_hyperparameters_digest(student.optimizer_hyperparameters),
            "feature_sha256": student.extents.factor_map_digest,
            "optimizer_step": student.retained_state.optimizer_step,
            "schema_version": INITIAL_BINDING_SCHEMA,
        }
        expected_acceptance = trust.get("acceptance_sha256")
        record = {**fields, "binding_sha256": sha(canonical(fields))}
        binding = InitialGenerationBinding.from_record(record)
        if (binding.digest != expected_acceptance
                or binding.optimizer_step != 0):
            invalid("BAMF_INITIAL_GENERATION_TRUST_ROOT_INVALID")
        pointer = {
            "schema": BAMF_POINTER_SCHEMA,
            "run_id": student.run_id,
            "generation": 0,
            "parent_manifest_sha256": None,
            "bundle": f"bamf-bundles/{manifest_sha256}",
            "manifest_sha256": manifest_sha256,
            "acceptance_sha256": binding.digest,
        }
        require_initial_generation_trust_root(pointer, student, binding)
        _write_parsed_initial_generation_acceptance(
            run_dir, manifest_sha256, binding,
            expected_acceptance_sha256=expected_acceptance)
        persisted = _require_published_acceptance(run_dir, pointer, student)
        if persisted.digest != binding.digest:
            invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
        _atomic_pointer(pointer_path, pointer)
        reconcile_bamf_outbox(run_dir, student)
        return pointer


def _authorize_publication_candidate(
        run_dir: Path, candidate: BamfBundleCandidate, authority):
    """Validate generation-specific authority before entering shared publication."""
    if candidate.generation > 0:
        if type(authority) is AtlasAdmissionBinding:
            return require_atlas_admission_binding(candidate, authority), None, None
        accepted = _require_acceptance(candidate, authority)
        return accepted, None, None
    from ..genesis import (
        PreparedInitialGeneration, validate_initial_generation_binding,
        validate_initial_generation_preparation,
        validate_initial_generation_source_authority,
    )
    if (type(authority) is not PreparedInitialGeneration
            or authority.candidate is not candidate):
        invalid("BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
    authority.__post_init__()
    validate_initial_generation_binding(candidate, authority.binding)
    validate_initial_generation_source_authority(candidate)
    existing = _existing_initial_generation_retry(run_dir, candidate, authority)
    if existing is not None:
        return None, authority, existing
    validate_initial_generation_preparation(authority)
    return authority.binding, authority, None


def _require_successor_source_authority(run_dir, parent, child, authority):
    from ..source_authority_custody import require_source_authority_successor_inheritance

    trusted = require_source_authority_successor_inheritance(
        run_dir,
        parent.correction_frontier,
        child.correction_frontier,
        allow_historical_anchor=(
            type(authority) is AcceptedCandidateBinding
            and child.transition.get("kind") == "RETAINED_CANDIDATE"),
    )
    trusted_digest = trusted.digest if trusted is not None else None
    if trusted_digest != child.correction_frontier.get(
            "source_authority_registry_sha256"):
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH")
    return trusted


def _require_retry_acceptance_family(authority, persisted) -> None:
    if type(authority) is AcceptedCandidateBinding:
        valid = isinstance(persisted, ParsedAcceptedCandidateBinding)
    elif type(authority) is AtlasAdmissionBinding:
        valid = isinstance(persisted, ParsedAtlasAdmissionBinding)
    else:
        valid = False
    if (not valid or persisted.digest != authority.digest
            or persisted.schema_version != authority.schema_version):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")


def _reconcile_already_pointed_retry(
        run_dir, current, candidate, authority, prepared, digest, stage):
    if (current["run_id"] != candidate.run_id
            or current["manifest_sha256"] != digest
            or current["parent_manifest_sha256"] != candidate.parent_manifest_sha256
            or current["schema"] != BAMF_POINTER_SCHEMA
            or current["acceptance_sha256"] != authority.digest):
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    student = load_bamf_bundle(
        run_dir / current["bundle"], expected_manifest_sha256=digest)
    if prepared is not None:
        require_initial_generation_trust_root(current, student, authority)
    else:
        parent, persisted = authenticate_current_successor_retry(
            run_dir, current, candidate, student,
            load_bundle=load_bamf_bundle,
            require_published_acceptance=_require_published_acceptance,
        )
        _require_retry_acceptance_family(authority, persisted)
        _require_successor_source_authority(run_dir, parent, student, authority)
    shutil.rmtree(stage)
    _write_acceptance(run_dir, digest, authority)
    reconcile_bamf_outbox(run_dir, student)
    return current


def _publish_authorized_generation(
        run_dir: Path, candidate: BamfBundleCandidate, authority, *,
        reserve_gib: float) -> dict:
    """Shared crash-safe transaction after generation-specific authority validates."""
    authority, prepared, existing = _authorize_publication_candidate(
        run_dir, candidate, authority)
    if existing is not None:
        return existing
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
            if current is not None and current["generation"] == candidate.generation:
                return _reconcile_already_pointed_retry(
                    run_dir, current, candidate, authority, prepared, digest, stage)
            if prepared is not None:
                from ..genesis import validate_initial_generation_preparation
                validate_initial_generation_preparation(prepared)
            parent = _validate_parent_transition_impl(
                run_dir, current, candidate,
                load_bundle=load_bamf_bundle, reconcile=reconcile_bamf_outbox)
            if candidate.generation > 0:
                if parent is None:
                    invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
                _require_successor_source_authority(
                    run_dir, parent, candidate, authority)
                _require_accepted_parent_impl(
                    run_dir, candidate, authority, load_bundle=load_bamf_bundle)
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
                publish_initial_generation_trust_root(run_dir, prepared, digest)
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
