"""Production candidate step: bind executed evidence, then run one native step.

This is the production path from executed-step evidence to an optimizer step.
The participation and the mask come from the B09.2 owner's binder, and the
step refuses anything that is not owner-issued provenance.
"""
from __future__ import annotations

from bilqis_mlx.learning.atlas_candidate import candidate_step
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance


def production_candidate_step(
        candidate, gradients, *, motif_reads, executed_parameter_names,
        visible_identity_rows, feedback_identity_rows, local_slot_rows,
        loss_bearing_target, group_eligible, active_admitted, spec, extents,
        run_id, generation, parent_manifest_sha256,
        parent_candidate_identity_sha256, parent_optimizer_step, topology_digest,
        candidate_step_ordinal, teacher_hparams, decay, max_norm: float):
    """Bind the executed step to owner provenance and run the masked AdamW step."""
    provenance = bind_execution_provenance(
        motif_reads=motif_reads,
        executed_parameter_names=executed_parameter_names,
        visible_identity_rows=visible_identity_rows,
        feedback_identity_rows=feedback_identity_rows,
        local_slot_rows=local_slot_rows,
        loss_bearing_target=loss_bearing_target,
        group_eligible=group_eligible,
        active_admitted=active_admitted,
        spec=spec, extents=extents,
        run_id=run_id, generation=generation,
        parent_manifest_sha256=parent_manifest_sha256,
        parent_candidate_identity_sha256=parent_candidate_identity_sha256,
        parent_optimizer_step=parent_optimizer_step,
        topology_digest=topology_digest,
        candidate_step_ordinal=candidate_step_ordinal)
    return candidate_step(
        candidate, gradients, provenance, teacher_hparams, decay=decay,
        loss_bearing=loss_bearing_target, max_norm=max_norm)
