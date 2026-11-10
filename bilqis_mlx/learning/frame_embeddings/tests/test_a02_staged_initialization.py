"""B02.2 qualification against A02's final typed staging candidate."""
from dataclasses import replace
import hashlib
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np
from lib.ithkuil.src.skos.publication import json_bytes

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import qualify_staged_identity_initialization
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.vocabulary import (
    VocabularyBankParent, apply_vocabulary_extension, plan_vocabulary_extension,
)
from bilqis_mlx.semantics.tests.atlas.vocabulary_fixtures import _allocation_fixture


class A02StagedInitializationTests(unittest.TestCase):
    def _stage(self):
        snapshot, prior = _allocation_fixture(highest=8192)
        feature_parameters = {
            "features.type": mx.zeros((512, 128), dtype=mx.float32).at[2, 0].add(.5),
            "features.project_type": mx.zeros((768, 128), dtype=mx.float32).at[0, 0].add(2),
            "features.project_graph": mx.zeros((768, 64), dtype=mx.float32).at[3, 4].add(5),
            "features.gates": mx.full((4,), -2, dtype=mx.float32),
        }
        original = mx.zeros((8192, 768), dtype=mx.float32).at[0, 7].add(9)
        moment = mx.zeros((8192, 768), dtype=mx.float32)
        parent = VocabularyBankParent(
            prior, (original,), (moment,), (moment,), ((0, 4),),
            feature_parameters, 17, 100_000_000,
        )
        with patch(
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            plan = plan_vocabulary_extension(
                prior, ("urn:concept:8192",), ModelTopologySpecV2())
            candidate = apply_vocabulary_extension(parent, plan)
        return snapshot, parent, plan, candidate

    def test_final_a02_candidate_matches_b02_deterministic_new_row_contract(self):
        snapshot, parent, plan, candidate = self._stage()
        before = np.asarray(parent.weights[0]).copy()

        proposals = qualify_staged_identity_initialization(
            parent, candidate, plan, snapshot)

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].semantic_id, "urn:concept:8192")
        self.assertEqual(proposals[0].abi_index, 8192)
        np.testing.assert_array_equal(
            proposals[0].weights, np.asarray(candidate.weights[1][0]))
        np.testing.assert_array_equal(np.asarray(candidate.weights[0]), before)
        self.assertEqual(candidate.row_counts, ((0, 4), (8192, 0)))

    def test_a02_candidate_with_wrong_initialized_row_fails_closed(self):
        snapshot, parent, plan, candidate = self._stage()
        tampered = candidate.weights[1].at[0, 0].add(1)
        forged = replace(candidate, weights=(candidate.weights[0], tampered))

        with self.assertRaises(BilqisError):
            qualify_staged_identity_initialization(parent, forged, plan, snapshot)

    def test_self_consistent_wrong_abi_allocation_cannot_self_ratify(self):
        snapshot, parent, plan, candidate = self._stage()
        allocation = replace(plan.allocations[0], abi_index=8193, row=1)
        active = (0, 8193)
        active_digest = hashlib.sha256(json_bytes(list(active))).hexdigest()
        forged_plan = replace(
            plan, allocations=(allocation,), active_indices=active,
            active_semantic_digest=active_digest)
        bank1 = candidate.weights[1].at[1].add(candidate.weights[1][0])
        forged_candidate = replace(
            candidate,
            extents=replace(candidate.extents, active_semantic_digest=active_digest),
            weights=(candidate.weights[0], bank1),
            active_indices=active,
            output_domain=(candidate.output_domain[0], (8193, "urn:concept:8192")),
            registry_mirror_delta=(allocation,),
        )

        with self.assertRaises(BilqisError):
            qualify_staged_identity_initialization(
                parent, forged_candidate, forged_plan, snapshot)


if __name__ == "__main__":
    unittest.main()
