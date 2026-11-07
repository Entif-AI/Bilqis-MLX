"""B12 package imports reset declared receiver state without becoming training steps."""
from dataclasses import replace
from unittest import TestCase

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_package_import import (
    ImportSlice, PackageImportTransaction, RESET_POLICY_SHA256, prepare_package_import,
)
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree


IDENTITY = "identity.bank.0"
DENSE = "dense.weight"
RELEASE = "b" * 64


def _parent():
    identity = mx.array([[1., 2.], [3., 4.]], dtype=mx.float32)
    dense = mx.array([[5., 6.], [7., 8.]], dtype=mx.float32)
    optimizer = AdamWStateTree(
        {IDENTITY: identity, DENSE: dense},
        {IDENTITY: mx.array([[.1, .2], [.3, .4]], dtype=mx.float32),
         DENSE: mx.array([[.5, .6], [.7, .8]], dtype=mx.float32)},
        {IDENTITY: mx.array([[.01, .02], [.03, .04]], dtype=mx.float32),
         DENSE: mx.array([[.05, .06], [.07, .08]], dtype=mx.float32)},
        {IDENTITY: mx.array([5, 6], dtype=mx.uint64),
         DENSE: mx.array(9, dtype=mx.uint64)})
    policy = PlasticityPolicy(
        "ADAPTIVE", 7, (IdentityRowAge(0, 0, 7), IdentityRowAge(0, 1, 2)))
    return CandidateState(
        optimizer, policy, MotifAllocationSnapshot(MotifManifest(RELEASE)), 11)


def _candidate_parameters(parent):
    identity = np.asarray(parent.optimizer.parameters[IDENTITY]).copy()
    dense = np.asarray(parent.optimizer.parameters[DENSE]).copy()
    identity.reshape(-1)[1] += .5
    dense.reshape(-1)[2] -= 1.
    return {IDENTITY: mx.array(identity), DENSE: mx.array(dense)}


def _snapshot(state):
    return {
        field: {name: np.asarray(value).tobytes()
                for name, value in getattr(state.optimizer, field).items()}
        for field in ("parameters", "m", "v", "update_counts")
    }


class PackageImportTransactionTests(TestCase):
    def test_import_resets_only_declared_receiver_cells_and_preserves_clocks(self):
        parent = _parent()
        before = _snapshot(parent)
        transaction = prepare_package_import(
            parent, _candidate_parameters(parent),
            (ImportSlice(DENSE, 2, 3), ImportSlice(IDENTITY, 1, 2)))
        state = transaction.candidate

        self.assertEqual(transaction.reset_policy_sha256, RESET_POLICY_SHA256)
        self.assertEqual(transaction.changed_identity_rows, ((0, 0),))
        self.assertEqual(state.optimizer_step, 11)
        self.assertIs(state.allocations, parent.allocations)
        self.assertEqual(state.policy.mode, "ADAPTIVE")
        self.assertEqual(state.policy.accepted_fast_since_full, 0)
        self.assertEqual(tuple(row.accepted_age for row in state.policy.row_ages), (0, 2))
        np.testing.assert_array_equal(np.asarray(state.optimizer.update_counts[IDENTITY]), [0, 6])
        self.assertEqual(int(np.asarray(state.optimizer.update_counts[DENSE])), 0)

        first = np.asarray(state.optimizer.m[IDENTITY])
        second = np.asarray(state.optimizer.v[IDENTITY])
        self.assertEqual(first[0, 1], 0.)
        self.assertEqual(second[0, 1], 0.)
        self.assertEqual(first[0, 0], .1)
        self.assertEqual(second[1, 1], .04)
        self.assertEqual(np.asarray(state.optimizer.m[DENSE]).reshape(-1)[2], 0.)
        self.assertEqual(np.asarray(state.optimizer.v[DENSE]).reshape(-1)[2], 0.)
        self.assertEqual(_snapshot(parent), before)

    def test_undeclared_parameter_change_and_untracked_identity_row_fail_closed(self):
        parent = _parent()
        parameters = _candidate_parameters(parent)
        with self.assertRaises(BilqisError):
            prepare_package_import(parent, parameters, (ImportSlice(IDENTITY, 1, 2),))

        no_second_age = replace(
            parent, policy=replace(parent.policy, row_ages=(parent.policy.row_ages[0],)))
        identity = np.asarray(parent.optimizer.parameters[IDENTITY]).copy()
        identity[1, 0] += 1.
        with self.assertRaises(BilqisError):
            prepare_package_import(
                no_second_age,
                {IDENTITY: mx.array(identity), DENSE: parent.optimizer.parameters[DENSE]},
                (ImportSlice(IDENTITY, 2, 3),))

    def test_transaction_cannot_be_caller_minted_or_replaced(self):
        parent = _parent()
        transaction = prepare_package_import(
            parent, _candidate_parameters(parent),
            (ImportSlice(DENSE, 2, 3), ImportSlice(IDENTITY, 1, 2)))
        with self.assertRaises(BilqisError):
            PackageImportTransaction()
        with self.assertRaises(BilqisError):
            replace(transaction, reset_policy_sha256="0" * 64)

    def test_same_weights_different_optimizer_histories_keep_receiver_local_untouched_state(self):
        left = _parent()
        right_optimizer = AdamWStateTree(
            left.optimizer.parameters,
            {IDENTITY: mx.array([[.9, .2], [.3, .4]], dtype=mx.float32),
             DENSE: mx.array([[.5, .6], [.7, .8]], dtype=mx.float32)},
            left.optimizer.v,
            {IDENTITY: mx.array([12, 6], dtype=mx.uint64),
             DENSE: mx.array(99, dtype=mx.uint64)})
        right = replace(left, optimizer=right_optimizer)
        slices = (ImportSlice(IDENTITY, 1, 2),)
        left_parameters = _candidate_parameters(left)
        right_parameters = _candidate_parameters(right)
        left_parameters[DENSE] = left.optimizer.parameters[DENSE]
        right_parameters[DENSE] = right.optimizer.parameters[DENSE]

        left_import = prepare_package_import(left, left_parameters, slices).candidate
        right_import = prepare_package_import(right, right_parameters, slices).candidate

        self.assertEqual(np.asarray(left_import.optimizer.m[IDENTITY])[0, 1], 0.)
        self.assertEqual(np.asarray(right_import.optimizer.m[IDENTITY])[0, 1], 0.)
        self.assertEqual(np.asarray(left_import.optimizer.m[IDENTITY])[0, 0], .1)
        self.assertEqual(np.asarray(right_import.optimizer.m[IDENTITY])[0, 0], .9)
        np.testing.assert_array_equal(np.asarray(left_import.optimizer.update_counts[IDENTITY]), [0, 6])
        np.testing.assert_array_equal(np.asarray(right_import.optimizer.update_counts[IDENTITY]), [0, 6])
        self.assertEqual(int(np.asarray(left_import.optimizer.update_counts[DENSE])), 9)
        self.assertEqual(int(np.asarray(right_import.optimizer.update_counts[DENSE])), 99)

if __name__ == "__main__":
    import unittest
    unittest.main()
