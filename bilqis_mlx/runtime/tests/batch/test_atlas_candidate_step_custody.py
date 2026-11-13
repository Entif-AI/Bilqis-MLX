"""B11 custody and C08 logical-batch binding for production candidate steps."""
from __future__ import annotations

import unittest
from dataclasses import replace
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
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.runtime.atlas_resources import BatchPlan
from bilqis_mlx.runtime.atlas_training_contracts import (
    BamfTrainingRow, _issue_training_batch,
)
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, Initializer, ModelTopologySpecV2, ParameterGroup,
    ParameterSpec,
)

BANK = "identity.bank.0"
RELEASE = "b" * 64
DECLARED = (ParameterSpec(
    BANK, (2, 2), Initializer.EMBEDDING, ParameterGroup.IDENTITY_ROW_AGE, True),)
CENSUS_SHAPE = (
    "bilqis_mlx.learning.atlas_participation_census.expected_bamf_shapes",
    "bilqis_mlx.learning._retention.atlas_participation_census.expected_bamf_shapes",
    "bilqis_mlx.runtime.model_topology_v2.expected_bamf_shapes",
)
DIGEST_SHAPE = (
    "bilqis_mlx.runtime.topology_v2.validation.expected_bamf_shapes",
    "bilqis_mlx.runtime.backbone_identity.expected_bamf_shapes",
)


class ProductionCandidateStepCustodyTests(unittest.TestCase):
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

    def eligibility(self):
        return GroupEligibility(
            mode="FULL", eligible_parameter_names=(BANK,), frozen_parameter_names=(),
            admitted_identity_rows=((0, 0),), fast_identity_rows=((0, 0),),
            established_identity_rows=())

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
            output=SimpleNamespace(generation_binding=execution_generation_digest(
                self.parent.optimizer.parameters,
                spec=ModelTopologySpecV2(), extents=self.extents)),
            custody_run_id=self.parent.custody.run_id,
            custody_generation=self.parent.custody.generation,
            custody_manifest_sha256=manifest_sha256,
        )
        gradient = object.__new__(BamfGradientExecution)
        object.__setattr__(gradient, "execution", execution)
        object.__setattr__(gradient, "gradients", {BANK: mx.zeros((2, 2))})
        return gradient

    def step_kwargs(self):
        return dict(
            group_eligible=self.eligibility(), spec=ModelTopologySpecV2(),
            extents=self.extents, run_id=self.parent.custody.run_id,
            generation=self.parent.custody.generation + 1,
            parent_manifest_sha256=self.parent.custody.manifest_sha256,
            parent_candidate_identity_sha256=candidate_identity_digest(self.parent),
            parent_optimizer_step=self.parent.optimizer_step,
            topology_digest=self.parent.custody.topology_digest,
            candidate_step_ordinal=1, teacher_hparams=self.hp, max_norm=1.)

    def test_matching_b13_custody_reaches_the_execution_binder(self):
        candidate = begin_candidate(self.parent)
        gradient = self.gradient_execution(self.parent.custody.manifest_sha256)
        marker, accepted = object(), object()
        with patch.object(BamfGradientExecution, "__post_init__", return_value=None), \
                patch("bilqis_mlx.runtime.atlas_candidate_step.bind_execution_provenance",
                      return_value=marker) as binder, \
                patch("bilqis_mlx.runtime.atlas_candidate_step.candidate_step",
                      return_value=accepted) as apply_step:
            result = production_candidate_step(
                candidate, loss_bearing_target=True,
                gradient_execution=gradient, **self.step_kwargs())
        self.assertIs(result, accepted)
        self.assertIs(binder.call_args.kwargs["loss_execution"], gradient.execution)
        self.assertIs(apply_step.call_args.args[1], gradient.gradients)

    def test_sibling_b13_manifest_cannot_replay_gradient_execution(self):
        candidate = begin_candidate(self.parent)
        gradient = self.gradient_execution("7" * 64)
        with patch.object(BamfGradientExecution, "__post_init__", return_value=None), \
                patch("bilqis_mlx.runtime.atlas_candidate_step.bind_execution_provenance") as binder, \
                self.assertRaises(BilqisError):
            production_candidate_step(
                candidate, loss_bearing_target=True,
                gradient_execution=gradient, **self.step_kwargs())
        binder.assert_not_called()

    def test_logical_batch_plan_drift_rejects_before_execution_binding(self):
        candidate = begin_candidate(self.parent)
        rows = tuple(BamfTrainingRow(
            None, None, None, SimpleNamespace(row_id=row_id, optimizer_step_seed=7))
            for row_id in ("row:a", "row:b"))
        batch = _issue_training_batch(
            "4" * 64, "generation:test", "5" * 64, "A.TEST", rows)
        plan = BatchPlan(
            groups=((0,), (1,)), logical_row_ids=("row:a", "row:b"),
            microbatch_size=1, estimated_peak_bytes=100, resident_bytes=50,
            optimizer_step_seed=7, generation_binding="generation:test",
            topology_digest=ModelTopologySpecV2().digest,
            memory_budget_digest="6" * 64, source_digest="7" * 64)
        gradients = {BANK: mx.zeros((2, 2))}
        groups = replace(plan, groups=((0, 1),), microbatch_size=2)
        seed = replace(plan, optimizer_step_seed=8)
        source = replace(plan, source_digest="8" * 64)
        rows_drift = replace(plan, logical_row_ids=("row:b", "row:a"))
        generation = replace(plan, generation_binding="generation:other")
        topology = replace(plan, topology_digest="9" * 64)
        cases = (
            ("plan-digest", groups, plan.digest, plan.source_digest, plan.generation_binding),
            ("optimizer-seed", seed, seed.digest, seed.source_digest, seed.generation_binding),
            ("source-digest", source, source.digest, plan.source_digest, source.generation_binding),
            ("row-order", rows_drift, rows_drift.digest,
             rows_drift.source_digest, rows_drift.generation_binding),
            ("generation-binding", generation, generation.digest,
             generation.source_digest, generation.generation_binding),
            ("topology-digest", topology, topology.digest,
             topology.source_digest, topology.generation_binding),
        )
        for name, drift, plan_digest, source_digest, generation_binding in cases:
            logical = SimpleNamespace(
                plan_digest=plan_digest, source_digest=source_digest,
                generation_binding=generation_binding,
                loss_executions=(), gradients=gradients)
            with self.subTest(case=name), patch(
                    "bilqis_mlx.runtime.atlas_candidate_step.require_logical_batch_gradient_execution",
                    return_value=logical), patch(
                    "bilqis_mlx.runtime.atlas_candidate_step.bind_execution_provenance_many") as binder, \
                    self.assertRaises(BilqisError) as caught:
                production_candidate_step(
                    candidate, loss_bearing_target=True,
                    logical_batch_execution=logical, training_batch=batch,
                    logical_batch_plan=drift, **self.step_kwargs())
            self.assertEqual(
                caught.exception.context["reason"], "C08_LOGICAL_BATCH_PLAN_DRIFT")
            binder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
