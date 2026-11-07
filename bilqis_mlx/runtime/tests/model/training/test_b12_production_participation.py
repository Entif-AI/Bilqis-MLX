"""B12 parent witness across B11 execution, B09 binding, and AdamW custody."""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import (
    CandidateCustodyIdentity, CandidateState, begin_candidate,
)
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_reads import MotifReadResult
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import (
    GroupEligibility, IdentityRowAge, PlasticityPolicy,
)
from bilqis_mlx.learning.atlas_readout import LossParts, ModelOutput
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step
from bilqis_mlx.runtime.atlas_model import BamfGradientExecution
from bilqis_mlx.runtime.atlas_model_contracts import (
    _FORWARD_ISSUANCE, _LOSS_EXECUTION_ISSUER, _ForwardRecord,
    _issue_loss_execution,
)
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, Initializer, ModelTopologySpecV2, ParameterGroup,
    ParameterSpec,
)


BANK = "identity.bank.0"
MOTIF = "motif.page.0"
DECLARED = (
    ParameterSpec(
        BANK, (2, 2), Initializer.EMBEDDING,
        ParameterGroup.IDENTITY_ROW_AGE, True),
    ParameterSpec(
        MOTIF, (2, 2), Initializer.EMBEDDING,
        ParameterGroup.FAST, True),
)
SHAPE_OWNERS = (
    "bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
    "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes",
    "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
    "bilqis_mlx.runtime.topology_v2.validation.expected_bamf_shapes",
    "bilqis_mlx.runtime.backbone_identity.expected_bamf_shapes",
)


def _parent():
    bank = mx.array([[1., 2.], [3., 4.]], dtype=mx.float32)
    motif = mx.array([[5., 6.], [7., 8.]], dtype=mx.float32)
    optimizer = AdamWStateTree(
        {BANK: bank, MOTIF: motif},
        {BANK: mx.zeros_like(bank), MOTIF: mx.zeros_like(motif)},
        {BANK: mx.zeros_like(bank), MOTIF: mx.zeros_like(motif)},
        {
            BANK: mx.array([4, 0], dtype=mx.uint64),
            MOTIF: mx.array([0, 5], dtype=mx.uint64),
        },
    )
    allocations = MotifAllocationSnapshot(MotifManifest("b" * 64))
    extents = GenerationExtents(
        1, 1, "a" * 64, allocations.manifest.digest, "c" * 64)
    spec = ModelTopologySpecV2()
    state = CandidateState(
        optimizer,
        PlasticityPolicy(
            "FOUNDATION", 0,
            (IdentityRowAge(0, 0, 4), IdentityRowAge(0, 1, 0)),
        ),
        allocations,
        11,
        CandidateCustodyIdentity(
            "fixture-run", 0, "6" * 64, spec.digest, extents.digest),
    )
    return state, spec, extents


def _synthetic_b11_gradient_fixture(parent, spec, extents, gradients):
    """Mint deterministic B11-shaped facts for the B09/B12 seam only."""
    generation = execution_generation_digest(
        parent.optimizer.parameters, spec=spec, extents=extents)
    output = object.__new__(ModelOutput)
    object.__setattr__(output, "plan", SimpleNamespace(generation_binding=generation))
    motif_read = MotifReadResult(
        mx.zeros((1, 1, 768), dtype=mx.float32),
        (("EXACT",),), (0,), ("a" * 64,),
    )
    record = _ForwardRecord(
        generation,
        parent.custody.run_id,
        parent.custody.generation,
        parent.custody.manifest_sha256,
        (), (), (), (), (motif_read,), (), None,
    )
    _FORWARD_ISSUANCE.issue(output, record)
    zero = mx.array(0.0, dtype=mx.float32)
    execution = _issue_loss_execution(
        output, LossParts(zero, zero, zero, zero), record,
        ((), ((0, 1),), (), ()),
    )
    gradient = object.__new__(BamfGradientExecution)
    for name, value in (
            ("execution", execution), ("gradients", gradients),
            ("loss_total", zero),
            ("schema_version", "bilqis.mlx.b11-gradient-execution/v1"),
            ("_issuance", _LOSS_EXECUTION_ISSUER)):
        object.__setattr__(gradient, name, value)
    gradient.__post_init__()
    return gradient


class B12ProductionParticipationTests(TestCase):
    def test_output_denominator_and_motif_read_reach_real_transaction(self):
        parent, spec, extents = _parent()
        eligibility = GroupEligibility(
            "FULL", (BANK, MOTIF), (), ((0, 0), (0, 1)),
            ((0, 0), (0, 1)), (),
        )
        gradients = {
            BANK: mx.array([[1e9, -1e9], [1., -2.]], dtype=mx.float32),
            MOTIF: mx.array([[2., -1.], [1e9, -1e9]], dtype=mx.float32),
        }
        with ExitStack() as stack:
            for target in SHAPE_OWNERS:
                stack.enter_context(patch(target, return_value=DECLARED))
            gradient = _synthetic_b11_gradient_fixture(
                parent, spec, extents, gradients)
            candidate = production_candidate_step(
                begin_candidate(parent), loss_bearing_target=True,
                gradient_execution=gradient, group_eligible=eligibility,
                spec=spec, extents=extents,
                run_id=parent.custody.run_id,
                generation=parent.custody.generation + 1,
                parent_manifest_sha256=parent.custody.manifest_sha256,
                parent_candidate_identity_sha256=candidate_identity_digest(parent),
                parent_optimizer_step=parent.optimizer_step,
                topology_digest=parent.custody.topology_digest,
                candidate_step_ordinal=1,
                teacher_hparams=AdamWHyperparameters(.001, (.9, .95), 1e-8, .01),
                max_norm=1.,
            )

        self.assertEqual(candidate.update_steps, 1)
        self.assertTrue(candidate.step_proofs[0].loss_bearing)
        self.assertEqual(int(candidate.optimizer.update_counts[BANK][1]), 1)
        self.assertEqual(int(candidate.optimizer.update_counts[MOTIF][0]), 1)
        for name, untouched_row in ((BANK, 0), (MOTIF, 1)):
            for field in ("parameters", "m", "v", "update_counts"):
                np.testing.assert_array_equal(
                    np.asarray(getattr(candidate.optimizer, field)[name][untouched_row]),
                    np.asarray(getattr(parent.optimizer, field)[name][untouched_row]),
                )
        self.assertFalse(bool(mx.all(
            candidate.optimizer.parameters[BANK][1]
            == parent.optimizer.parameters[BANK][1])))
        self.assertFalse(bool(mx.all(
            candidate.optimizer.parameters[MOTIF][0]
            == parent.optimizer.parameters[MOTIF][0])))
