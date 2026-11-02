"""B12.2 disposable candidate rollback and accepted-clock witnesses."""
from dataclasses import replace
from unittest import TestCase

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning._retention import atlas_candidate as candidate_owner
from bilqis_mlx.learning._engram.tests.motif_fixtures import RELEASE, full_first_page, source
from bilqis_mlx.learning.atlas_engram import MotifBudget, MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters, AdamWStateTree, _create_unbound_bamf_optimizer,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    FEATURE_NONE_ROW, GenerationExtents, Initializer, ModelTopologySpecV2,
    expected_bamf_shapes, initialize_bamf_row,
)
from bilqis_mlx.learning._retention.atlas_candidate import (
    CandidateInitialization, CandidateState, CandidateTransaction,
    bind_initial_candidate_state, begin_candidate, candidate_step, resolve_candidate,
)


class CandidateTransactionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topology = ModelTopologySpecV2()
        cls.extents = GenerationExtents(1, 1, RELEASE, "b" * 64, "c" * 64)
        cls.state, cls.decay, _manifest = _create_unbound_bamf_optimizer(
            cls.topology, cls.extents, run_seed=475)
        cls.parent = bind_initial_candidate_state(
            cls.state,
            MotifAllocationSnapshot(MotifManifest(RELEASE)),
            topology=cls.topology, extents=cls.extents, run_seed=475)

    def setUp(self):
        self.hp = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)
        self.name = 'identity.bank.0'

    def bound(self, *, run_seed=475, allocations=None):
        return bind_initial_candidate_state(
            self.state,
            MotifAllocationSnapshot(MotifManifest(RELEASE))
            if allocations is None else allocations,
            topology=self.topology, extents=self.extents, run_seed=run_seed)

    def step(self, candidate, mask=(True, False), *, loss_bearing=True, zero_gradient=False):
        gradients = {
            name: mx.zeros_like(value)
            for name, value in candidate.optimizer.parameters.items()
        }
        selected = mx.zeros_like(candidate.optimizer.parameters[self.name])
        if not zero_gradient:
            selected[0] = mx.array([3.] * selected.shape[1], dtype=mx.float32)
            selected[1] = mx.array(
                [3e38, -3e38] * (selected.shape[1] // 2), dtype=mx.float32)
        gradients[self.name] = selected
        participation = {
            name: mx.zeros(count.shape, dtype=mx.bool_)
            for name, count in candidate.optimizer.update_counts.items()
        }
        rows = mx.zeros(candidate.optimizer.update_counts[self.name].shape, dtype=mx.bool_)
        rows[0], rows[1] = mask
        participation[self.name] = rows
        return candidate_step(
            candidate, gradients, participation, self.hp, decay=self.decay,
            loss_bearing=loss_bearing, max_norm=1.)

    def snapshot(self, state):
        return tuple(np.asarray(getattr(state.optimizer, field)[self.name]).tobytes()
                     for field in ('parameters', 'm', 'v', 'update_counts'))

    def test_rejection_returns_exact_parent_with_all_custody(self):
        before = self.snapshot(self.parent)
        candidate = begin_candidate(self.parent, frames=(source(),), budget=MotifBudget(0))
        candidate = self.step(self.step(candidate))
        self.assertNotEqual(candidate.allocations.digest, self.parent.allocations.digest)
        self.assertIs(resolve_candidate(candidate, accepted=False), self.parent)
        self.assertEqual(self.snapshot(self.parent), before)
        self.assertEqual(self.parent.policy, PlasticityPolicy())
        self.assertEqual(self.parent.optimizer_step, 0)
        self.assertEqual(self.parent.allocations.observed_uses, ())

    def test_acceptance_moves_entire_state_once_for_two_steps(self):
        candidate = self.step(self.step(begin_candidate(self.parent)))
        accepted = resolve_candidate(candidate, accepted=True)
        np.testing.assert_array_equal(
            np.asarray(accepted.optimizer.update_counts[self.name][:2]), [2, 0])
        self.assertEqual(accepted.optimizer_step, 2)
        self.assertEqual(accepted.policy, PlasticityPolicy())
        self.assertEqual(candidate.update_mode, 'FULL')
        self.assertEqual(begin_candidate(accepted).update_mode, 'FULL')
        self.assertNotEqual(self.snapshot(accepted), self.snapshot(self.parent))
        for field in ('parameters', 'm', 'v', 'update_counts'):
            np.testing.assert_array_equal(np.asarray(getattr(accepted.optimizer, field)[self.name][1]),
                                          np.asarray(getattr(self.parent.optimizer, field)[self.name][1]))

    def test_changing_step_masks_preserve_row_local_counts(self):
        first = self.step(begin_candidate(self.parent))
        second = self.step(first, mask=(False, True), zero_gradient=True)
        accepted = resolve_candidate(second, accepted=True)
        self.assertEqual(accepted.policy, PlasticityPolicy())
        np.testing.assert_array_equal(
            np.asarray(accepted.optimizer.update_counts[self.name][:2]), [1, 1])

    def test_no_loss_or_wholly_frozen_candidate_cannot_advance_clocks_or_allocations(self):
        for kwargs in ({'loss_bearing': False}, {'mask': (False, False)}):
            candidate = begin_candidate(self.parent, frames=(source(),), budget=MotifBudget(0))
            result = self.step(candidate, **kwargs)
            self.assertIs(result, candidate)
            self.assertIs(resolve_candidate(result, accepted=True), self.parent)

    def test_fresh_custody_is_foundation_and_teacher_request_stays_full(self):
        self.assertEqual(self.parent.policy, PlasticityPolicy())
        for request in (False, True):
            candidate = self.step(begin_candidate(
                self.parent, teacher_requests_full=request))
            self.assertEqual(candidate.update_mode, 'FULL')
            self.assertEqual(resolve_candidate(candidate, accepted=True).policy.accepted_fast_since_full, 0)

    def test_no_generic_state_issuer_can_bypass_candidate_custody(self):
        self.assertFalse(hasattr(candidate_owner, "_issue_state"))
        self.assertFalse(hasattr(candidate_owner, "_STATE_ISSUER"))

    def test_invalid_state_and_decision_fail_before_parent_mutation(self):
        before = self.snapshot(self.parent)
        parameters = dict(self.state.parameters)
        parameters[self.name] = parameters[self.name] + 100
        forged = AdamWStateTree(
            parameters, self.state.m, self.state.v, self.state.update_counts)
        with self.assertRaises(BilqisError):
            CandidateState(
                forged, PlasticityPolicy(),
                MotifAllocationSnapshot(MotifManifest(RELEASE)), 0,
                CandidateInitialization(self.topology, self.extents, 475))
        with self.assertRaises(BilqisError):
            resolve_candidate(begin_candidate(self.parent), accepted=1)
        self.assertEqual(self.snapshot(self.parent), before)

    def test_prepopulated_allocations_cannot_claim_initial_b01_custody(self):
        with self.assertRaises(BilqisError):
            self.bound(allocations=MotifAllocationSnapshot(full_first_page()))

    def test_full_b01_tree_materializes_planned_motif_rows_without_touching_parent(self):
        topology, extents = self.topology, self.extents
        parent = self.bound()
        parent_page = mx.array(parent.optimizer.parameters["motif.page.0"])
        untouched = parent.optimizer.parameters["blocks.0.query"]

        candidate = begin_candidate(
            parent, frames=(source(),), budget=MotifBudget(2))

        self.assertEqual(len(candidate.allocations.manifest.slots), 2)
        declared = next(
            item for item in expected_bamf_shapes(topology, extents)
            if item.name == "motif.page.0")
        for slot in candidate.allocations.manifest.slots:
            expected = initialize_bamf_row(
                declared, run_seed=475, row_id=slot.key.digest)
            np.testing.assert_array_equal(
                np.asarray(candidate.optimizer.parameters["motif.page.0"][slot.slot_id]),
                expected)
            self.assertTrue(bool(mx.all(candidate.optimizer.m["motif.page.0"][slot.slot_id] == 0)))
            self.assertTrue(bool(mx.all(candidate.optimizer.v["motif.page.0"][slot.slot_id] == 0)))
            self.assertEqual(int(candidate.optimizer.update_counts["motif.page.0"][slot.slot_id]), 0)
        np.testing.assert_array_equal(
            np.asarray(parent.optimizer.parameters["motif.page.0"]),
            np.asarray(parent_page))
        self.assertIs(candidate.optimizer.parameters["blocks.0.query"], untouched)
        self.assertIs(resolve_candidate(candidate, accepted=False), parent)

    def test_materialization_binding_must_match_parent_release_and_capacity(self):
        topology, extents, optimizer = self.topology, self.extents, self.state
        for wrong in (
            GenerationExtents(1, 1, "f" * 64, "b" * 64, "c" * 64),
            GenerationExtents(1, 2, RELEASE, "b" * 64, "c" * 64),
        ):
            with self.subTest(extents=wrong), self.assertRaises(BilqisError):
                bind_initial_candidate_state(
                    optimizer,
                    MotifAllocationSnapshot(MotifManifest(RELEASE)),
                    topology=topology, extents=wrong, run_seed=475)

    def test_run_seed_is_replayed_against_actual_b01_tree(self):
        with self.assertRaises(BilqisError):
            self.bound(run_seed=999)

    def test_initialization_binding_rejects_incomplete_b01_parameter_tree(self):
        topology = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, RELEASE, "b" * 64, "c" * 64)
        name = self.name
        partial = AdamWStateTree(
            {name: self.parent.optimizer.parameters[name]},
            {name: self.parent.optimizer.m[name]},
            {name: self.parent.optimizer.v[name]},
            {name: self.parent.optimizer.update_counts[name]})
        with self.assertRaises(BilqisError):
            bind_initial_candidate_state(
                partial,
                MotifAllocationSnapshot(MotifManifest(RELEASE)),
                topology=topology, extents=extents, run_seed=475)

    def test_internal_seed_relabel_cannot_authorize_new_motif_rows(self):
        self.assertFalse(hasattr(candidate_owner, "_issue_initialization"))
        with self.assertRaises(BilqisError):
            CandidateState(
                self.parent.optimizer, self.parent.policy, self.parent.allocations,
                self.parent.optimizer_step,
                CandidateInitialization(self.topology, self.extents, 999))

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

    def test_no_generic_transaction_issuer_can_bypass_row_materialization(self):
        self.assertFalse(hasattr(candidate_owner, "_issue_transaction"))
        self.assertFalse(hasattr(candidate_owner, "_TRANSACTION_ISSUER"))

    def test_public_initial_binding_cannot_smuggle_page_growth_state(self):
        with self.assertRaises(BilqisError):
            self.bound(allocations=MotifAllocationSnapshot(full_first_page()))

    def test_caller_cannot_issue_transaction_with_arbitrary_optimizer_or_allocation(self):
        parameters = dict(self.parent.optimizer.parameters)
        counts = dict(self.parent.optimizer.update_counts)
        parameters[self.name] = parameters[self.name] + 100
        counts[self.name] = counts[self.name] + 1
        changed = AdamWStateTree(
            parameters,
            self.parent.optimizer.m, self.parent.optimizer.v,
            counts)
        with self.assertRaises(BilqisError):
            CandidateTransaction(self.parent, changed, self.parent.allocations, False, 1)
        legitimate = self.step(begin_candidate(self.parent, frames=(source(),), budget=MotifBudget(0)))
        with self.assertRaises(BilqisError):
            replace(legitimate, optimizer=changed)
        forged = replace(legitimate.allocations, observed_uses=(
            (legitimate.allocations.observed_uses[0][0], 999),))
        with self.assertRaises(BilqisError):
            replace(legitimate, allocations=forged)
        self.assertEqual(resolve_candidate(legitimate, accepted=True).optimizer_step, 1)
