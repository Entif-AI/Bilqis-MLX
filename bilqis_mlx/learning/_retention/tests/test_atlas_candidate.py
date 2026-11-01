"""B12.2 disposable candidate rollback and accepted-clock witnesses."""
from dataclasses import replace
from unittest import TestCase

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning._engram.tests.motif_fixtures import RELEASE, source
from bilqis_mlx.learning.atlas_engram import MotifBudget, MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
from bilqis_mlx.learning._retention.atlas_candidate import (
    CandidateState, CandidateTransaction, begin_candidate, candidate_step, resolve_candidate,
)


class CandidateTransactionTests(TestCase):
    def setUp(self):
        name = 'identity.bank.0'
        values = mx.array([[.5, -.25], [1., 2.]], dtype=mx.float32)
        state = AdamWStateTree({name: values}, {name: mx.ones_like(values) * .1},
                              {name: mx.ones_like(values) * .01},
                              {name: mx.array([2, 3], dtype=mx.uint64)})
        self.parent = CandidateState(
            state, PlasticityPolicy('ADAPTIVE', 7, (IdentityRowAge(0, 0, 7), IdentityRowAge(0, 1, 2))),
            MotifAllocationSnapshot(MotifManifest(RELEASE)), 11)
        self.hp = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)
        self.name = name

    def step(self, candidate, mask=(True, False), *, loss_bearing=True):
        return candidate_step(
            candidate, {self.name: mx.array([[3., 4.], [3e38, -3e38]], dtype=mx.float32)},
            {self.name: mx.array(mask)}, self.hp, decay={self.name: True},
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
        self.assertEqual(self.parent.policy.accepted_fast_since_full, 7)
        self.assertEqual(self.parent.optimizer_step, 11)
        self.assertEqual(self.parent.allocations.observed_uses, ())

    def test_acceptance_moves_entire_state_and_ages_once_for_two_steps(self):
        candidate = self.step(self.step(begin_candidate(self.parent)))
        accepted = resolve_candidate(candidate, accepted=True)
        np.testing.assert_array_equal(np.asarray(accepted.optimizer.update_counts[self.name]), [4, 3])
        self.assertEqual(accepted.optimizer_step, 13)
        self.assertEqual(tuple(r.accepted_age for r in accepted.policy.row_ages), (8, 2))
        self.assertEqual(accepted.policy.accepted_fast_since_full, 8)
        self.assertEqual(candidate.update_mode, 'FAST')
        self.assertEqual(begin_candidate(accepted).update_mode, 'FULL')
        self.assertNotEqual(self.snapshot(accepted), self.snapshot(self.parent))
        for field in ('parameters', 'm', 'v', 'update_counts'):
            np.testing.assert_array_equal(np.asarray(getattr(accepted.optimizer, field)[self.name][1]),
                                          np.asarray(getattr(self.parent.optimizer, field)[self.name][1]))

    def test_changing_step_masks_ages_union_once(self):
        first = self.step(begin_candidate(self.parent))
        second = candidate_step(
            first, {self.name: mx.zeros((2, 2), dtype=mx.float32)},
            {self.name: mx.array([False, True])}, self.hp, decay={self.name: True},
            loss_bearing=True, max_norm=1.)
        accepted = resolve_candidate(second, accepted=True)
        self.assertEqual(tuple(r.accepted_age for r in accepted.policy.row_ages), (8, 3))
        np.testing.assert_array_equal(np.asarray(accepted.optimizer.update_counts[self.name]), [3, 4])

    def test_no_loss_or_wholly_frozen_candidate_cannot_advance_clocks_or_allocations(self):
        for kwargs in ({'loss_bearing': False}, {'mask': (False, False)}):
            candidate = begin_candidate(self.parent, frames=(source(),), budget=MotifBudget(0))
            result = self.step(candidate, **kwargs)
            self.assertIs(result, candidate)
            self.assertIs(resolve_candidate(result, accepted=True), self.parent)

    def test_full_acceptance_resets_cadence_rejection_keeps_full_due(self):
        due = replace(self.parent, policy=replace(self.parent.policy, accepted_fast_since_full=8))
        candidate = self.step(begin_candidate(due))
        self.assertEqual(candidate.update_mode, 'FULL')
        self.assertIs(resolve_candidate(candidate, accepted=False), due)
        self.assertEqual(resolve_candidate(candidate, accepted=True).policy.accepted_fast_since_full, 0)
        self.assertEqual(begin_candidate(resolve_candidate(candidate, accepted=False)).update_mode, 'FULL')

    def test_teacher_full_and_foundation_use_existing_policy(self):
        for parent, request in ((self.parent, True),
                                (replace(self.parent, policy=PlasticityPolicy(row_ages=self.parent.policy.row_ages)), False)):
            candidate = self.step(begin_candidate(parent, teacher_requests_full=request))
            self.assertEqual(candidate.update_mode, 'FULL')
            self.assertEqual(resolve_candidate(candidate, accepted=True).policy.accepted_fast_since_full, 0)

    def test_invalid_state_and_decision_fail_before_parent_mutation(self):
        before = self.snapshot(self.parent)
        with self.assertRaises(BilqisError):
            replace(self.parent, optimizer_step=True)
        with self.assertRaises(BilqisError):
            replace(self.parent, policy=replace(self.parent.policy, row_ages=(IdentityRowAge(0, 3, 0),)))
        with self.assertRaises(BilqisError):
            resolve_candidate(begin_candidate(self.parent), accepted=1)
        self.assertEqual(self.snapshot(self.parent), before)

    def test_unmaterialized_slot_allocation_is_rejected(self):
        with self.assertRaises(BilqisError):
            begin_candidate(self.parent, frames=(source(),), budget=MotifBudget(2))

    def test_caller_cannot_issue_transaction_with_arbitrary_optimizer_or_allocation(self):
        changed = AdamWStateTree(
            {self.name: self.parent.optimizer.parameters[self.name] + 100},
            self.parent.optimizer.m, self.parent.optimizer.v,
            {self.name: self.parent.optimizer.update_counts[self.name] + 1})
        with self.assertRaises(BilqisError):
            CandidateTransaction(self.parent, changed, self.parent.allocations, False, 1)
        legitimate = self.step(begin_candidate(self.parent, frames=(source(),), budget=MotifBudget(0)))
        with self.assertRaises(BilqisError):
            replace(legitimate, optimizer=changed)
        forged = replace(legitimate.allocations, observed_uses=(
            (legitimate.allocations.observed_uses[0][0], 999),))
        with self.assertRaises(BilqisError):
            replace(legitimate, allocations=forged)
        self.assertEqual(resolve_candidate(legitimate, accepted=True).optimizer_step, 12)
