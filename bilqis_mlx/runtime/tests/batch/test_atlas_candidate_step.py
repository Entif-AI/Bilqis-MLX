"""Fail-closed production path for B09.2/B12.2 candidate steps."""
from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import (
    CandidateCustodyIdentity, CandidateState, begin_candidate,
)
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_participation import ActiveAdmittedRows
from bilqis_mlx.learning.atlas_plasticity import (
    GroupEligibility, IdentityRowAge, PlasticityPolicy,
)
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, Initializer, ModelTopologySpecV2, ParameterGroup,
    ParameterSpec,
)

BANK = "identity.bank.0"
RELEASE = "b" * 64
DECLARED = (ParameterSpec(
    BANK, (2, 2), Initializer.MATRIX, ParameterGroup.IDENTITY_ROW_AGE, True),)
CENSUS_SHAPE = (
    "bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
    "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes",
)


class ProductionCandidateStepTests(unittest.TestCase):
    def setUp(self):
        values = mx.array([[.5, -.25], [1., 2.]], dtype=mx.float32)
        state = AdamWStateTree(
            {BANK: values}, {BANK: mx.ones_like(values) * .1},
            {BANK: mx.ones_like(values) * .01},
            {BANK: mx.array([2, 3], dtype=mx.uint64)})
        allocations = MotifAllocationSnapshot(MotifManifest(RELEASE))
        self.extents = GenerationExtents(
            1, 1, "a" * 64, allocations.manifest.digest, "c" * 64)
        self.parent = CandidateState(
            state, PlasticityPolicy(
                "ADAPTIVE", 7,
                (IdentityRowAge(0, 0, 7), IdentityRowAge(0, 1, 2))),
            allocations, 11,
            CandidateCustodyIdentity(
                "fixture-run", 0, "6" * 64, ModelTopologySpecV2().digest,
                self.extents.digest))
        self.hp = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)

    def eligibility(self, *, mode="FULL"):
        return GroupEligibility(
            mode=mode, eligible_parameter_names=(BANK,), frozen_parameter_names=(),
            admitted_identity_rows=((0, 0),), fast_identity_rows=((0, 0),),
            established_identity_rows=())

    def step(self, candidate, *, loss_bearing_target=False, eligibility=None):
        with patch(CENSUS_SHAPE[0], return_value=DECLARED), \
                patch(CENSUS_SHAPE[1], return_value=DECLARED):
            return production_candidate_step(
                candidate, {BANK: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32)},
                loss_bearing_target=loss_bearing_target,
                group_eligible=eligibility or self.eligibility(),
                active_admitted=ActiveAdmittedRows(identity_rows=((0, 0),)),
                spec=ModelTopologySpecV2(), extents=self.extents,
                run_id=self.parent.custody.run_id,
                generation=self.parent.custody.generation + 1,
                parent_manifest_sha256=self.parent.custody.manifest_sha256,
                parent_candidate_identity_sha256=candidate_identity_digest(self.parent),
                parent_optimizer_step=self.parent.optimizer_step,
                topology_digest=self.parent.custody.topology_digest,
                candidate_step_ordinal=1,
                teacher_hparams=self.hp, decay={BANK: True}, max_norm=1.)

    def test_step_accepts_no_caller_execution_or_motif_facts(self):
        parameters = set(inspect.signature(production_candidate_step).parameters)
        for forbidden in (
                "motif_reads", "executed_parameter_names", "visible_identity_rows",
                "feedback_identity_rows", "local_slot_rows"):
            self.assertNotIn(forbidden, parameters)

    def test_no_loss_step_is_an_exact_noop(self):
        parent = begin_candidate(self.parent)
        self.assertIs(self.step(parent), parent)

    def test_loss_bearing_step_fails_closed_without_b11_execution_trace(self):
        with self.assertRaises(BilqisError):
            self.step(begin_candidate(self.parent), loss_bearing_target=True)

    def test_forged_fast_reclassification_is_refused_before_any_update(self):
        with self.assertRaises(BilqisError):
            self.step(
                begin_candidate(self.parent),
                eligibility=self.eligibility(mode="FAST"))


if __name__ == "__main__":
    unittest.main()
