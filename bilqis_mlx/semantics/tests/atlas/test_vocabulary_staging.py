"""A02 detached bank staging and active readout witnesses."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas_projection import BANK_SIZE
from bilqis_mlx.semantics.atlas.vocabulary import (
    VocabularyBankParent, apply_vocabulary_extension,
    plan_vocabulary_extension, staged_tied_logits,
)
from bilqis_mlx.semantics.tests.atlas.vocabulary_fixtures import _allocation_fixture


class AtlasVocabularyStagingTests(unittest.TestCase):
    def test_a02_bank_candidate_preserves_prior_and_masks_inactive_logits(self):
        snapshot, prior = _allocation_fixture()
        parameters = {
            "features.type": mx.zeros((512, 128), dtype=mx.float32),
            "features.project_type": mx.ones((768, 128), dtype=mx.float32) / 128,
            "features.project_graph": mx.zeros((768, 64), dtype=mx.float32),
            "features.gates": mx.zeros((4,), dtype=mx.float32),
        }
        original = mx.zeros((BANK_SIZE, 768), dtype=mx.float32)
        original = original.at[0].add(mx.ones((768,), dtype=mx.float32))
        original = original.at[1].add(mx.full((768,), 999, dtype=mx.float32))
        moment = mx.zeros((BANK_SIZE, 768), dtype=mx.float32)
        moment = moment.at[0].add(mx.ones((768,), dtype=mx.float32))
        parent = VocabularyBankParent(
            prior, (original,), (moment,), (moment,),
            ((0, 7),), parameters, 7, BANK_SIZE * 768 * 4 * 3)
        with patch(
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            plan = plan_vocabulary_extension(
                prior, ("urn:concept:8191", "urn:concept:8192"),
                ModelTopologySpecV2())
            candidate = apply_vocabulary_extension(parent, plan)
        self.assertEqual(candidate.extents.semantic_bank_count, 2)
        self.assertEqual(candidate.row_counts, ((0, 7), (8191, 0), (8192, 0)))
        self.assertEqual(candidate.output_domain, (
            (0, "urn:concept:prior"),
            (8191, "urn:concept:8191"),
            (8192, "urn:concept:8192")))
        self.assertEqual(candidate.active_mask[0] & 3, 1)
        self.assertEqual(candidate.active_mask[8191 // 8] & 128, 128)
        self.assertEqual(candidate.active_mask[8192 // 8] & 1, 1)
        np.testing.assert_array_equal(
            np.asarray(candidate.weights[0][0]), np.ones((768,), dtype=np.float32))
        np.testing.assert_array_equal(
            np.asarray(candidate.weights[0][1]), np.full((768,), 999, dtype=np.float32))
        np.testing.assert_array_equal(
            np.asarray(candidate.moments_m[0][0]), np.ones((768,), dtype=np.float32))
        np.testing.assert_array_equal(
            np.asarray(candidate.moments_m[0][8191]), np.zeros((768,), dtype=np.float32))
        np.testing.assert_array_equal(
            np.asarray(candidate.moments_v[1][0]), np.zeros((768,), dtype=np.float32))
        indices, logits = staged_tied_logits(
            candidate, mx.ones((768,), dtype=mx.float32))
        self.assertEqual(indices, (0, 8191, 8192))
        self.assertEqual(tuple(np.asarray(logits).shape), (3,))
        self.assertEqual(float(np.asarray(logits)[0]), 768.0)
        self.assertTrue(np.isfinite(np.asarray(logits)).all())
        self.assertNotIn(1, indices)
        self.assertEqual(float(np.asarray(original[1, 0])), 999.0)

    def test_a02_rejects_forged_plan_and_insufficient_bank_budget(self):
        snapshot, prior = _allocation_fixture()
        parameters = {
            "features.type": mx.zeros((512, 128), dtype=mx.float32),
            "features.project_type": mx.zeros((768, 128), dtype=mx.float32),
            "features.project_graph": mx.zeros((768, 64), dtype=mx.float32),
            "features.gates": mx.zeros((4,), dtype=mx.float32),
        }
        empty = mx.zeros((BANK_SIZE, 768), dtype=mx.float32)
        parent = VocabularyBankParent(
            prior, (empty,), (empty,), (empty,),
            ((0, 3),), parameters, 0, 0)
        with patch(
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            plan = plan_vocabulary_extension(
                prior, ("urn:concept:8192",), ModelTopologySpecV2())
            with self.assertRaises(BilqisError) as budget:
                apply_vocabulary_extension(parent, plan)
            self.assertEqual(
                budget.exception.context["reason"],
                "BAMF_VOCABULARY_BANK_RESOURCE_BUDGET_EXCEEDED")
            with self.assertRaises(BilqisError) as forged:
                apply_vocabulary_extension(
                    replace(parent, resource_budget_bytes=100_000_000),
                    replace(plan, source_allocation_digest="0" * 64))
            self.assertEqual(
                forged.exception.context["reason"],
                "BAMF_VOCABULARY_PLAN_SOURCE_REPLAY_MISMATCH")
        np.testing.assert_array_equal(
            np.asarray(empty[0]), np.zeros((768,), dtype=np.float32))
