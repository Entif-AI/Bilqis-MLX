"""Fail-closed production path for B09.2/B12.2 candidate steps."""
from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import (
    CandidateCustodyIdentity, CandidateState, begin_candidate,
)
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import (
    GroupEligibility, IdentityRowAge, PlasticityPolicy,
)
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step
from bilqis_mlx.runtime.atlas_model import BamfGradientExecution
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters, AdamWStateTree, reconcile_b01_optimizer_manifest,
)
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, Initializer, ModelTopologySpecV2, ParameterGroup,
    ParameterSpec,
)

BANK = "identity.bank.0"
FEATURE = "features.type"
RELEASE = "b" * 64
DECLARED = (ParameterSpec(
    BANK, (2, 2), Initializer.EMBEDDING, ParameterGroup.IDENTITY_ROW_AGE, True),)
NO_DECAY_DECLARED = (ParameterSpec(
    BANK, (2, 2), Initializer.EMBEDDING, ParameterGroup.IDENTITY_ROW_AGE, False),)
ORDERED_DECLARED = (
    ParameterSpec(
        BANK, (2, 2), Initializer.EMBEDDING,
        ParameterGroup.IDENTITY_ROW_AGE, True),
    ParameterSpec(
        FEATURE, (2, 2), Initializer.EMBEDDING,
        ParameterGroup.FAST, False),
)
CENSUS_SHAPE = (
    "bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
    "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes",
    "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
    "bilqis_mlx.runtime.topology_v2.validation.expected_bamf_shapes",
)
DIGEST_SHAPE = (
    "bilqis_mlx.runtime.topology_v2.validation.expected_bamf_shapes",
    "bilqis_mlx.runtime.backbone_identity.expected_bamf_shapes",
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
                patch(CENSUS_SHAPE[1], return_value=DECLARED), \
                patch(CENSUS_SHAPE[2], return_value=DECLARED), \
                patch(CENSUS_SHAPE[3], return_value=DECLARED):
            return production_candidate_step(
                candidate, {BANK: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32)},
                loss_bearing_target=loss_bearing_target,
                group_eligible=eligibility or self.eligibility(),
                spec=ModelTopologySpecV2(), extents=self.extents,
                run_id=self.parent.custody.run_id,
                generation=self.parent.custody.generation + 1,
                parent_manifest_sha256=self.parent.custody.manifest_sha256,
                parent_candidate_identity_sha256=candidate_identity_digest(self.parent),
                parent_optimizer_step=self.parent.optimizer_step,
                topology_digest=self.parent.custody.topology_digest,
                candidate_step_ordinal=1,
                teacher_hparams=self.hp, max_norm=1.)

    def gradient_execution(self, manifest_sha256):
        patches = (
            patch(DIGEST_SHAPE[0], return_value=DECLARED),
            patch(DIGEST_SHAPE[1], return_value=DECLARED),
            patch(CENSUS_SHAPE[2], return_value=DECLARED),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        execution = SimpleNamespace(
            output=SimpleNamespace(
                generation_binding=execution_generation_digest(
                    self.parent.optimizer.parameters,
                    spec=ModelTopologySpecV2(), extents=self.extents,
                )
            ),
            custody_run_id=self.parent.custody.run_id,
            custody_generation=self.parent.custody.generation,
            custody_manifest_sha256=manifest_sha256,
        )
        gradient = object.__new__(BamfGradientExecution)
        object.__setattr__(gradient, "execution", execution)
        object.__setattr__(gradient, "gradients", {BANK: mx.zeros((2, 2))})
        return gradient

    def test_step_accepts_no_caller_execution_or_motif_facts(self):
        parameters = set(inspect.signature(production_candidate_step).parameters)
        for forbidden in (
                "motif_reads", "executed_parameter_names", "visible_identity_rows",
                "feedback_identity_rows", "local_slot_rows", "active_admitted"):
            self.assertNotIn(forbidden, parameters)

    def test_decay_manifest_is_derived_from_b01_not_the_caller(self):
        parameters = set(inspect.signature(production_candidate_step).parameters)
        self.assertNotIn("decay", parameters)
        candidate = begin_candidate(self.parent)
        marker = object()
        with patch(CENSUS_SHAPE[0], return_value=NO_DECAY_DECLARED), \
                patch(CENSUS_SHAPE[1], return_value=NO_DECAY_DECLARED), \
                patch(CENSUS_SHAPE[2], return_value=NO_DECAY_DECLARED), \
                patch(CENSUS_SHAPE[3], return_value=NO_DECAY_DECLARED), \
                patch(
                    "bilqis_mlx.runtime.atlas_candidate_step.candidate_step",
                    return_value=marker,
                ) as apply_step:
            result = production_candidate_step(
                candidate,
                {BANK: mx.zeros((2, 2), dtype=mx.float32)},
                loss_bearing_target=False,
                group_eligible=self.eligibility(),
                spec=ModelTopologySpecV2(), extents=self.extents,
                run_id=self.parent.custody.run_id,
                generation=self.parent.custody.generation + 1,
                parent_manifest_sha256=self.parent.custody.manifest_sha256,
                parent_candidate_identity_sha256=candidate_identity_digest(self.parent),
                parent_optimizer_step=self.parent.optimizer_step,
                topology_digest=self.parent.custody.topology_digest,
                candidate_step_ordinal=1,
                teacher_hparams=self.hp, max_norm=1.,
            )
        self.assertIs(result, marker)
        self.assertEqual(apply_step.call_args.kwargs["decay"], {BANK: False})

    def test_b01_manifest_rejects_wrong_count_geometry_and_misowned_prefix(self):
        optimizer = self.parent.optimizer
        scalar_count = AdamWStateTree(
            optimizer.parameters, optimizer.m, optimizer.v,
            {BANK: mx.array(2, dtype=mx.uint64)})
        wrong_name = "frame.identity.bank.0"
        misowned = AdamWStateTree(
            {wrong_name: optimizer.parameters[BANK]},
            {wrong_name: optimizer.m[BANK]},
            {wrong_name: optimizer.v[BANK]},
            {wrong_name: optimizer.update_counts[BANK]})
        with patch(CENSUS_SHAPE[2], return_value=DECLARED), \
                patch(CENSUS_SHAPE[3], return_value=DECLARED):
            for malformed in (scalar_count, misowned):
                with self.subTest(keys=tuple(malformed.parameters)), \
                        self.assertRaises(BilqisError):
                    reconcile_b01_optimizer_manifest(
                        malformed, ModelTopologySpecV2(), self.extents)

    def test_b01_manifest_rejects_valid_tree_reordered_away_from_ledger(self):
        values = mx.ones((2, 2), dtype=mx.float32)
        reversed_names = (FEATURE, BANK)
        state = AdamWStateTree(
            {name: values for name in reversed_names},
            {name: mx.zeros_like(values) for name in reversed_names},
            {name: mx.zeros_like(values) for name in reversed_names},
            {name: mx.zeros((2,), dtype=mx.uint64) for name in reversed_names},
        )
        with patch(CENSUS_SHAPE[2], return_value=ORDERED_DECLARED), \
                patch(CENSUS_SHAPE[3], return_value=ORDERED_DECLARED), \
                self.assertRaises(BilqisError):
            reconcile_b01_optimizer_manifest(
                state, ModelTopologySpecV2(), self.extents)

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

    def test_matching_b13_custody_reaches_the_execution_binder(self):
        candidate = begin_candidate(self.parent)
        gradient = self.gradient_execution(self.parent.custody.manifest_sha256)
        marker = object()
        accepted = object()
        with patch.object(BamfGradientExecution, "__post_init__", return_value=None), \
                patch(
                    "bilqis_mlx.runtime.atlas_candidate_step.bind_execution_provenance",
                    return_value=marker,
                ) as binder, \
                patch(
                    "bilqis_mlx.runtime.atlas_candidate_step.candidate_step",
                    return_value=accepted,
                ) as apply_step:
            result = production_candidate_step(
                candidate,
                loss_bearing_target=True,
                gradient_execution=gradient,
                group_eligible=self.eligibility(),
                spec=ModelTopologySpecV2(), extents=self.extents,
                run_id=self.parent.custody.run_id,
                generation=self.parent.custody.generation + 1,
                parent_manifest_sha256=self.parent.custody.manifest_sha256,
                parent_candidate_identity_sha256=candidate_identity_digest(self.parent),
                parent_optimizer_step=self.parent.optimizer_step,
                topology_digest=self.parent.custody.topology_digest,
                candidate_step_ordinal=1,
                teacher_hparams=self.hp, max_norm=1.,
            )
        self.assertIs(result, accepted)
        self.assertIs(binder.call_args.kwargs["loss_execution"], gradient.execution)
        self.assertIs(apply_step.call_args.args[1], gradient.gradients)

    def test_sibling_b13_manifest_cannot_replay_gradient_execution(self):
        candidate = begin_candidate(self.parent)
        gradient = self.gradient_execution("7" * 64)
        with patch.object(BamfGradientExecution, "__post_init__", return_value=None), \
                patch(
                    "bilqis_mlx.runtime.atlas_candidate_step.bind_execution_provenance",
                ) as binder:
            with self.assertRaises(BilqisError):
                production_candidate_step(
                    candidate,
                    loss_bearing_target=True,
                    gradient_execution=gradient,
                    group_eligible=self.eligibility(),
                    spec=ModelTopologySpecV2(), extents=self.extents,
                    run_id=self.parent.custody.run_id,
                    generation=self.parent.custody.generation + 1,
                    parent_manifest_sha256=self.parent.custody.manifest_sha256,
                    parent_candidate_identity_sha256=candidate_identity_digest(self.parent),
                    parent_optimizer_step=self.parent.optimizer_step,
                    topology_digest=self.parent.custody.topology_digest,
                    candidate_step_ordinal=1,
                    teacher_hparams=self.hp, max_norm=1.,
                )
        binder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
