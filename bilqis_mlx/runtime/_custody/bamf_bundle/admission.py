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

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from bilqis_mlx.learning.atlas_acceptance import (
    candidate_identity_digest, mint_acceptance_binding,
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
from bilqis_mlx.runtime.model_topology_v2 import ParameterCensus

from .codec import load_bamf_bundle
from .publication import _pointer_lock, _read_pointer, publish_bamf_generation
from .records import BamfBundleCandidate, CompleteStudent, invalid


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


def _identity_of(student: CompleteStudent, run_dir: Path) -> AcceptedGenerationIdentity:
    """The published identity of one loaded accepted generation."""
    pointer = json.loads((Path(run_dir) / "bamf-state.json").read_text())
    return AcceptedGenerationIdentity(
        run_id=student.run_id,
        generation=student.generation,
        manifest_sha256=pointer["manifest_sha256"],
        topology_digest=student.topology.digest,
        extents_digest=student.extents.digest,
        optimizer_step=student.retained_state.optimizer_step,
        candidate_identity_sha256=candidate_identity_digest(student.retained_state))


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
    """Derive the participation inputs from their owners.

    The group eligibility comes from the B01 parameter census owner and the
    retained policy owner, the admitted rows from the published custody, and
    the executed parameter names from the same census. A caller cannot
    reclassify a parameter, substitute identity rows or admission state, or
    claim a parameter executed when the owners do not report it.
    """
    census = _parameter_census(parent)
    mode = next_update_mode(parent.retained_state.policy,
                             teacher_requests_full=False)
    eligibility = group_eligibility(
        mode, census, parent.retained_state.policy.row_ages)
    return eligibility, ActiveAdmittedRows(
        identity_rows=eligibility.admitted_identity_rows)


def admit_candidate_step(run_dir: Path, gradients, *,
                         motif_reads, loss_bearing_target, teacher_hparams,
                         decay, max_norm: float) -> CandidateTransaction:
    """Run one candidate optimizer step for the accepted generation in custody.

    The participation inputs are derived from their owners, the step binds
    itself to the published generation identity, and provenance issued for
    another candidate, generation, step, topology or extents state cannot be
    used here.
    """
    parent = load_accepted_generation(run_dir)
    identity = _identity_of(parent, run_dir)
    eligibility, active_admitted = derive_participation_inputs(parent)
    executed_parameter_names = tuple(sorted(
        item.name for item in _parameter_census(parent).parameters))
    return production_candidate_step(
        begin_candidate(parent.retained_state), gradients,
        motif_reads=motif_reads,
        executed_parameter_names=executed_parameter_names,
        visible_identity_rows=eligibility.admitted_identity_rows,
        feedback_identity_rows=(),
        local_slot_rows=(),
        loss_bearing_target=loss_bearing_target,
        group_eligible=eligibility,
        active_admitted=active_admitted,
        spec=parent.topology, extents=parent.extents,
        run_id=identity.run_id, generation=identity.generation + 1,
        parent_manifest_sha256=identity.manifest_sha256,
        parent_candidate_identity_sha256=identity.candidate_identity_sha256,
        parent_optimizer_step=identity.optimizer_step,
        topology_digest=identity.topology_digest,
        candidate_step_ordinal=1,
        teacher_hparams=teacher_hparams, decay=decay, max_norm=max_norm)


def accept_and_publish(run_dir: Path, bundle: BamfBundleCandidate,
                       retained_state: CandidateState, *,
                       decision: CandidateRetentionDecision,
                       feature_sha256: str) -> dict:
    """Publish a candidate that the retention decision owner has accepted.

    Publication does not decide that the candidate was accepted. The retention
    decision owner issues the decision, the retention owner mints the acceptance
    binding from that decision, and B13 custody publishes the generation only
    when the binding matches the candidate it publishes.
    """
    binding = mint_acceptance_binding(
        decision, retained_state, run_id=bundle.run_id,
        generation=bundle.generation, feature_sha256=feature_sha256)
    return publish_bamf_generation(run_dir, bundle, acceptance=binding)
