"""Production candidate admission: derive, step, accept, publish.

This is the production path from executed-step evidence to a published accepted
generation. The B09.2 binder derives the participation and the mask, the
retention owner mints the acceptance binding, and B13 custody publishes the
generation only with that binding. No test helper is involved.
"""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.learning.atlas_candidate import (
    CandidateState, CandidateTransaction, begin_candidate, resolve_candidate,
)
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step

from .codec import load_bamf_bundle
from .publication import _pointer_lock, _read_pointer, publish_bamf_generation
from .records import BamfBundleCandidate, CompleteStudent, invalid


def load_accepted_generation(run_dir: Path) -> CompleteStudent:
    """Load the currently published accepted generation under the pointer lock."""
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
    return student


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


def admit_candidate_step(parent: CompleteStudent, gradients, *,
                         motif_reads, executed_parameter_names,
                         visible_identity_rows, feedback_identity_rows,
                         local_slot_rows, loss_bearing_target, group_eligible,
                         active_admitted, spec, extents, teacher_hparams,
                         decay, max_norm: float) -> CandidateTransaction:
    """Run one candidate optimizer step through the production participation binder.

    The participation and the mask come from the B09.2 owner binder, and the
    step refuses anything that is not owner-issued provenance.
    """
    return production_candidate_step(
        begin_candidate(parent.retained_state), gradients,
        motif_reads=motif_reads,
        executed_parameter_names=executed_parameter_names,
        visible_identity_rows=visible_identity_rows,
        feedback_identity_rows=feedback_identity_rows,
        local_slot_rows=local_slot_rows,
        loss_bearing_target=loss_bearing_target,
        group_eligible=group_eligible, active_admitted=active_admitted,
        spec=spec, extents=extents, teacher_hparams=teacher_hparams,
        decay=decay, max_norm=max_norm)


def accept_and_publish(run_dir: Path, bundle: BamfBundleCandidate,
                       retained_state: CandidateState, *,
                       feature_sha256: str, retention_reason: str,
                       step_proofs: tuple = ()) -> dict:
    """Accept a candidate with the retention owner and publish it with that binding.

    The retention owner mints the acceptance binding for the exact accepted
    optimizer state and the owner-bound step proofs. B13 custody publishes the
    generation only when the binding matches the candidate it publishes.
    """
    binding = mint_acceptance_binding(
        retained_state, run_id=bundle.run_id, generation=bundle.generation,
        feature_sha256=feature_sha256, retention_reason=retention_reason,
        step_proofs=tuple(step_proofs))
    return publish_bamf_generation(run_dir, bundle, acceptance=binding)
