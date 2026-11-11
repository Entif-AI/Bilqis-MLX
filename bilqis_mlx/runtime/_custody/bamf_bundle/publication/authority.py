"""Generation acceptance and lineage checks used by B13 publication."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    ACCEPTANCE_SCHEMA, MOTIF_ACCEPTANCE_SCHEMA, AcceptedCandidateBinding,
    _require_issued_binding,
    candidate_identity_digest,
)

from ..atlas_admission import (
    ATLAS_ADMISSION_SCHEMA, AtlasAdmissionBinding, ParsedAtlasAdmissionBinding,
)
from ..package_import_transition import (
    is_package_import_transition, require_issued_package_import_transition,
)
from ..motif.transition import (
    is_motif_allocation_transition, require_issued_motif_allocation_transition,
)
from ..records import (
    ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA, BAMF_POINTER_SCHEMA,
    BamfBundleCandidate, CompleteStudent, invalid,
)
from .storage import ACCEPTANCE_DIR


_UNBOUND_RETRY = object()


def require_acceptance(
        candidate: BamfBundleCandidate,
        acceptance: AcceptedCandidateBinding | None) -> AcceptedCandidateBinding:
    """Publication is not acceptance: the retention owner must have accepted it."""
    if candidate.generation == 0:
        invalid("BAMF_INITIAL_GENERATION_BOOTSTRAP_REQUIRED")
    if type(acceptance) is not AcceptedCandidateBinding:
        invalid("BAMF_GENERATION_ACCEPTANCE_REQUIRED")
    _require_issued_binding(acceptance)
    acceptance.__post_init__()
    motif_transition = is_motif_allocation_transition(candidate.transition)
    expected_schema = MOTIF_ACCEPTANCE_SCHEMA if motif_transition else ACCEPTANCE_SCHEMA
    if (acceptance.schema_version != expected_schema
            or acceptance.run_id != candidate.run_id
            or acceptance.generation != candidate.generation
            or acceptance.feature_sha256 != candidate.extents.factor_map_digest
            or acceptance.optimizer_step != candidate.retained_state.optimizer_step
            or acceptance.candidate_identity_sha256
            != candidate_identity_digest(candidate.retained_state)
            or acceptance.step_proof_sha256 != tuple(
                proof.digest for proof in candidate.retained_state.step_proofs)
            or acceptance.source_authority_registry_sha256
            != candidate.correction_frontier.get(
                "source_authority_registry_sha256")):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    if motif_transition:
        from ..genesis.records import successor_candidate_identity_digest
        if (acceptance.generation_authority_sha256
                != successor_candidate_identity_digest(candidate)):
            invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    return acceptance


def validate_parent_transition(
        run_dir: Path, pointer: dict | None, candidate: BamfBundleCandidate, *,
        load_bundle, reconcile) -> CompleteStudent | None:
    if pointer is None:
        if candidate.generation != 0 or candidate.parent_manifest_sha256 is not None:
            invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
        return None
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
    if is_motif_allocation_transition(candidate.transition):
        require_issued_motif_allocation_transition(candidate.transition)
        transition = candidate.transition
        if (parent.topology.digest != candidate.topology.digest
                or candidate_step <= parent_step
                or parent.extents.digest != transition["parent_extents_sha256"]
                or candidate.extents.digest != transition["candidate_extents_sha256"]
                or parent.retained_state.allocations.digest
                != transition["parent_allocation_sha256"]
                or candidate.retained_state.allocations.digest
                != transition["candidate_allocation_sha256"]
                or candidate_identity_digest(candidate.retained_state)
                != transition["candidate_identity_sha256"]
                or parent.extents.semantic_bank_count != candidate.extents.semantic_bank_count
                or parent.extents.active_semantic_digest != candidate.extents.active_semantic_digest
                or parent.extents.factor_map_digest != candidate.extents.factor_map_digest
                or candidate.extents.motif_page_count - parent.extents.motif_page_count
                != transition["added_pages"]
                or candidate.extents.motif_key_map_digest
                != candidate.retained_state.allocations.manifest.digest):
            invalid("BAMF_GENERATION_TRANSITION_INVALID")
    elif is_package_import_transition(candidate.transition):
        require_issued_package_import_transition(candidate.transition)
        if (parent.topology.digest != candidate.topology.digest
                or parent.extents.digest != candidate.extents.digest
                or candidate_step != parent_step):
            invalid("BAMF_GENERATION_TRANSITION_INVALID")
    else:
        if (parent.extents.motif_page_count != candidate.extents.motif_page_count
                or parent.extents.motif_key_map_digest
                != candidate.extents.motif_key_map_digest
                or parent.retained_state.allocations.digest
                != candidate.retained_state.allocations.digest):
            invalid("BAMF_GENERATION_TRANSITION_INVALID")
        kind = ("MODEL_SWAP" if parent.topology.digest != candidate.topology.digest else
                "PARAMETER_EXTENSION" if parent.extents.digest != candidate.extents.digest else
                "RETAINED_CANDIDATE")
        if (candidate_step < parent_step or
                (kind == "RETAINED_CANDIDATE" and candidate_step <= parent_step)):
            invalid("BAMF_REJECTED_CANDIDATE_NOT_GENERATION")
        if candidate.transition.get("kind") != kind:
            invalid("BAMF_GENERATION_TRANSITION_INVALID")
    reconcile(run_dir, parent)
    return parent


def authenticate_current_successor_retry(
        run_dir: Path,
        current: dict,
        candidate: BamfBundleCandidate,
        current_child: CompleteStudent,
        *,
        load_bundle,
        require_published_acceptance,
):
    """Authenticate one already-pointed exact successor retry from accepted custody."""
    from ..genesis.records import successor_candidate_identity_digest

    if (not isinstance(current, dict)
            or type(candidate) is not BamfBundleCandidate
            or type(current_child) is not CompleteStudent
            or current.get("run_id") != current_child.run_id
            or current.get("generation") != current_child.generation
            or current.get("parent_manifest_sha256")
            != current_child.parent_manifest_sha256
            or candidate.run_id != current_child.run_id
            or candidate.generation != current_child.generation
            or candidate.parent_manifest_sha256
            != current_child.parent_manifest_sha256
            or successor_candidate_identity_digest(current_child)
            != successor_candidate_identity_digest(candidate)):
        invalid(DataPlaneError.BUNDLE_IDENTITY_CONFLICT)
    persisted = require_published_acceptance(run_dir, current, current_child)
    parent_sha = current_child.parent_manifest_sha256
    if parent_sha is None:
        invalid("BAMF_RUN_IDENTITY_DRIFT")
    parent = load_bundle(
        Path(run_dir) / "bamf-bundles" / parent_sha,
        expected_manifest_sha256=parent_sha)
    if (parent.run_id != current_child.run_id
            or parent.generation + 1 != current_child.generation
            or parent.run_identity != current_child.run_identity
            or persisted.parent_candidate_identity_sha256
            != candidate_identity_digest(parent.retained_state)):
        invalid("BAMF_RUN_IDENTITY_DRIFT")
    return parent, persisted


def require_accepted_parent(
        run_dir: Path, candidate: BamfBundleCandidate,
        acceptance, *, load_bundle) -> None:
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
            or parent.run_identity != candidate.run_identity
            or acceptance.parent_candidate_identity_sha256
            != candidate_identity_digest(parent.retained_state)):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    vocabulary_changed = (
        parent.extents.semantic_bank_count != candidate.extents.semantic_bank_count
        or parent.extents.active_semantic_digest
        != candidate.extents.active_semantic_digest)
    if vocabulary_changed and type(acceptance) is not AtlasAdmissionBinding:
        invalid("BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED")


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
            from ..genesis import (
                InitialGenerationBinding,
                validate_parsed_initial_generation_binding,
            )
            acceptance = InitialGenerationBinding.from_record(record)
            validate_parsed_initial_generation_binding(
                student, acceptance, pointer["acceptance_sha256"])
        else:
            if record.get("schema_version") == ATLAS_ADMISSION_SCHEMA:
                acceptance = AtlasAdmissionBinding.from_record(record)
            else:
                acceptance = AcceptedCandidateBinding.from_record(record)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, BilqisError):
        invalid("BAMF_GENERATION_ACCEPTANCE_INVALID")
    if student.generation == 0:
        from .genesis_trust import require_initial_generation_trust_root
        require_initial_generation_trust_root(pointer, student, acceptance)
        return acceptance
    if (acceptance.digest != pointer["acceptance_sha256"]
            or acceptance.run_id != student.run_id
            or acceptance.generation != student.generation
            or acceptance.feature_sha256 != student.extents.factor_map_digest
            or acceptance.optimizer_step != student.retained_state.optimizer_step
            or acceptance.candidate_identity_sha256
            != candidate_identity_digest(student.retained_state)
            or (not isinstance(acceptance, ParsedAtlasAdmissionBinding)
                and (acceptance.schema_version not in {
                        ACCEPTANCE_SCHEMA, MOTIF_ACCEPTANCE_SCHEMA}
                     or acceptance.step_proof_sha256 != tuple(
                         proof.digest for proof in student.retained_state.step_proofs)
                     or acceptance.source_authority_registry_sha256
                     != student.correction_frontier.get(
                         "source_authority_registry_sha256")))):
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    if is_motif_allocation_transition(student.transition):
        from ..genesis.records import successor_candidate_identity_digest
        if (acceptance.schema_version != MOTIF_ACCEPTANCE_SCHEMA
                or acceptance.generation_authority_sha256
                != successor_candidate_identity_digest(student)):
            invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    elif (not isinstance(acceptance, ParsedAtlasAdmissionBinding)
          and acceptance.schema_version != ACCEPTANCE_SCHEMA):
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
                and parent.run_identity != student.run_identity)
            or (not is_motif_allocation_transition(student.transition)
                and parent.retained_state.allocations.digest
                != student.retained_state.allocations.digest)
            or (isinstance(acceptance, ParsedAtlasAdmissionBinding)
                and acceptance.parent_candidate_identity_sha256
                != candidate_identity_digest(parent.retained_state))):
        invalid("BAMF_RUN_IDENTITY_DRIFT")
    return acceptance
