"""Production candidate admission: derive, step, accept, publish.

This is the production path from executed-step evidence to a published accepted
generation. The B09.2 binder derives the participation and the mask, the
retention owner mints the acceptance binding, and B13 custody publishes the
generation only with that binding. No test helper is involved.

The generation identity used to bind a step comes from the published custody,
never from caller parameters, so a provenance record cannot be replayed onto
another candidate, generation, step, topology or extents state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    AcceptedCandidateBinding, candidate_identity_digest, mint_acceptance_binding,
)
from bilqis_mlx.learning.atlas_retention_decision import (
    CandidateRetentionDecision,
)
from bilqis_mlx.learning.atlas_candidate import (
    CandidateState, CandidateTransaction, begin_candidate, resolve_candidate,
)
from bilqis_mlx.learning.atlas_plasticity import group_eligibility, next_update_mode
from bilqis_mlx.learning.atlas_participation import ActiveAdmittedRows
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.model_topology_v2 import ParameterCensus

from .codec import load_bamf_bundle
from .publication import (
    ACCEPTANCE_DIR, _live_bundle_manifest, _pointer_lock, _read_pointer,
    publish_bamf_generation,
)
from .records import (
    BAMF_POINTER_SCHEMA, BamfBundleCandidate, CompleteStudent,
    canonical, invalid, sha, sidecar_records,
)
from .execution_cache import _issue_accepted_execution_cache


@dataclass(frozen=True)
class AcceptedGenerationIdentity:
    """The published identity of the accepted generation in custody."""

    run_id: str
    generation: int
    manifest_sha256: str
    topology_digest: str
    extents_digest: str
    optimizer_step: int
    candidate_identity_sha256: str


def _read_accepted(run_dir: Path):
    run_dir = Path(run_dir)
    pointer_path = run_dir / "bamf-state.json"
    with _pointer_lock(run_dir):
        pointer = _read_pointer(pointer_path)
        if pointer is None:
            invalid("BAMF_GENERATION_POINTER_MISSING")
        student = load_bamf_bundle(
            run_dir / "bamf-bundles" / pointer["manifest_sha256"],
            expected_manifest_sha256=pointer["manifest_sha256"])
        if (student.run_id != pointer["run_id"]
                or student.generation != pointer["generation"]
                or student.parent_manifest_sha256 != pointer["parent_manifest_sha256"]):
            invalid("BAMF_GENERATION_POINTER_DRIFT")
    return pointer, student


def load_accepted_generation(run_dir: Path) -> CompleteStudent:
    """Load the currently published accepted generation under the pointer lock."""
    return _read_accepted(run_dir)[1]


def bind_accepted_execution_cache(run_dir: Path):
    """Authenticate the live accepted generation and mint its retained B08 cache."""
    run_dir = Path(run_dir)
    _pointer, student = _read_accepted(run_dir)
    identity = _published_in_memory_identity(run_dir, student)
    generation_binding = execution_generation_digest(
        student.retained_state.optimizer.parameters,
        spec=student.topology,
        extents=student.extents,
    )
    return _issue_accepted_execution_cache(
        run_id=identity.run_id,
        generation=identity.generation,
        accepted_manifest_sha256=identity.manifest_sha256,
        generation_binding=generation_binding,
        motif_manifest=student.retained_state.allocations.manifest,
    )


def _identity_from_pointer(
        student: CompleteStudent, pointer: dict) -> AcceptedGenerationIdentity:
    """Bind the current student to the exact accepted B13 pointer."""
    manifest = pointer.get("manifest_sha256") if isinstance(pointer, dict) else None
    if (type(student) is not CompleteStudent
            or not isinstance(pointer, dict)
            or pointer.get("schema") != BAMF_POINTER_SCHEMA
            or pointer.get("run_id") != student.run_id
            or pointer.get("generation") != student.generation
            or pointer.get("parent_manifest_sha256") != student.parent_manifest_sha256
            or not isinstance(manifest, str) or len(manifest) != SHA256_HEX_LENGTH
            or any(char not in "0123456789abcdef" for char in manifest)):
        invalid("BAMF_GENERATION_POINTER_DRIFT")
    return AcceptedGenerationIdentity(
        run_id=student.run_id,
        generation=student.generation,
        manifest_sha256=manifest,
        topology_digest=student.topology.digest,
        extents_digest=student.extents.digest,
        optimizer_step=student.retained_state.optimizer_step,
        candidate_identity_sha256=candidate_identity_digest(student.retained_state))


def _published_in_memory_identity(
        run_dir: Path, student: CompleteStudent) -> AcceptedGenerationIdentity:
    """Authenticate an in-memory student without reconstructing its tensor bundle."""
    run_dir = Path(run_dir)
    if type(student) is not CompleteStudent:
        invalid("BAMF_GENERATION_POINTER_DRIFT")
    with _pointer_lock(run_dir):
        pointer = _read_pointer(run_dir / "bamf-state.json")
        if pointer is None:
            invalid("BAMF_GENERATION_POINTER_MISSING")
        identity = _identity_from_pointer(student, pointer)
        manifest = _live_bundle_manifest(run_dir, pointer)
        if (manifest["implementation_sha256"] != student.implementation_sha256
                or canonical(manifest["topology"])
                != canonical(student.topology.to_record())
                or canonical(manifest["extents"])
                != canonical(student.extents.to_record())
                or canonical(manifest["provenance"])
                != canonical(student.provenance.to_record())
                or canonical(manifest["transition"])
                != canonical(dict(student.transition))
                or manifest["optimizer"]["step"] != student.retained_state.optimizer_step
                or canonical(manifest["optimizer"]["hyperparameters"])
                != canonical(asdict(student.optimizer_hyperparameters))):
            invalid("BAMF_GENERATION_POINTER_DRIFT")
        for name, record in sidecar_records(student).items():
            stored = manifest["sidecars"].get(name)
            if (not isinstance(stored, dict)
                    or stored.get("sha256") != sha(canonical(record))):
                invalid("BAMF_GENERATION_POINTER_DRIFT")
        acceptance_path = (
            run_dir / ACCEPTANCE_DIR / f"{identity.manifest_sha256}.json")
        if acceptance_path.is_symlink() or not acceptance_path.is_file():
            invalid("BAMF_GENERATION_ACCEPTANCE_MISSING")
        try:
            acceptance = AcceptedCandidateBinding.from_record(
                json.loads(acceptance_path.read_bytes()))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, BilqisError):
            invalid("BAMF_GENERATION_ACCEPTANCE_INVALID")
        if (acceptance.digest != pointer["acceptance_sha256"]
                or acceptance.run_id != identity.run_id
                or acceptance.generation != identity.generation
                or acceptance.feature_sha256 != student.extents.factor_map_digest
                or acceptance.optimizer_step != identity.optimizer_step
                or acceptance.candidate_identity_sha256
                != identity.candidate_identity_sha256
                or acceptance.step_proof_sha256 != tuple(
                    proof.digest for proof in student.retained_state.step_proofs)):
            invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    return identity


def derive_successor_bundle(parent: CompleteStudent, retained_state: CandidateState,
                            *, parent_manifest_sha256: str,
                            delivery_events: tuple) -> BamfBundleCandidate:
    """Build the successor generation bundle from the accepted parent custody.

    The successor inherits the parent's topology, extents, provenance and
    sidecars. Only the retained optimizer state, the generation identity, the
    transition kind and the delivery intent change. The delivery events are
    unbound intent records for the new lineage; the parent's bound outbox is
    never replayed under a new generation.
    """
    if type(parent) is not CompleteStudent or type(retained_state) is not CandidateState:
        invalid("BAMF_GENERATION_PARENT_INVALID")
    kind = "RETAINED_CANDIDATE"
    transition = {
        "schema": "bilqis.mlx.bamf-generation-transition/v1",
        "kind": kind,
        "invalidate_derived_caches": kind in {"PARAMETER_EXTENSION", "MODEL_SWAP"},
    }
    return BamfBundleCandidate(
        parent.run_id, parent.generation + 1, parent_manifest_sha256,
        parent.implementation_sha256, parent.topology, parent.extents,
        retained_state, parent.optimizer_hyperparameters, parent.provenance,
        dict(parent.semantic_abi), dict(parent.compiler_features),
        dict(parent.correction_frontier), dict(parent.teacher_state),
        dict(parent.evaluation_contract), transition, tuple(delivery_events))


def _parameter_census(parent: CompleteStudent) -> ParameterCensus:
    """The B01 parameter census owner for the accepted generation.

    The declared parameter set is read through the census owner module that the
    participation owner validates against, so both see exactly the same ledger.
    """
    owner = sys.modules["bilqis_mlx.learning.atlas_participation_census"]
    return ParameterCensus(
        parent.topology.digest, parent.extents.digest,
        owner.expected_bamf_shapes(parent.topology, parent.extents))


def derive_participation_inputs(parent: CompleteStudent):
    """Derive structural eligibility from B01 and the retained policy.

    The group eligibility comes from the B01 parameter census owner and the
    retained policy owner, and the admitted rows from published custody.
    Neither the census nor these eligibility facts prove actual execution.
    """
    census = _parameter_census(parent)
    mode = next_update_mode(parent.retained_state.policy,
                             teacher_requests_full=False)
    eligibility = group_eligibility(
        mode, census, parent.retained_state.policy.row_ages)
    return eligibility, ActiveAdmittedRows(
        identity_rows=eligibility.admitted_identity_rows)


def _admit_loaded_candidate_step(
        parent: CompleteStudent, identity: AcceptedGenerationIdentity, gradients=None, *,
        loss_bearing_target, gradient_execution=None, teacher_hparams,
        max_norm: float) -> CandidateTransaction:
    """Pass custody-verified state plus B11 execution truth to B09/B12.

    Raw gradients remain usable only for the no-loss no-op path. A loss-bearing
    update must carry the unforgeable ``BamfGradientExecution`` issued by the
    real B11 forward/backward owner; B09 then derives participation and the
    final update mask from that same execution record.
    """
    if (type(parent) is not CompleteStudent
            or type(identity) is not AcceptedGenerationIdentity
            or identity.run_id != parent.run_id
            or identity.generation != parent.generation
            or identity.topology_digest != parent.topology.digest
            or identity.extents_digest != parent.extents.digest
            or identity.optimizer_step != parent.retained_state.optimizer_step
            or identity.candidate_identity_sha256
            != candidate_identity_digest(parent.retained_state)):
        invalid("BAMF_GENERATION_POINTER_DRIFT")
    eligibility, _active_admitted = derive_participation_inputs(parent)
    return production_candidate_step(
        begin_candidate(parent.retained_state), gradients,
        loss_bearing_target=loss_bearing_target,
        gradient_execution=gradient_execution,
        group_eligible=eligibility,
        spec=parent.topology, extents=parent.extents,
        run_id=identity.run_id, generation=identity.generation + 1,
        parent_manifest_sha256=identity.manifest_sha256,
        parent_candidate_identity_sha256=identity.candidate_identity_sha256,
        parent_optimizer_step=identity.optimizer_step,
        topology_digest=identity.topology_digest,
        candidate_step_ordinal=1,
        teacher_hparams=teacher_hparams, max_norm=max_norm)


def admit_uninterrupted_candidate_step(
        run_dir: Path, parent: CompleteStudent, gradients=None, *,
        loss_bearing_target, gradient_execution=None, teacher_hparams,
        max_norm: float) -> CandidateTransaction:
    """Continue held state only after full current B13 custody authentication."""
    identity = _published_in_memory_identity(run_dir, parent)
    return _admit_loaded_candidate_step(
        parent, identity, gradients,
        loss_bearing_target=loss_bearing_target,
        gradient_execution=gradient_execution,
        teacher_hparams=teacher_hparams, max_norm=max_norm)


def admit_candidate_step(run_dir: Path, gradients=None, *,
                         loss_bearing_target, gradient_execution=None, teacher_hparams,
                         max_norm: float) -> CandidateTransaction:
    """Cold-load the accepted state and enter the production execution guard."""
    pointer, parent = _read_accepted(run_dir)
    identity = _identity_from_pointer(parent, pointer)
    return _admit_loaded_candidate_step(
        parent, identity, gradients,
        loss_bearing_target=loss_bearing_target,
        gradient_execution=gradient_execution,
        teacher_hparams=teacher_hparams, max_norm=max_norm)


def accept_and_publish(run_dir: Path, bundle: BamfBundleCandidate,
                       retained_state: CandidateState, *,
                       decision: CandidateRetentionDecision,
                       feature_sha256: str,
                       training_authorities=None) -> dict:
    """Publish a candidate that the retention decision owner has accepted.

    Publication does not decide that the candidate was accepted. The retention
    decision owner issues the decision, the retention owner mints the acceptance
    binding from that decision, and B13 custody publishes the generation only
    when the binding matches the candidate it publishes.
    """
    binding = mint_acceptance_binding(
        decision, retained_state, run_id=bundle.run_id,
        generation=bundle.generation, feature_sha256=feature_sha256,
        training_authorities=training_authorities)
    return publish_bamf_generation(run_dir, bundle, acceptance=binding)
