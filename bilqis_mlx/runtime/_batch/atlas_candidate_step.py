"""Production candidate-step boundary for B09.2/B12.2 execution authority."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_candidate import candidate_step
from bilqis_mlx.runtime.atlas_model import BamfGradientExecution
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.atlas_optimizer import reconcile_b01_optimizer_manifest


def _invalid(reason):
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


def production_candidate_step(
        candidate, gradients=None, *, loss_bearing_target,
        gradient_execution=None,
        group_eligible, spec, extents,
        run_id, generation, parent_manifest_sha256,
        parent_candidate_identity_sha256, parent_optimizer_step, topology_digest,
        candidate_step_ordinal, teacher_hparams, max_norm: float):
    """Run only when the binder can issue truthful execution provenance."""
    loss_execution = None
    actual_gradients = gradients
    if loss_bearing_target:
        if type(gradient_execution) is not BamfGradientExecution:
            _invalid("B11_GRADIENT_EXECUTION_REQUIRED")
        gradient_execution.__post_init__()
        expected_generation = execution_generation_digest(
            candidate.optimizer.parameters, spec=spec, extents=extents)
        if gradient_execution.execution.output.generation_binding != expected_generation:
            _invalid("B11_GRADIENT_EXECUTION_CANDIDATE_MISMATCH")
        custody = candidate.parent.custody
        execution = gradient_execution.execution
        if (
            custody is None
            or execution.custody_run_id != custody.run_id
            or execution.custody_generation != custody.generation
            or execution.custody_manifest_sha256 != custody.manifest_sha256
        ):
            _invalid("B11_GRADIENT_EXECUTION_CUSTODY_MISMATCH")
        loss_execution = execution
        actual_gradients = gradient_execution.gradients
    elif gradient_execution is not None:
        _invalid("B11_GRADIENT_EXECUTION_UNEXPECTED")
    provenance = bind_execution_provenance(
        loss_bearing_target=loss_bearing_target,
        loss_execution=loss_execution,
        group_eligible=group_eligible,
        spec=spec, extents=extents,
        run_id=run_id, generation=generation,
        parent_manifest_sha256=parent_manifest_sha256,
        parent_candidate_identity_sha256=parent_candidate_identity_sha256,
        parent_optimizer_step=parent_optimizer_step,
        topology_digest=topology_digest,
        candidate_step_ordinal=candidate_step_ordinal)
    decay = reconcile_b01_optimizer_manifest(candidate.optimizer, spec, extents)
    return candidate_step(
        candidate, actual_gradients, provenance, teacher_hparams, decay=decay,
        loss_bearing=loss_bearing_target, max_norm=max_norm,
        training_authority=(getattr(loss_execution, "training_authority", None)
                            if loss_execution is not None else None))
