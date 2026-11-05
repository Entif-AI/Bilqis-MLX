"""Production candidate-step boundary for B09.2/B12.2 execution authority."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_candidate import (
    begin_candidate, candidate_identity_digest, candidate_step,
)
from bilqis_mlx.learning.atlas_plasticity import (
    group_eligibility, next_update_mode,
)
from bilqis_mlx.runtime.atlas_model import BamfGradientExecution
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.publication import (
    load_bamf_generation_authority,
)
from bilqis_mlx.runtime.model_topology_v2 import bamf_parameter_census


def _invalid(reason):
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


def production_candidate_step(
        candidate, gradients=None, *, loss_bearing_target,
        gradient_execution=None,
        group_eligible, spec, extents,
        run_id, generation, parent_manifest_sha256,
        parent_candidate_identity_sha256, parent_optimizer_step, topology_digest,
        candidate_step_ordinal, teacher_hparams, decay, max_norm: float):
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
    if not loss_bearing_target:
        return candidate
    return candidate_step(
        candidate, actual_gradients, provenance, teacher_hparams, decay=decay,
        loss_bearing=loss_bearing_target, max_norm=max_norm)


def admit_current_candidate_step(
        pointer_path: Path, *, gradient_execution=None,
        loss_bearing_target: bool, teacher_hparams, decay,
        max_norm: float):
    """Start one B12 candidate step from the current B13 accepted generation.

    The public production boundary accepts no caller-authored participation,
    eligibility, topology, generation, manifest, or candidate identity. Those
    values are rederived from the current immutable B13 generation before the
    B11 execution witness is admitted.
    """
    parent, manifest_sha256 = load_bamf_generation_authority(
        Path(pointer_path))
    state = parent.retained_state
    custody = state.custody
    if (
        custody is None
        or custody.run_id != parent.run_id
        or custody.generation != parent.generation
        or custody.manifest_sha256 != manifest_sha256
        or custody.topology_digest != parent.topology.digest
        or custody.extents_digest != parent.extents.digest
    ):
        _invalid("B13_CANDIDATE_CUSTODY_MISMATCH")
    census = bamf_parameter_census(parent.topology, parent.extents)
    eligibility = group_eligibility(
        next_update_mode(
            state.policy, teacher_requests_full=False),
        census,
        state.policy.row_ages,
    )
    candidate = begin_candidate(state)
    return production_candidate_step(
        candidate,
        loss_bearing_target=loss_bearing_target,
        gradient_execution=gradient_execution,
        group_eligible=eligibility,
        spec=parent.topology,
        extents=parent.extents,
        run_id=parent.run_id,
        generation=parent.generation + 1,
        parent_manifest_sha256=manifest_sha256,
        parent_candidate_identity_sha256=candidate_identity_digest(state),
        parent_optimizer_step=state.optimizer_step,
        topology_digest=parent.topology.digest,
        candidate_step_ordinal=1,
        teacher_hparams=teacher_hparams,
        decay=decay,
        max_norm=max_norm,
    )
