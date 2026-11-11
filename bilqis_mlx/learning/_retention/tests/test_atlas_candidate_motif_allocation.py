"""B07 retained-allocation materialization at the B12 candidate boundary."""
import unittest

import numpy as np

from bilqis_mlx.learning._engram.tests.motif_fixtures import full_first_page, source
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning._atlas_candidate.transaction import _stage_candidate_motif_allocation
from bilqis_mlx.learning.atlas_engram import (
    MOTIF_PAGE_STATE_BYTES, MotifBudget, initialize_planned_motif_slot,
)
from bilqis_mlx.learning.atlas_engram_transaction import (
    MotifAllocationSnapshot, _prepare_candidate_motif_snapshot,
)
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents

from .motif_allocation_support import (
    CandidateMotifAllocationFixture, IDENTITY, MOTIF,
)


class CandidateMotifAllocationTests(
        CandidateMotifAllocationFixture, unittest.TestCase):

    def test_staged_allocation_materializes_b01_row_and_rejection_is_exact_parent(self):
        transaction = self._step()
        proposal = _prepare_candidate_motif_snapshot(
            (source(),), self.parent.allocations, MotifBudget(2))
        successor_extents = GenerationExtents(
            1, 1, "a" * 64, proposal.proposed.manifest.digest, "c" * 64)
        continuation = self._continuation(proposal)

        with self._shape_patches(), self._continuation_patch(continuation):
            staged = _stage_candidate_motif_allocation(
                transaction, continuation, spec=self.spec,
                parent_extents=self.extents, candidate_extents=successor_extents,
                run_seed=17)

        self.assertEqual(staged.allocations, proposal.proposed)
        self.assertEqual(self.parent.allocations, transaction.parent.allocations)
        expected = initialize_planned_motif_slot(
            proposal.view, 0, run_seed=17, topology=self.spec,
            extents=successor_extents)
        np.testing.assert_array_equal(
            np.asarray(staged.optimizer.parameters[MOTIF][0]), expected)
        np.testing.assert_array_equal(
            np.asarray(staged.optimizer.m[MOTIF][0]), np.zeros((128,), np.float32))
        np.testing.assert_array_equal(
            np.asarray(staged.optimizer.v[MOTIF][0]), np.zeros((128,), np.float32))
        self.assertEqual(int(staged.optimizer.update_counts[MOTIF][0]), 0)

        with self._continuation_patch(continuation):
            self.assertIs(resolve_candidate(staged, accepted=False), self.parent)
            retained = resolve_candidate(staged, accepted=True)
        self.assertEqual(retained.allocations, proposal.proposed)
        np.testing.assert_array_equal(
            np.asarray(retained.optimizer.parameters[MOTIF][0]), expected)

    def test_page_growth_adds_exactly_one_b01_page_and_preserves_parent_page(self):
        full = MotifAllocationSnapshot(full_first_page())
        extents = GenerationExtents(
            1, 1, "a" * 64, full.manifest.digest, "c" * 64)
        optimizer = AdamWStateTree(
            self.parent.optimizer.parameters, self.parent.optimizer.m,
            self.parent.optimizer.v, self.parent.optimizer.update_counts)
        parent = self._retained_state(optimizer, full, extents)
        original_parent, original_extents = self.parent, self.extents
        self.parent, self.extents = parent, extents
        try:
            transaction = self._step()
            proposal = _prepare_candidate_motif_snapshot(
                (source(),), parent.allocations,
                MotifBudget(2, page_growth_bytes=MOTIF_PAGE_STATE_BYTES))
            continuation = self._continuation(proposal)
            successor_extents = GenerationExtents(
                1, 2, "a" * 64, proposal.proposed.manifest.digest, "c" * 64)
            self.assertEqual(proposal.view.page_growth.added_pages, 1)
            self.assertEqual(proposal.proposed.manifest.capacity, 32768)
            before_page = np.asarray(transaction.optimizer.parameters[MOTIF]).copy()
            before_m = np.asarray(transaction.optimizer.m[MOTIF]).copy()
            before_v = np.asarray(transaction.optimizer.v[MOTIF]).copy()
            before_counts = np.asarray(transaction.optimizer.update_counts[MOTIF]).copy()

            with (self._shape_patches(growth=True),
                  self._continuation_patch(continuation)):
                staged = _stage_candidate_motif_allocation(
                    transaction, continuation, spec=self.spec,
                    parent_extents=extents, candidate_extents=successor_extents,
                    run_seed=17)

            transition = staged.motif_transition
            self.assertIsNotNone(transition)
            self.assertEqual(transition.added_pages, 1)
            self.assertEqual(transition.candidate_extents.motif_page_count, 2)
            self.assertEqual(set(staged.optimizer.parameters),
                             {IDENTITY, MOTIF, "motif.page.1"})
            np.testing.assert_array_equal(
                np.asarray(staged.optimizer.parameters[MOTIF]), before_page)
            np.testing.assert_array_equal(np.asarray(staged.optimizer.m[MOTIF]), before_m)
            np.testing.assert_array_equal(np.asarray(staged.optimizer.v[MOTIF]), before_v)
            np.testing.assert_array_equal(
                np.asarray(staged.optimizer.update_counts[MOTIF]), before_counts)
            np.testing.assert_array_equal(
                np.asarray(staged.optimizer.m["motif.page.1"]),
                np.zeros((16384, 128), dtype=np.float32))
            np.testing.assert_array_equal(
                np.asarray(staged.optimizer.v["motif.page.1"]),
                np.zeros((16384, 128), dtype=np.float32))
            np.testing.assert_array_equal(
                np.asarray(staged.optimizer.update_counts["motif.page.1"]),
                np.zeros((16384,), dtype=np.uint64))
            for slot in proposal.view.plan.allocated:
                row = slot.slot_id % 16384
                expected = initialize_planned_motif_slot(
                    proposal.view, slot.slot_id, run_seed=17,
                    topology=self.spec, extents=transition.candidate_extents)
                np.testing.assert_array_equal(
                    np.asarray(staged.optimizer.parameters["motif.page.1"][row]),
                    expected)
            with self._continuation_patch(continuation):
                self.assertIs(resolve_candidate(staged, accepted=False), parent)
        finally:
            self.parent, self.extents = original_parent, original_extents


if __name__ == "__main__":
    unittest.main()
