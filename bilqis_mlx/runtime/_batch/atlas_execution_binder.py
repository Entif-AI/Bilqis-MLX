"""Fail-closed B09.2 binder until B11/B08 execution authority is executable.

B01 can prove the declared tensor census and plasticity groups, but it cannot
prove that a tensor participated in one objective.  The current public B08 read
is quarantined to no-hit, and B11.2 has not yet installed the single production
backend/gradient dispatch that can own a loss-bearing execution trace.

Consequently this boundary may issue only non-authorizing no-loss provenance.
It deliberately accepts no caller-supplied dense names, row gathers or motif
read records.  When B11.2 lands, that owner must replace this hold with a typed
execution-owned trace rather than reopening structural claims as credentials.
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
from bilqis_mlx.learning.atlas_participation_census import validate_group_census


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


def bind_execution_provenance(
        *, loss_bearing_target: bool,
        group_eligible, active_admitted: ActiveAdmittedRows,
        spec, extents, run_id: str, generation: int,
        parent_manifest_sha256: str, parent_candidate_identity_sha256: str,
        parent_optimizer_step: int, topology_digest: str,
        candidate_step_ordinal: int) -> StepExecutionProvenance:
    """Issue only inert provenance while no production execution owner exists."""
    if type(loss_bearing_target) is not bool:
        _invalid("LOSS_BEARING_TARGET_REQUIRED")
    validate_group_census(group_eligible, spec, extents)
    if loss_bearing_target:
        _invalid("B11_EXECUTION_AUTHORITY_REQUIRED")
    inputs = StepParticipationInputs(loss_bearing_target=False)
    return issue_execution_provenance(
        inputs, SemanticDenominator(), (), RoleReadParticipation(),
        group_eligible, active_admitted, spec=spec, extents=extents,
        run_id=run_id, generation=generation,
        parent_manifest_sha256=parent_manifest_sha256,
        parent_candidate_identity_sha256=parent_candidate_identity_sha256,
        parent_optimizer_step=parent_optimizer_step,
        topology_digest=topology_digest,
        candidate_step_ordinal=candidate_step_ordinal)
