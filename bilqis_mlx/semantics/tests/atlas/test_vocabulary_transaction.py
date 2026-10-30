"""A02.2 complete B01 tensor-tree staging without checkpoint publication."""
from __future__ import annotations

from dataclasses import replace
import os
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import (
    ModelTopologySpecV2, create_unbound_bamf_state,
)
from bilqis_mlx.semantics.atlas.vocabulary import (
    VocabularyBankParent, plan_vocabulary_extension,
)
from bilqis_mlx.semantics.atlas.vocabulary_transaction import (
    FullVocabularyParent, stage_full_vocabulary_extension,
)
from bilqis_mlx.semantics.tests.atlas.vocabulary_fixtures import _allocation_fixture


class AtlasVocabularyTransactionTests(unittest.TestCase):
    def test_rejects_incomplete_b01_tensor_tree_before_staging(self):
        snapshot, prior = _allocation_fixture()
        bank = mx.zeros((8192, 768), dtype=mx.float32)
        banks = VocabularyBankParent(
            prior, (bank,), (bank,), (bank,), ((0, 0),),
            {}, 0, 100_000_000)
        full = FullVocabularyParent(
            banks, ModelTopologySpecV2(), {"identity.bank.0": bank},
            {"step": mx.array(0, dtype=mx.uint64)},
            observed_available_bytes=200 * 1024 ** 3)
        with patch(
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            plan = plan_vocabulary_extension(
                prior, ("urn:concept:8192",), ModelTopologySpecV2())
            with self.assertRaises(BilqisError):
                stage_full_vocabulary_extension(full, plan)

    @unittest.skipUnless(
        os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
        "full 80M-parameter disposable B01 state requires explicit witness",
    )
    def test_complete_b01_tensor_tree_preserves_old_state_and_new_zero_moments(self):
        snapshot, prior = _allocation_fixture()
        topology = ModelTopologySpecV2()
        parameters, optimizer_state, _ = create_unbound_bamf_state(
            topology, prior.extents, run_seed=0)
        bank = "identity.bank.0"
        feature_names = (
            "features.type", "features.project_type",
            "features.project_graph", "features.gates",
        )
        banks = VocabularyBankParent(
            prior, (parameters[bank],),
            (optimizer_state[bank]["m"],),
            (optimizer_state[bank]["v"],),
            ((0, 0),),
            {name: parameters[name] for name in feature_names},
            0, 100_000_000,
        )
        parent = FullVocabularyParent(
            banks, topology, parameters, optimizer_state,
            observed_available_bytes=200 * 1024 ** 3)
        with patch(
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            plan = plan_vocabulary_extension(
                prior, ("urn:concept:8192",), topology)
            injected = dict(banks.feature_parameters)
            injected["features.project_type"] = mx.full(
                (768, 128), 50, dtype=mx.float32)
            with self.assertRaises(BilqisError) as injected_error:
                stage_full_vocabulary_extension(
                    replace(parent, bank_parent=replace(
                        banks, feature_parameters=injected)), plan)
            self.assertEqual(
                injected_error.exception.context["reason"],
                "BAMF_VOCABULARY_FEATURE_PARAMETER_SLICE_DRIFT")
            with self.assertRaises(BilqisError) as budget:
                stage_full_vocabulary_extension(
                    replace(parent, observed_available_bytes=0), plan)
            self.assertEqual(
                budget.exception.context["reason"],
                "BAMF_VOCABULARY_DISK_STAGING_BUDGET_EXCEEDED")
            prepared = stage_full_vocabulary_extension(parent, plan)
        self.assertEqual(prepared.status, "STAGED_NOT_ADMITTED")
        self.assertTrue(prepared.resource_estimate.fits)
        self.assertEqual(prepared.bank_candidate.extents.semantic_bank_count, 2)
        self.assertEqual(len(prepared.parameters), len(parameters) + 1)
        self.assertEqual(len(prepared.optimizer_state), len(optimizer_state) + 1)
        self.assertIs(prepared.parameters["blocks.0.query"], parameters["blocks.0.query"])
        self.assertIs(prepared.optimizer_state["step"], optimizer_state["step"])
        self.assertEqual(prepared.bank_candidate.active_indices, (0, 8192))
        np.testing.assert_array_equal(
            np.asarray(prepared.parameters[bank]), np.asarray(parameters[bank]))
        np.testing.assert_array_equal(
            np.asarray(prepared.optimizer_state[bank]["m"]),
            np.asarray(optimizer_state[bank]["m"]))
        np.testing.assert_array_equal(
            np.asarray(prepared.optimizer_state["identity.bank.1"]["m"][0]),
            np.zeros((768,), dtype=np.float32))
        np.testing.assert_array_equal(
            np.asarray(prepared.optimizer_state["identity.bank.1"]["v"][0]),
            np.zeros((768,), dtype=np.float32))
        self.assertEqual(int(optimizer_state["step"].item()), 0)


if __name__ == "__main__":
    unittest.main()
