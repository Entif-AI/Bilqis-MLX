"""Generation acceptance and lineage checks used by B13 publication."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    ACCEPTANCE_SCHEMA, AcceptedCandidateBinding, candidate_identity_digest,
)

from .package_import_transition import (
    is_package_import_transition, require_issued_package_import_transition,
)
from .records import (
    ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA, BAMF_POINTER_SCHEMA,
    BamfBundleCandidate, CompleteStudent, invalid,
)
from ._publication_storage import ACCEPTANCE_DIR


_UNBOUND_RETRY = object()


def require_acceptance(
        candidate: BamfBundleCandidate,
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


def validate_parent_transition(
        run_dir: Path, pointer: dict | None, candidate: BamfBundleCandidate, *,
        load_bundle, reconcile) -> None:
    if pointer is None:
        if candidate.generation != 0 or candidate.parent_manifest_sha256 is not None:
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        return
    if (pointer["run_id"] != candidate.run_id
            or pointer["generation"] != candidate.generation - 1
            or pointer["manifest_sha256"] != candidate.parent_manifest_sha256):
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    parent = load_bundle(
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
    reconcile(run_dir, parent)


def require_accepted_parent(
        run_dir: Path, candidate: BamfBundleCandidate,
        acceptance: AcceptedCandidateBinding, *, load_bundle) -> None:
    """Verify the C05 parent identity against immutable B13 parent custody."""
    if candidate.generation == 0:
        return
    parent_sha = candidate.parent_manifest_sha256
    if parent_sha is None:
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    parent = load_bundle(
        run_dir / "bamf-bundles" / parent_sha,
        expected_manifest_sha256=parent_sha)
    if (parent.run_id != candidate.run_id
            or parent.generation + 1 != candidate.generation
            or (parent.run_identity is not None
                and parent.run_identity != candidate.run_identity)
            or acceptance.parent_candidate_identity_sha256
            != candidate_identity_digest(parent.retained_state)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")


def parent_acceptance_for_publication(
        run_dir: Path, candidate: BamfBundleCandidate,
        accepted: AcceptedCandidateBinding, *, pointer_lock, read_pointer,
        live_manifest, load_bundle, require_published_acceptance):
    """Read the exact parent acceptance that the new immutable manifest must bind."""
    pointer_path = Path(run_dir) / "bamf-state.json"
    with pointer_lock(run_dir):
        current = read_pointer(pointer_path)
        if current is None:
            if candidate.generation != 0 or candidate.parent_manifest_sha256 is not None:
                invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
            return None
        if current["generation"] == candidate.generation:
            if (current["run_id"] != candidate.run_id
                    or current["parent_manifest_sha256"] != candidate.parent_manifest_sha256
                    or current.get("acceptance_sha256") != accepted.digest):
                invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
            manifest = live_manifest(run_dir, current)
            if manifest.get("schema") != ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA:
                return _UNBOUND_RETRY
            return manifest.get("parent_acceptance_sha256")
        if (current["run_id"] != candidate.run_id
                or current["generation"] != candidate.generation - 1
                or current["manifest_sha256"] != candidate.parent_manifest_sha256):
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        parent = load_bundle(
            run_dir / current["bundle"],
            expected_manifest_sha256=current["manifest_sha256"])
        require_published_acceptance(run_dir, current, parent)
        return current["acceptance_sha256"]


def load_generation_locked(
        pointer_path: Path, *, read_pointer, live_manifest,
        load_bundle) -> tuple[CompleteStudent, dict]:
    pointer = read_pointer(pointer_path)
    if pointer is None:
        invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)
    live_manifest(pointer_path.parent, pointer)
    student = load_bundle(
        pointer_path.parent / "bamf-bundles" / pointer["manifest_sha256"],
        expected_manifest_sha256=pointer["manifest_sha256"])
    if (student.run_id != pointer["run_id"] or student.generation != pointer["generation"]
            or student.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    return student, pointer


def require_published_acceptance(
        run_dir: Path, pointer: dict, student: CompleteStudent, *,
        load_bundle, live_manifest):
    """Authenticate the generation-specific acceptance bound by one live pointer."""
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
    if (acceptance.schema_version != ACCEPTANCE_SCHEMA
            or acceptance.digest != pointer["acceptance_sha256"]
            or acceptance.run_id != student.run_id
            or acceptance.generation != student.generation
            or acceptance.feature_sha256 != student.extents.factor_map_digest
            or acceptance.optimizer_step != student.retained_state.optimizer_step
            or acceptance.candidate_identity_sha256
            != candidate_identity_digest(student.retained_state)
            or acceptance.step_proof_sha256 != tuple(
                proof.digest for proof in student.retained_state.step_proofs)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    manifest = live_manifest(run_dir, pointer)
    legacy_student = manifest.get("schema") != ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA
    parent_sha = student.parent_manifest_sha256
    if parent_sha is None:
        invalid("BAMF_RUN_IDENTITY_DRIFT")
    parent = load_bundle(
        Path(run_dir) / "bamf-bundles" / parent_sha,
        expected_manifest_sha256=parent_sha)
    if (parent.run_id != student.run_id
            or parent.generation + 1 != student.generation
            or (not legacy_student
                and parent.run_identity is not None
                and parent.run_identity != student.run_identity)):
        invalid("BAMF_RUN_IDENTITY_DRIFT")
    return acceptance
