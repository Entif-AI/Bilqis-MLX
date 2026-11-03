"""Shared B09.2 execution-provenance fixtures for owner tests."""
from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

from bilqis_mlx.learning.atlas_execution_provenance import (
    issue_execution_provenance,
)
from bilqis_mlx.learning.atlas_participation import (
    ActiveAdmittedRows, RoleReadParticipation, SemanticDenominator,
    StepParticipationInputs,
)
from bilqis_mlx.learning.atlas_plasticity import GroupEligibility
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, Initializer, ModelTopologySpecV2, ParameterGroup,
    ParameterSpec,
)

PARAMETER = "identity.bank.0"
DECLARED = (ParameterSpec(PARAMETER, (2, 2), Initializer.MATRIX,
                          ParameterGroup.IDENTITY_ROW_AGE, True),)
EXTENTS = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
CENSUS_SHAPES = (
    "bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
    "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes",
)


def execution_provenance(*, rows=(0,), loss_bearing=True, mode="FULL"):
    """Issue owner provenance for one executed step over the fixture bank."""
    identity = tuple((0, row) for row in rows)
    inputs = StepParticipationInputs(
        visible_identity_rows=identity,
        executed_parameter_names=(PARAMETER,),
        loss_bearing_target=loss_bearing)
    active = ActiveAdmittedRows(identity_rows=identity)
    eligibility = GroupEligibility(
        mode=mode, eligible_parameter_names=(PARAMETER,),
        frozen_parameter_names=(), admitted_identity_rows=identity,
        fast_identity_rows=identity, established_identity_rows=())
    with ExitStack() as stack:
        for target in CENSUS_SHAPES:
            stack.enter_context(patch(target, return_value=DECLARED))
        return issue_execution_provenance(
            inputs, SemanticDenominator(), (), RoleReadParticipation(),
            eligibility, active, spec=ModelTopologySpecV2(), extents=EXTENTS)
