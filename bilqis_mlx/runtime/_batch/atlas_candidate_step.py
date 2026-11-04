"""Production candidate-step boundary for B09.2/B12.2 execution authority."""
from __future__ import annotations

from bilqis_mlx.learning.atlas_candidate import candidate_step
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance


def production_candidate_step(
        candidate, gradients, *, loss_bearing_target,
        group_eligible, active_admitted, spec, extents,
        run_id, generation, parent_manifest_sha256,
        parent_candidate_identity_sha256, parent_optimizer_step, topology_digest,
        candidate_step_ordinal, teacher_hparams, decay, max_norm: float):
    """Run only when the binder can issue truthful execution provenance."""
    provenance = bind_execution_provenance(
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
