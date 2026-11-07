"""Crash-idempotent, serialized B13.1 pointer publication and outbox recovery."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError, data_plane
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    ACCEPTANCE_SCHEMA, AcceptedCandidateBinding, candidate_identity_digest,
)
from .codec import load_bamf_bundle, save_bamf_bundle
from .package_import_transition import (
    is_package_import_transition, require_issued_package_import_transition,
)
from .records import (
    BAMF_POINTER_SCHEMA, BamfBundleCandidate, CompleteStudent, canonical, invalid, sha,
)

from ._publication_storage import (
    ACCEPTANCE_DIR, _acceptance_path, _atomic_pointer, _live_bundle_manifest,
    _pointer_lock, _read_pointer, _require_bundle_root, _require_run_root,
    _stage, _write_acceptance,
)

def reconcile_bamf_outbox(run_dir: Path, student: CompleteStudent, *, publish_missing=True) -> bool:
    """Reconcile while the caller holds the generation pointer writer lock."""
    from bilqis_mlx.runtime import checkpoints
    return checkpoints._reconcile_delivery_outbox(
        Path(run_dir), {"run_id": student.run_id, "generation": student.generation,
                        "delivery_outbox": list(student.outbox)},
        publish_missing=publish_missing)


def record_bamf_rejection(run_dir: Path, student: CompleteStudent, evidence: dict) -> str:
    """Publish idempotent failure evidence without minting or mutating a generation."""
    if type(student) is not CompleteStudent or not isinstance(evidence, dict) or not evidence:
        invalid("BAMF_REJECTION_EVIDENCE_INVALID")
    from bilqis_mlx.runtime import checkpoint_outbox, checkpoints
    run_dir = Path(run_dir)
    pointer_path = run_dir / "bamf-state.json"
    with _pointer_lock(run_dir):
        pointer = _read_pointer(pointer_path)
        if (pointer is None or pointer["run_id"] != student.run_id
                or pointer["generation"] != student.generation):
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        manifest = _live_bundle_manifest(run_dir, pointer)
        optimizer_step = manifest.get("optimizer", {}).get("step") if isinstance(manifest, dict) else None
        if type(optimizer_step) is not int or optimizer_step != manifest.get("tensors", {}).get("optimizer_step"):
            invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
        event = {
            "event": "BAMF_CANDIDATE_REJECTED",
            "generation": pointer["generation"],
            "student_manifest_sha256": pointer["manifest_sha256"],
            "optimizer_step": optimizer_step,
            "evidence": dict(evidence),
        }
        record = {"run_id": pointer["run_id"], "generation": pointer["generation"]}
        outbox = checkpoint_outbox.with_delivery_outbox(record, (event,))["delivery_outbox"]
        receipt = {
            "schema": "bilqis.mlx.bamf-rejection-receipt/v1",
            "run_id": student.run_id, "generation": student.generation,
            "student_manifest_sha256": pointer["manifest_sha256"], "event": outbox[0],
        }
        raw = canonical(receipt)
        digest = sha(raw)
        data_plane().put_object(digest, raw)
        checkpoints._reconcile_delivery_outbox(
            run_dir, {**record, "delivery_outbox": outbox})
        return digest


def _validate_parent_transition(run_dir: Path, pointer: dict | None, candidate: BamfBundleCandidate) -> None:
    if pointer is None:
        if candidate.generation != 0 or candidate.parent_manifest_sha256 is not None:
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        return
    if (pointer["run_id"] != candidate.run_id
            or pointer["generation"] != candidate.generation - 1
            or pointer["manifest_sha256"] != candidate.parent_manifest_sha256):
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    parent = load_bamf_bundle(
        run_dir / pointer["bundle"], expected_manifest_sha256=pointer["manifest_sha256"])
    if (parent.run_id != pointer["run_id"]
            or parent.generation != pointer["generation"]
            or parent.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    parent_step = parent.retained_state.optimizer_step
    candidate_step = candidate.retained_state.optimizer_step
    if is_package_import_transition(candidate.transition):
        require_issued_package_import_transition(candidate.transition)
        if (parent.topology.digest != candidate.topology.digest
                or parent.extents.digest != candidate.extents.digest
                or candidate_step != parent_step):
            invalid("BAMF_GENERATION_TRANSITION_INVALID")
    else:
        kind = ("MODEL_SWAP" if parent.topology.digest != candidate.topology.digest else
                "PARAMETER_EXTENSION" if parent.extents.digest != candidate.extents.digest else
                "RETAINED_CANDIDATE")
        if (candidate_step < parent_step or
                (kind == "RETAINED_CANDIDATE" and candidate_step <= parent_step)):
            invalid("BAMF_REJECTED_CANDIDATE_NOT_GENERATION")
        if candidate.transition.get("kind") != kind:
            invalid("BAMF_GENERATION_TRANSITION_INVALID")
    reconcile_bamf_outbox(run_dir, parent)


def _require_acceptance(candidate: BamfBundleCandidate,
                         acceptance: AcceptedCandidateBinding | None) -> AcceptedCandidateBinding:
    """Publication is not acceptance: the retention owner must have accepted it."""
    if candidate.generation == 0:
        invalid("BAMF_INITIAL_GENERATION_BOOTSTRAP_REQUIRED")
    if type(acceptance) is not AcceptedCandidateBinding:
        invalid("BAMF_GENERATION_ACCEPTANCE_REQUIRED")
    if (acceptance.schema_version != ACCEPTANCE_SCHEMA
            or acceptance.run_id != candidate.run_id
            or acceptance.generation != candidate.generation
            or acceptance.feature_sha256 != candidate.extents.factor_map_digest
            or acceptance.optimizer_step != candidate.retained_state.optimizer_step
            or acceptance.candidate_identity_sha256
            != candidate_identity_digest(candidate.retained_state)
            or acceptance.step_proof_sha256 != tuple(
                proof.digest for proof in candidate.retained_state.step_proofs)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    return acceptance


def _require_accepted_parent(run_dir: Path, candidate: BamfBundleCandidate,
                             acceptance: AcceptedCandidateBinding) -> None:
    """Verify the C05 parent identity against immutable B13 parent custody."""
    if candidate.generation == 0:
        return  # Genesis admission is a distinct upstream source/bootstrap gate.
    parent_sha = candidate.parent_manifest_sha256
    if parent_sha is None:
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    parent = load_bamf_bundle(
        run_dir / "bamf-bundles" / parent_sha,
        expected_manifest_sha256=parent_sha)
    if (parent.run_id != candidate.run_id
            or parent.generation + 1 != candidate.generation
            or candidate.run_identity != parent.run_identity
            or acceptance.parent_candidate_identity_sha256
            != candidate_identity_digest(parent.retained_state)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")


def publish_bamf_generation(run_dir: Path, candidate: BamfBundleCandidate, *,
                            acceptance: AcceptedCandidateBinding | None = None,
                            reserve_gib: float = 100.0) -> dict:
    """Publish one retained successor; generation zero has a separate B13 gate."""
    accepted = _require_acceptance(candidate, acceptance)
    return _publish_authorized_generation(
        run_dir, candidate, accepted, reserve_gib=reserve_gib)


def _publish_authorized_generation(run_dir: Path, candidate: BamfBundleCandidate,
                                   authority, *, reserve_gib: float) -> dict:
    """Shared crash-safe transaction after the generation owner authenticates authority."""
    if candidate.generation == 0:
        from .genesis import (
            PreparedInitialGeneration, validate_initial_generation_preparation,
        )
        if (type(authority) is not PreparedInitialGeneration
                or authority.candidate is not candidate):
            invalid("BAMF_INITIAL_GENERATION_PREPARATION_REQUIRED")
        validate_initial_generation_preparation(authority)
        authority = authority.binding
    else:
        authority = _require_acceptance(candidate, authority)
    run_dir = Path(run_dir)
    stage = _stage(run_dir)
    try:
        manifest = save_bamf_bundle(candidate, stage, reserve_gib=reserve_gib)
        digest = manifest["manifest_sha256"]
        target = _require_bundle_root(run_dir, create=True) / digest
        pointer_path = run_dir / "bamf-state.json"
        with _pointer_lock(run_dir):
            current = _read_pointer(pointer_path)
            if candidate.generation > 0:
                _require_accepted_parent(run_dir, candidate, authority)
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
            _validate_parent_transition(run_dir, current, candidate)
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


def _load_generation_locked(pointer_path: Path) -> tuple[CompleteStudent, dict]:
    pointer = _read_pointer(pointer_path)
    if pointer is None:
        invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)
    _live_bundle_manifest(pointer_path.parent, pointer)
    student = load_bamf_bundle(
        pointer_path.parent / "bamf-bundles" / pointer["manifest_sha256"],
        expected_manifest_sha256=pointer["manifest_sha256"])
    if (student.run_id != pointer["run_id"] or student.generation != pointer["generation"]
            or student.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return student, pointer


def _require_published_acceptance(
        run_dir: Path, pointer: dict, student: CompleteStudent) -> AcceptedCandidateBinding:
    """Authenticate the acceptance receipt bound by one live BAMF pointer."""
    if pointer.get("schema") != BAMF_POINTER_SCHEMA:
        invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
    acceptance_path = (
        Path(run_dir) / ACCEPTANCE_DIR / f"{pointer['manifest_sha256']}.json")
    if acceptance_path.is_symlink() or not acceptance_path.is_file():
        invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
    try:
        record = json.loads(acceptance_path.read_bytes())
        if student.generation == 0:
            from .genesis import (
                InitialGenerationBinding,
                validate_parsed_initial_generation_binding,
            )
            acceptance = InitialGenerationBinding.from_record(record)
            validate_parsed_initial_generation_binding(
                student, acceptance, pointer["acceptance_sha256"])
            return acceptance
        acceptance = AcceptedCandidateBinding.from_record(record)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, BilqisError):
        invalid("BAMF_GENERATION_ACCEPTANCE_INVALID")
    if (acceptance.digest != pointer["acceptance_sha256"]
            or acceptance.run_id != student.run_id
            or acceptance.generation != student.generation
            or acceptance.feature_sha256 != student.extents.factor_map_digest
            or acceptance.optimizer_step != student.retained_state.optimizer_step
            or acceptance.candidate_identity_sha256
            != candidate_identity_digest(student.retained_state)
            or acceptance.step_proof_sha256 != tuple(
                proof.digest for proof in student.retained_state.step_proofs)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    parent_sha = student.parent_manifest_sha256
    if parent_sha is None:
        invalid("BAMF_RUN_IDENTITY_DRIFT")
    parent = load_bamf_bundle(
        Path(run_dir) / "bamf-bundles" / parent_sha,
        expected_manifest_sha256=parent_sha)
    if (parent.run_id != student.run_id
            or parent.generation + 1 != student.generation
            or parent.run_identity != student.run_identity):
        invalid("BAMF_RUN_IDENTITY_DRIFT")
    return acceptance


def load_bamf_generation_authority(pointer_path: Path) -> tuple[CompleteStudent, str]:
    """Read current accepted B13 authority without mutating delivery state."""
    pointer_path = Path(pointer_path)
    with _pointer_lock(pointer_path.parent):
        student, pointer = _load_generation_locked(pointer_path)
        _require_published_acceptance(pointer_path.parent, pointer, student)
        return student, pointer["manifest_sha256"]


def load_bamf_generation(pointer_path: Path, *, publish_missing_outbox: bool = True) -> CompleteStudent:
    pointer_path = Path(pointer_path)
    with _pointer_lock(pointer_path.parent):
        student, _ = _load_generation_locked(pointer_path)
        reconcile_bamf_outbox(
            pointer_path.parent, student, publish_missing=publish_missing_outbox)
        return student
