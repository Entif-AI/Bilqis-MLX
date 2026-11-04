"""B09.2 binder consuming only B11-issued production execution authority."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_execution_provenance import (
    StepExecutionProvenance, issue_execution_provenance,
)
from bilqis_mlx.learning.atlas_participation import (
    ActiveAdmittedRows, RoleReadParticipation, SemanticDenominator,
    StepParticipationInputs,
)
from bilqis_mlx.learning.atlas_participation_census import validate_group_census
from bilqis_mlx.runtime.atlas_model import require_bamf_loss_execution


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


def bind_execution_provenance(
        *, loss_bearing_target: bool,
        loss_execution=None,
        group_eligible,
        spec, extents, run_id: str, generation: int,
        parent_manifest_sha256: str, parent_candidate_identity_sha256: str,
        parent_optimizer_step: int, topology_digest: str,
        candidate_step_ordinal: int) -> StepExecutionProvenance:
    """Issue inert no-loss provenance or bind the exact B11 loss execution."""
    if type(loss_bearing_target) is not bool:
        _invalid("LOSS_BEARING_TARGET_REQUIRED")
    validate_group_census(group_eligible, spec, extents)
    if not loss_bearing_target:
        if loss_execution is not None:
            _invalid("B11_EXECUTION_AUTHORITY_UNEXPECTED")
        inputs = StepParticipationInputs(loss_bearing_target=False)
        active_admitted = ActiveAdmittedRows()
    else:
        execution = require_bamf_loss_execution(loss_execution)
        inputs = StepParticipationInputs(
            visible_identity_rows=execution.visible_identity_rows,
            visible_feature_rows=execution.feature_rows,
            local_slot_rows=execution.local_slot_rows,
            executed_parameter_names=execution.dense_parameter_names,
            loss_bearing_target=True,
        )
        active_admitted = ActiveAdmittedRows(
            identity_rows=group_eligible.admitted_identity_rows,
            motif_slots=tuple(sorted({
                slot
                for result in execution.motif_reads
                for slot in result.participating_slots
            })),
            feature_rows=execution.feature_rows,
            local_slot_rows=execution.local_slot_rows,
        )
    return issue_execution_provenance(
        inputs, SemanticDenominator(), (
            execution.motif_reads if loss_bearing_target else ()),
        RoleReadParticipation(),
        group_eligible, active_admitted, spec=spec, extents=extents,
        run_id=run_id, generation=generation,
        parent_manifest_sha256=parent_manifest_sha256,
        parent_candidate_identity_sha256=parent_candidate_identity_sha256,
        parent_optimizer_step=parent_optimizer_step,
        topology_digest=topology_digest,
        candidate_step_ordinal=candidate_step_ordinal)
