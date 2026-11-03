"""B12.2 execution-provenance binding and caller-substitution adversaries.

A caller-created candidate must never make its own mask the final truth of an
optimizer step. The step binds to owner-issued B09.2 execution provenance.
"""
from __future__ import annotations

import unittest
from dataclasses import replace

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import (
    begin_candidate, candidate_step, resolve_candidate,
)
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.learning.atlas_execution_provenance import StepExecutionProvenance
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree

from bilqis_mlx.learning._retention.tests.execution_fixtures import (
    PARAMETER, execution_provenance,
)

RELEASE = "b" * 64
NAME = PARAMETER


class ExecutionProvenanceBindingTests(unittest.TestCase):
    def setUp(self):
        values = mx.array([[.5, -.25], [1., 2.]], dtype=mx.float32)
        state = AdamWStateTree(
            {NAME: values}, {NAME: mx.ones_like(values) * .1},
            {NAME: mx.ones_like(values) * .01},
            {NAME: mx.array([2, 3], dtype=mx.uint64)})
        self.parent = __import__(
            "bilqis_mlx.learning.atlas_candidate", fromlist=["CandidateState"]
        ).CandidateState(
            state, PlasticityPolicy('ADAPTIVE', 7, (IdentityRowAge(0, 0, 7),
                                                     IdentityRowAge(0, 1, 2))),
            MotifAllocationSnapshot(MotifManifest(RELEASE)), 11)
        self.hp = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)

    def gradients(self):
        return {NAME: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32)}

    def step(self, candidate, execution):
        return candidate_step(
            candidate, self.gradients(), execution, self.hp, decay={NAME: True},
            loss_bearing=True, max_norm=1.)

    def test_raw_caller_mask_is_not_an_execution_authority(self):
        candidate = begin_candidate(self.parent)
        with self.assertRaises(BilqisError):
            self.step(candidate, {NAME: mx.array([True, False])})
        with self.assertRaises(BilqisError):
            self.step(candidate, mx.array([True, False]))

    def test_forged_provenance_cannot_be_constructed_by_a_caller(self):
        issued = execution_provenance(self.parent, rows=(0,))
        with self.assertRaises(BilqisError):
            StepExecutionProvenance(
                issued.participation, issued.mask, issued.eligible_parameter_names,
                issued.extents_sha256, issued.run_id, issued.generation,
                issued.parent_manifest_sha256,
                issued.parent_candidate_identity_sha256,
                issued.parent_optimizer_step, issued.topology_digest)
        with self.assertRaises(BilqisError):
            replace(issued, mask=issued.mask)

    def test_recorded_proof_binds_the_owner_derived_mask(self):
        issued = execution_provenance(self.parent, rows=(0,))
        candidate = self.step(begin_candidate(self.parent), issued)
        self.assertEqual(len(candidate.step_proofs), 1)
        proof = candidate.step_proofs[0]
        self.assertEqual(proof.provenance_sha256, issued.digest)
        self.assertEqual(proof.parameter_names, (NAME,))
        self.assertTrue(proof.loss_bearing)
        accepted = resolve_candidate(candidate, accepted=True)
        np.testing.assert_array_equal(
            np.asarray(accepted.optimizer.update_counts[NAME]), [3, 3])

    def test_unparticipating_rows_never_advance(self):
        candidate = self.step(begin_candidate(self.parent), execution_provenance(self.parent, rows=()))
        accepted = resolve_candidate(candidate, accepted=True)
        np.testing.assert_array_equal(
            np.asarray(accepted.optimizer.update_counts[NAME]), [2, 3])

    def test_provenance_for_another_parameter_set_is_refused(self):
        issued = execution_provenance(self.parent, rows=(0,))
        with self.assertRaises(BilqisError):
            other = replace(issued, eligible_parameter_names=("features.norm",))
            self.step(begin_candidate(self.parent), other)


if __name__ == "__main__":
    unittest.main()
