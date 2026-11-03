"""Production-path adversaries for the B09.2 execution binder.

The binder is the production entry point for candidate-step participation. It
must derive participation from the execution and read owners, and it must not
accept a caller-asserted mask or a forged group classification.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram_reads import MotifReadResult
from bilqis_mlx.learning.atlas_execution_provenance import (
    StepExecutionProvenance,
)
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
    ParameterSpec(BANK, (2, 2), Initializer.MATRIX, ParameterGroup.IDENTITY_ROW_AGE, True),
    ParameterSpec(MOTIF, (8, 8), Initializer.MATRIX, ParameterGroup.FAST, True),
)
EXTENTS = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
CENSUS_SHAPE = ("bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
                 "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes")


def motif_read(slots):
    """One B08 read-owner result with the given participating motif slots."""
    width = ModelTopologySpecV2.width
    return MotifReadResult(
        mx.zeros((1, 1, width), dtype=mx.float32), (("MISS",),), tuple(slots), (None,))


def eligibility(mode="FULL", admitted=((0, 0),), eligible=(BANK, MOTIF)):
    return GroupEligibility(
        mode=mode, eligible_parameter_names=tuple(eligible),
        frozen_parameter_names=(), admitted_identity_rows=tuple(admitted),
        fast_identity_rows=tuple(admitted), established_identity_rows=())


class ExecutionBinderProductionTests(unittest.TestCase):
    def bind(self, **overrides):
        evidence = {
            "motif_reads": (motif_read((0,)),),
            "executed_parameter_names": (BANK, MOTIF),
            "visible_identity_rows": ((0, 0),),
            "feedback_identity_rows": (),
            "local_slot_rows": (),
            "loss_bearing_target": True,
            "group_eligible": eligibility(),
            "active_admitted": ActiveAdmittedRows(
                identity_rows=((0, 0),), motif_slots=(0,)),
            "spec": ModelTopologySpecV2(),
            "extents": EXTENTS,
        }
        evidence.update(overrides)
        with patch(CENSUS_SHAPE[0], return_value=DECLARED), \
                patch(CENSUS_SHAPE[1], return_value=DECLARED):
            return bind_execution_provenance(**evidence)

    def test_binder_derives_participation_from_the_read_owners(self):
        provenance = self.bind()
        motif = provenance.mask.parameter(MOTIF)
        self.assertEqual(motif.row_indices, (0,))
        self.assertEqual(provenance.mask.parameter(BANK).row_indices, (0,))
        self.assertTrue(provenance.mask.has_loss_bearing_target)

    def test_unread_motif_slots_cannot_be_claimed(self):
        provenance = self.bind(motif_reads=(motif_read(()),))
        self.assertEqual(provenance.mask.parameter(MOTIF).row_indices, ())

    def test_forged_fast_reclassification_of_a_slow_parameter_is_refused(self):
        forged = eligibility(mode="FAST", admitted=((0, 0),), eligible=(BANK, MOTIF))
        with self.assertRaises(BilqisError):
            self.bind(group_eligible=forged)

    def test_caller_cannot_construct_the_provenance(self):
        provenance = self.bind()
        with self.assertRaises(BilqisError):
            StepExecutionProvenance(
                provenance.participation, provenance.mask,
                provenance.eligible_parameter_names, provenance.extents_sha256)

    def test_same_execution_evidence_reproduces_the_same_provenance(self):
        self.assertEqual(self.bind().digest, self.bind().digest)
        self.assertNotEqual(
            self.bind().digest,
            self.bind(executed_parameter_names=(BANK,)).digest)


if __name__ == "__main__":
    unittest.main()
