"""Fail-closed production authority tests for the B09.2 execution binder."""
from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_execution_provenance import StepExecutionProvenance
from bilqis_mlx.learning.atlas_participation import ActiveAdmittedRows
from bilqis_mlx.learning.atlas_plasticity import GroupEligibility
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, Initializer, ModelTopologySpecV2, ParameterGroup,
    ParameterSpec,
)

BANK = "identity.bank.0"
MOTIF = "motif.page.0"
DECLARED = (
    ParameterSpec(BANK, (2, 2), Initializer.MATRIX,
                  ParameterGroup.IDENTITY_ROW_AGE, True),
    ParameterSpec(MOTIF, (8, 8), Initializer.MATRIX,
                  ParameterGroup.FAST, True),
)
EXTENTS = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
CENSUS_SHAPE = (
    "bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
    "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes",
)


def eligibility(mode="FULL", admitted=((0, 0),), eligible=(BANK, MOTIF)):
    return GroupEligibility(
        mode=mode,
        eligible_parameter_names=tuple(eligible),
        frozen_parameter_names=(),
        admitted_identity_rows=tuple(admitted),
        fast_identity_rows=tuple(admitted),
        established_identity_rows=(),
    )


class ExecutionBinderProductionTests(unittest.TestCase):
    def bind(self, **overrides):
        evidence = {
            "loss_bearing_target": False,
            "group_eligible": eligibility(),
            "active_admitted": ActiveAdmittedRows(
                identity_rows=((0, 0),), motif_slots=(0,)),
            "spec": ModelTopologySpecV2(),
            "extents": EXTENTS,
            "run_id": "fixture-run",
            "generation": 1,
            "parent_manifest_sha256": "6" * 64,
            "parent_candidate_identity_sha256": "7" * 64,
            "parent_optimizer_step": 11,
            "topology_digest": "8" * 64,
            "candidate_step_ordinal": 1,
        }
        evidence.update(overrides)
        with patch(CENSUS_SHAPE[0], return_value=DECLARED), \
                patch(CENSUS_SHAPE[1], return_value=DECLARED):
            return bind_execution_provenance(**evidence)

    def test_binder_accepts_no_caller_execution_or_motif_facts(self):
        parameters = set(inspect.signature(bind_execution_provenance).parameters)
        for forbidden in (
                "motif_reads", "executed_parameter_names", "visible_identity_rows",
                "feedback_identity_rows", "local_slot_rows"):
            self.assertNotIn(forbidden, parameters)

    def test_no_loss_binder_issues_empty_non_authorizing_provenance(self):
        provenance = self.bind()
        self.assertFalse(provenance.mask.has_loss_bearing_target)
        self.assertEqual(provenance.participation.dense_parameter_names, ())
        for item in provenance.mask.parameters:
            self.assertFalse(item.whole_parameter)
            self.assertEqual(item.row_indices, ())

    def test_loss_bearing_step_fails_closed_until_b11_execution_owner_exists(self):
        with self.assertRaises(BilqisError):
            self.bind(loss_bearing_target=True)

    def test_forged_fast_reclassification_of_slow_parameter_is_refused(self):
        forged = eligibility(mode="FAST", admitted=((0, 0),), eligible=(BANK, MOTIF))
        with self.assertRaises(BilqisError):
            self.bind(group_eligible=forged)

    def test_caller_cannot_construct_the_provenance(self):
        provenance = self.bind()
        with self.assertRaises(BilqisError):
            StepExecutionProvenance(
                provenance.participation, provenance.mask,
                provenance.eligible_parameter_names, provenance.extents_sha256,
                provenance.run_id, provenance.generation,
                provenance.parent_manifest_sha256,
                provenance.parent_candidate_identity_sha256,
                provenance.parent_optimizer_step, provenance.topology_digest,
                provenance.candidate_step)


if __name__ == "__main__":
    unittest.main()
