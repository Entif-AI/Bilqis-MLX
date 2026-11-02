"""Adversarial B12.2 candidate issuance and resolution authority witnesses."""
from dataclasses import replace
from unittest import TestCase

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning._retention import atlas_candidate as candidate_owner
from bilqis_mlx.learning._engram.tests.motif_fixtures import RELEASE, source
from bilqis_mlx.learning.atlas_engram import MotifBudget, MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning._retention.atlas_candidate import (
    CandidateInitialization, CandidateResolution, CandidateState, CandidateTransaction,
    bind_initial_candidate_state, begin_candidate, candidate_step, resolve_candidate,
)
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters, AdamWStateTree, _create_unbound_bamf_optimizer,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    FEATURE_NONE_ROW, GenerationExtents, Initializer, ModelTopologySpecV2,
    expected_bamf_shapes,
)


class CandidateAuthorityTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topology = ModelTopologySpecV2()
        cls.extents = GenerationExtents(1, 1, RELEASE, "b" * 64, "c" * 64)
        cls.state, cls.decay, _manifest = _create_unbound_bamf_optimizer(
            cls.topology, cls.extents, run_seed=475)
        cls.parent = bind_initial_candidate_state(
            cls.state, MotifAllocationSnapshot(MotifManifest(RELEASE)),
            topology=cls.topology, extents=cls.extents, run_seed=475)

    def setUp(self):
        self.hp = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)
        self.name = 'identity.bank.0'

    def step(self, candidate):
        gradients = {
            name: mx.zeros_like(value)
            for name, value in candidate.optimizer.parameters.items()
        }
        gradients[self.name][0] = mx.array(
            [3.] * gradients[self.name].shape[1], dtype=mx.float32)
        participation = {
            name: mx.zeros(count.shape, dtype=mx.bool_)
            for name, count in candidate.optimizer.update_counts.items()
        }
        participation[self.name][0] = True
        return candidate_step(
            candidate, gradients, participation, self.hp, decay=self.decay,
            loss_bearing=True, max_norm=1.)

    def test_seed_invariant_none_row_cannot_be_last_witness(self):
        counts = dict(self.parent.optimizer.update_counts)
        seed_sensitive = {
            Initializer.MATRIX, Initializer.EMBEDDING, Initializer.FEATURE_TABLE,
        }
        for item in expected_bamf_shapes(self.topology, self.extents):
            if item.initializer not in seed_sensitive:
                continue
            current = counts[item.name]
            if current.ndim == 0:
                counts[item.name] = mx.array(1, dtype=current.dtype)
                continue
            exhausted = mx.ones(current.shape, dtype=current.dtype)
            if item.initializer is Initializer.FEATURE_TABLE:
                exhausted[FEATURE_NONE_ROW] = mx.array(0, dtype=current.dtype)
            counts[item.name] = exhausted
        exhausted_optimizer = AdamWStateTree(
            self.parent.optimizer.parameters, self.parent.optimizer.m,
            self.parent.optimizer.v, counts)
        with self.assertRaises(BilqisError):
            CandidateState(
                exhausted_optimizer, self.parent.policy, self.parent.allocations,
                self.parent.optimizer_step,
                CandidateInitialization(self.topology, self.extents, 999))

    def test_replay_valid_rejected_transaction_cannot_mint_retained_descendant(self):
        candidate = begin_candidate(
            self.parent, frames=(source(),), budget=MotifBudget(1))
        self.assertIs(resolve_candidate(candidate, accepted=True), self.parent)
        with self.assertRaises(BilqisError):
            CandidateState(
                candidate.optimizer, self.parent.policy, candidate.allocations,
                self.parent.optimizer_step, self.parent.initialization,
                self.parent, CandidateResolution(candidate, False))

    def test_forged_resolution_cannot_mint_retained_descendant(self):
        candidate = self.step(begin_candidate(self.parent))
        forged = CandidateResolution(candidate, True)
        with self.assertRaises(BilqisError):
            CandidateState(
                candidate.optimizer, self.parent.policy, candidate.allocations,
                self.parent.optimizer_step + 1, self.parent.initialization,
                self.parent, forged)

    def test_resolution_rejects_resolution_pointer_retarget(self):
        candidate = self.step(begin_candidate(self.parent))
        later = self.step(candidate)
        accepted = resolve_candidate(candidate, accepted=True)
        resolution = accepted.resolution
        object.__setattr__(resolution, "candidate", later)
        with self.assertRaises(BilqisError):
            CandidateState(
                later.optimizer, accepted.policy, later.allocations, 2,
                self.parent.initialization, self.parent, resolution)

    def test_resolution_rejects_mutated_exact_transaction_object(self):
        candidate = self.step(begin_candidate(self.parent))
        later = self.step(candidate)
        accepted = resolve_candidate(candidate, accepted=True)
        for name in ('optimizer', 'update_steps', 'steps'):
            object.__setattr__(candidate, name, getattr(later, name))
        with self.assertRaises(BilqisError):
            CandidateState(
                later.optimizer, accepted.policy, later.allocations, 2,
                self.parent.initialization, self.parent, accepted.resolution)

    def test_rejected_numerical_state_cannot_take_fresh_attempt_token(self):
        rejected = self.step(begin_candidate(self.parent))
        self.assertIs(resolve_candidate(rejected, accepted=False), self.parent)
        fresh = begin_candidate(self.parent)
        with self.assertRaises(BilqisError):
            replace(rejected, attempt=fresh.attempt)

    def test_attempt_token_cannot_cross_parent_lineage(self):
        other_state, _decay, _manifest = _create_unbound_bamf_optimizer(
            self.topology, self.extents, run_seed=476)
        other = bind_initial_candidate_state(
            other_state, MotifAllocationSnapshot(MotifManifest(RELEASE)),
            topology=self.topology, extents=self.extents, run_seed=476)
        issued = begin_candidate(self.parent)
        forged = object.__new__(CandidateTransaction)
        for name, value in (
            ('parent', other), ('optimizer', other.optimizer),
            ('allocations', other.allocations), ('teacher_requests_full', False),
            ('attempt', issued.attempt), ('update_steps', 0), ('frames', ()),
            ('budget', MotifBudget(0)), ('steps', ()),
            ('schema_version', issued.schema_version),
        ):
            object.__setattr__(forged, name, value)
        with self.assertRaises(BilqisError):
            forged.__post_init__()

    def test_resolved_attempt_cannot_continue_numerical_evolution(self):
        candidate = self.step(begin_candidate(self.parent))
        resolve_candidate(candidate, accepted=True)
        with self.assertRaises(BilqisError):
            self.step(candidate)

    def test_candidate_optimizer_cannot_mutate_retained_parent_by_alias(self):
        candidate = begin_candidate(self.parent)
        before = np.asarray(self.parent.optimizer.parameters[self.name]).copy()

        candidate.optimizer.parameters[self.name][0, 0] = (
            candidate.optimizer.parameters[self.name][0, 0] + 1)

        np.testing.assert_array_equal(
            np.asarray(self.parent.optimizer.parameters[self.name]), before)

    def test_materialized_candidate_does_not_alias_untouched_parent_leaf(self):
        name = 'blocks.0.query'
        before = np.asarray(self.parent.optimizer.parameters[name]).copy()
        candidate = begin_candidate(
            self.parent, frames=(source(),), budget=MotifBudget(1))

        candidate.optimizer.parameters[name][0, 0] = (
            candidate.optimizer.parameters[name][0, 0] + 1)

        np.testing.assert_array_equal(
            np.asarray(self.parent.optimizer.parameters[name]), before)

    def test_nested_proof_retarget_rejects_before_resolution(self):
        candidate = self.step(begin_candidate(self.parent))
        proof = candidate.steps[0]
        proof.gradients[self.name][0] = mx.array(
            [6.] * proof.gradients[self.name].shape[1], dtype=mx.float32)

        from bilqis_mlx.runtime.atlas_optimizer import _adamw_update
        rewritten = _adamw_update(
            candidate.parent.optimizer, proof.gradients, proof.update_mask,
            proof.teacher_hparams, decay=proof.decay,
            loss_bearing=proof.loss_bearing, max_norm=proof.max_norm)
        for field in ('parameters', 'm', 'v', 'update_counts'):
            getattr(candidate.optimizer, field)[self.name][:] = getattr(
                rewritten, field)[self.name]

        with self.assertRaises(BilqisError):
            resolve_candidate(candidate, accepted=True)

    def test_masked_off_proof_mutation_invalidates_issued_resolution(self):
        candidate = self.step(begin_candidate(self.parent))
        accepted = resolve_candidate(candidate, accepted=True)
        proof = candidate.steps[0]
        self.assertFalse(bool(proof.update_mask[self.name][1]))

        proof.gradients[self.name][1] = mx.ones_like(
            proof.gradients[self.name][1]) * 37

        with self.assertRaises(BilqisError):
            accepted.__post_init__()

    def test_no_generic_transaction_issuer_or_public_constructor(self):
        self.assertFalse(hasattr(candidate_owner, "_issue_transaction"))
        with self.assertRaises(BilqisError):
            CandidateTransaction(self.parent, self.state, self.parent.allocations, False, 1)

    def test_caller_cannot_replace_optimizer_or_allocation(self):
        legitimate = self.step(begin_candidate(
            self.parent, frames=(source(),), budget=MotifBudget(0)))
        with self.assertRaises(BilqisError):
            replace(legitimate, optimizer=self.parent.optimizer)
        forged = replace(legitimate.allocations, observed_uses=(
            (legitimate.allocations.observed_uses[0][0], 999),))
        with self.assertRaises(BilqisError):
            replace(legitimate, allocations=forged)
        self.assertEqual(resolve_candidate(legitimate, accepted=True).optimizer_step, 1)
