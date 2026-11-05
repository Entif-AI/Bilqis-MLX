"""B01 classification must constrain B09 parameter update masks."""
from dataclasses import replace
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_plasticity import (
    ActiveAdmittedRows, IdentityRowAge, RoleReadParticipation,
    SemanticDenominator, StepParticipationInputs, group_eligibility,
    parameter_update_mask, step_participation,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, ParameterGroup, bamf_parameter_census,
)


class CensusMaskTests(TestCase):
    def setUp(self):
        self.spec = ModelTopologySpecV2()
        self.extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
        self.census = bamf_parameter_census(self.spec, self.extents)
        self.eligibility = group_eligibility("FAST", self.census, (IdentityRowAge(0, 0, 0),))
        self.participation = step_participation(
            StepParticipationInputs(visible_identity_rows=((0, 0),),
                executed_parameter_names=("blocks.0.query", "plastic.group.0.A")),
            SemanticDenominator(), (), RoleReadParticipation())
        self.active = ActiveAdmittedRows(identity_rows=((0, 0),))

    def test_forged_fast_eligibility_over_b01_slow_is_rejected(self):
        query = next(p for p in self.census.parameters if p.name == "blocks.0.query")
        self.assertIs(query.group, ParameterGroup.SLOW)
        forged = replace(self.eligibility,
            eligible_parameter_names=tuple(sorted(self.eligibility.eligible_parameter_names + (query.name,))),
            frozen_parameter_names=tuple(n for n in self.eligibility.frozen_parameter_names if n != query.name))
        with self.assertRaises(BilqisError):
            parameter_update_mask(forged, self.participation, self.active,
                                  spec=self.spec, extents=self.extents)

    def test_b01_full_census_allows_fast_and_young_identity_but_freezes_slow(self):
        mask = parameter_update_mask(self.eligibility, self.participation, self.active,
                                     spec=self.spec, extents=self.extents)
        self.assertFalse(mask.parameter("blocks.0.query").whole_parameter)
        self.assertTrue(mask.parameter("plastic.group.0.A").whole_parameter)
        self.assertEqual(mask.parameter("identity.bank.0").row_indices, (0,))

    def test_full_mode_permits_executed_slow_parameter(self):
        eligibility = group_eligibility("FULL", self.census, (IdentityRowAge(0, 0, 0),))
        mask = parameter_update_mask(eligibility, self.participation, self.active,
                                     spec=self.spec, extents=self.extents)
        self.assertTrue(mask.parameter("blocks.0.query").whole_parameter)

    def test_public_mask_requires_b01_spec_and_extents(self):
        with self.assertRaises(TypeError):
            parameter_update_mask(self.eligibility, self.participation, self.active)

    def test_partial_census_is_not_a_public_bypass(self):
        partial = replace(self.eligibility, frozen_parameter_names=())
        with self.assertRaises(BilqisError):
            parameter_update_mask(partial, self.participation, self.active,
                                  spec=self.spec, extents=self.extents)
