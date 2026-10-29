"""A02 prospective identity-factor staging without B02 authority."""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes, initialize_bamf_row,
)
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, AtlasCounts, CorpusCoverageRow, BANK_SIZE, SHAPE_POLICY,
    compile_atlas_release, persist_atlas_release,
    _canonical_bytes as _atlas_bytes, _digest as _atlas_sha256,
)
from bilqis_mlx.semantics.atlas_features import (
    FeatureSchema, build_feature_manifest,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_vocabulary import (
    VocabularyPrior, VocabularyBankParent,
    apply_vocabulary_extension, plan_vocabulary_extension,
    prepare_identity_factors, staged_tied_logits,
)
from bilqis_mlx.semantics.atlas_vocabulary_resources import (
    build_registry_mirror_delta,
)
from bilqis_mlx.semantics.tests.atlas.test_atlas_features import (
    BROADER, _features, _snapshot,
)
from bilqis_mlx.semantics.tests.atlas.test_atlas_projection import (
    PRIOR_ABI, _bindings,
)
from bilqis_mlx.vocabulary_growth import digest
from bilqis_mlx.semantics.tests.atlas.test_atlas_vocabulary import _allocation_fixture

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
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
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
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
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

    def test_a02_stages_inactive_row_factor_without_b02_dependency(self):
        snapshot = _snapshot(
            definitions=(("urn:concept:A", ("urn:type:Entity",)),
                         ("urn:concept:B", ("urn:type:Future",))),
            relations=(("urn:concept:B", BROADER, "urn:concept:A"),))
        snapshot = replace(
            snapshot,
            abi_entries=tuple(
                replace(entry, source="CANONICAL_SKOS", active=False,
                        teaching_candidate=False, reason="IMPLEMENTATION_UNCOVERED")
                if entry.semantic_id == "urn:concept:B" else entry
                for entry in snapshot.abi_entries),
            concepts=tuple(
                replace(item, active=False,
                        implementation_status="IMPLEMENTATION_UNCOVERED",
                        teaching_candidate=False,
                        teaching_reason="IMPLEMENTATION_UNCOVERED")
                if item.concept.semantic_id == "urn:concept:B" else item
                for item in snapshot.concepts),
            withheld_rows=(
                CorpusCoverageRow(
                    "fixture", "source", "candidate", "urn:concept:B",
                    "SOURCE_ELIGIBLE", "IMPLEMENTATION_UNCOVERED",
                    False, "IMPLEMENTATION_UNCOVERED",
                    "IMPLEMENTATION_UNCOVERED", "fixture"),
            ),
        )
        current = _features(snapshot, roles=(), schemas=())
        type_table = mx.zeros((512, 128), dtype=mx.float32)
        type_table = type_table.at[3].add(mx.ones((128,), dtype=mx.float32))
        parameters = {
            "features.type": type_table,
            "features.project_type": mx.ones((768, 128), dtype=mx.float32) / 128.0,
            "features.project_graph": mx.zeros((768, 64), dtype=mx.float32),
            "features.gates": mx.zeros((4,), dtype=mx.float32),
        }

        plan, factors = prepare_identity_factors(
            snapshot, current, ("urn:concept:B",), parameters,
            extents=GenerationExtents(1, 1, "a" * 64, "b" * 64, current.digest))

        self.assertEqual(tuple(name for name, _ in factors), ("urn:concept:B",))
        factor = factors[0][1]
        np.testing.assert_allclose(factor, np.full((768,), 0.5, dtype=np.float32))
        entry = next(item for item in snapshot.abi_entries
                     if item.semantic_id == "urn:concept:B")
        identity_spec = next(
            item for item in expected_bamf_shapes(
                ModelTopologySpecV2(),
                GenerationExtents(
                    1, 1, "a" * 64, "b" * 64, current.digest))
            if item.name == "identity.bank.0")
        row = initialize_bamf_row(
            identity_spec, run_seed=7, row_id=entry.semantic_id, factor=factor)
        self.assertEqual(row.shape, (768,))
        self.assertEqual(row.dtype, np.float32)
        self.assertEqual(plan.identities[0].abi_index, entry.index)
        self.assertFalse(entry.active)
        self.assertEqual(plan.identities[0].graph64[7], 0.0)
        graph_projector = np.zeros((768, 64), dtype=np.float32)
        graph_projector[:, 7] = 1.0
        graph_only = {
            "features.type": mx.zeros((512, 128), dtype=mx.float32),
            "features.project_type": mx.zeros((768, 128), dtype=mx.float32),
            "features.project_graph": mx.array(graph_projector),
            "features.gates": mx.zeros((4,), dtype=mx.float32),
        }
        _, graph_factors = prepare_identity_factors(
            snapshot, current, ("urn:concept:B",), graph_only,
            extents=GenerationExtents(
                1, 1, "a" * 64, "b" * 64, current.digest))
        np.testing.assert_array_equal(
            graph_factors[0][1], np.zeros((768,), dtype=np.float32))
