"""Production-path adversary for the B12.2 candidate step.

The production step takes executed evidence, binds it through the B09.2 owner
and runs the masked native AdamW step. It has no caller-mask parameter.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import (
    CandidateCustodyIdentity, CandidateState, begin_candidate, resolve_candidate,
)
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, Initializer, ModelTopologySpecV2, ParameterGroup,
    ParameterSpec,
)

BANK = "identity.bank.0"
RELEASE = "b" * 64
DECLARED = (ParameterSpec(BANK, (2, 2), Initializer.MATRIX,
                           ParameterGroup.IDENTITY_ROW_AGE, True),)
EXTENTS = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
CENSUS_SHAPE = ("bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
                 "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes")


class ProductionCandidateStepTests(unittest.TestCase):
    def setUp(self):
        values = mx.array([[.5, -.25], [1., 2.]], dtype=mx.float32)
        state = AdamWStateTree(
            {BANK: values}, {BANK: mx.ones_like(values) * .1},
            {BANK: mx.ones_like(values) * .01},
            {BANK: mx.array([2, 3], dtype=mx.uint64)})
        allocations = MotifAllocationSnapshot(MotifManifest(RELEASE))
        extents = GenerationExtents(
            1, 1, "a" * 64, allocations.manifest.digest, "c" * 64)
        self.parent_extents = extents
        self.parent = CandidateState(
            state, PlasticityPolicy('ADAPTIVE', 7, (IdentityRowAge(0, 0, 7),
                                                    IdentityRowAge(0, 1, 2))),
            allocations, 11,
            CandidateCustodyIdentity(
                "fixture-run", 0, "6" * 64, ModelTopologySpecV2().digest,
                extents.digest))
        self.hp = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)

    def step(self, candidate, rows=((0, 0),)):
        from bilqis_mlx.learning.atlas_plasticity import GroupEligibility
        from bilqis_mlx.learning.atlas_participation import ActiveAdmittedRows
        eligibility = GroupEligibility(
            mode="FULL", eligible_parameter_names=(BANK,), frozen_parameter_names=(),
            admitted_identity_rows=tuple(rows), fast_identity_rows=tuple(rows),
            established_identity_rows=())
        with patch(CENSUS_SHAPE[0], return_value=DECLARED), \
                patch(CENSUS_SHAPE[1], return_value=DECLARED):
            return production_candidate_step(
                candidate, {BANK: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32)},
                motif_reads=(), executed_parameter_names=(BANK,),
                visible_identity_rows=tuple(rows), feedback_identity_rows=(),
                local_slot_rows=(), loss_bearing_target=True,
                group_eligible=eligibility,
                active_admitted=ActiveAdmittedRows(identity_rows=tuple(rows)),
                spec=ModelTopologySpecV2(), extents=self.parent_extents,
                run_id=self.parent.custody.run_id,
                generation=self.parent.custody.generation + 1,
                parent_manifest_sha256=self.parent.custody.manifest_sha256,
                parent_candidate_identity_sha256=candidate_identity_digest(
                    self.parent),
                parent_optimizer_step=self.parent.optimizer_step,
                topology_digest=self.parent.custody.topology_digest,
                candidate_step_ordinal=1,
                teacher_hparams=self.hp, decay={BANK: True}, max_norm=1.)

    def test_production_step_advances_only_the_executed_row(self):
        candidate = self.step(begin_candidate(self.parent))
        accepted = resolve_candidate(candidate, accepted=True)
        np.testing.assert_array_equal(
            np.asarray(accepted.optimizer.update_counts[BANK]), [3, 3])
        self.assertEqual(len(candidate.step_proofs), 1)
        self.assertEqual(candidate.step_proofs[0].parameter_names, (BANK,))

    def test_production_step_has_no_caller_mask_parameter(self):
        candidate = begin_candidate(self.parent)
        with self.assertRaises(TypeError):
            self.step(candidate, update_mask={BANK: mx.array([True, False])})

    def test_forged_group_classification_is_refused(self):
        from bilqis_mlx.learning.atlas_plasticity import GroupEligibility
        from bilqis_mlx.learning.atlas_participation import ActiveAdmittedRows
        forged = GroupEligibility(
            mode="FAST", eligible_parameter_names=(BANK,), frozen_parameter_names=(),
            admitted_identity_rows=((0, 0),), fast_identity_rows=((0, 0),),
            established_identity_rows=())
        with patch(CENSUS_SHAPE[0], return_value=DECLARED), \
                patch(CENSUS_SHAPE[1], return_value=DECLARED):
            with self.assertRaises(BilqisError):
                production_candidate_step(
                    begin_candidate(self.parent),
                    {BANK: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32)},
                    motif_reads=(), executed_parameter_names=(BANK,),
                    visible_identity_rows=((0, 0),), feedback_identity_rows=(),
                    local_slot_rows=(), loss_bearing_target=True,
                    group_eligible=forged,
                    active_admitted=ActiveAdmittedRows(identity_rows=((0, 0),)),
                    spec=ModelTopologySpecV2(), extents=self.parent_extents,
                    run_id=self.parent.custody.run_id,
                    generation=self.parent.custody.generation + 1,
                    parent_manifest_sha256=self.parent.custody.manifest_sha256,
                    parent_candidate_identity_sha256=candidate_identity_digest(
                        self.parent),
                    parent_optimizer_step=self.parent.optimizer_step,
                    topology_digest=self.parent.custody.topology_digest,
                    candidate_step_ordinal=1,
                    teacher_hparams=self.hp, decay={BANK: True}, max_norm=1.)


if __name__ == "__main__":
    unittest.main()
