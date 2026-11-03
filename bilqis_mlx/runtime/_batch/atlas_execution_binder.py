"""Production binder from executed-step evidence to B09.2 participation and mask.

This is the production entry point for candidate-step participation. It
consumes the evidence the execution and read owners produced: the B08 motif
read results, the executed parameter names, the gathered identity rows and the
local slot rows. Motif participation comes only from the read results, so a
caller cannot claim a motif slot the read owner did not report, and the mask
always comes from the B09.2 owner.
"""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_execution_provenance import (
    StepExecutionProvenance, issue_execution_provenance,
)
from bilqis_mlx.learning.atlas_participation import (
    ActiveAdmittedRows, RoleReadParticipation, SemanticDenominator,
    StepParticipationInputs,
)


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


def bind_execution_provenance(
        *, motif_reads: tuple, executed_parameter_names: tuple,
        visible_identity_rows: tuple, feedback_identity_rows: tuple,
        local_slot_rows: tuple, loss_bearing_target: bool,
        group_eligible, active_admitted: ActiveAdmittedRows,
        spec, extents, run_id: str, generation: int,
        parent_manifest_sha256: str, parent_candidate_identity_sha256: str,
        parent_optimizer_step: int, topology_digest: str,
        candidate_step_ordinal: int) -> StepExecutionProvenance:
    """Bind one executed step to owner-issued participation and mask provenance.

    The motif read results are the only source of motif participation, and the
    executed parameter names are the only source of dense participation. The
    returned provenance carries the owner-derived mask, so B12.2 never accepts
    a caller mask.
    """
    if not isinstance(motif_reads, tuple):
        _invalid("MOTIF_READ_RESULTS_REQUIRED")
    if not isinstance(executed_parameter_names, tuple):
        _invalid("EXECUTED_PARAMETER_NAMES_REQUIRED")
    inputs = StepParticipationInputs(
        visible_identity_rows=tuple(visible_identity_rows),
        feedback_identity_rows=tuple(feedback_identity_rows),
        local_slot_rows=tuple(local_slot_rows),
        executed_parameter_names=tuple(executed_parameter_names),
        loss_bearing_target=bool(loss_bearing_target))
    return issue_execution_provenance(
        inputs, SemanticDenominator(), motif_reads, RoleReadParticipation(),
        group_eligible, active_admitted, spec=spec, extents=extents,
        run_id=run_id, generation=generation,
        parent_manifest_sha256=parent_manifest_sha256,
        parent_candidate_identity_sha256=parent_candidate_identity_sha256,
        parent_optimizer_step=parent_optimizer_step,
        topology_digest=topology_digest,
        candidate_step_ordinal=candidate_step_ordinal)
