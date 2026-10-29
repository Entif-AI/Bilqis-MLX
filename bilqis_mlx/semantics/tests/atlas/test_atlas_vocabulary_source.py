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

class AtlasVocabularySourceTests(unittest.TestCase):
    def test_a02_planner_rejects_unpinned_and_duplicate_admissions(self):
        snapshot, prior = _allocation_fixture()
        with self.assertRaises(BilqisError):
            plan_vocabulary_extension(
                prior, ("urn:concept:8191",), ModelTopologySpecV2())
        with patch(
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            for admissions in (
                ("urn:concept:8191", "urn:concept:8191"),
                ("urn:concept:prior",),
                ("urn:missing",),
            ):
                with self.subTest(admissions=admissions), self.assertRaises(BilqisError):
                    plan_vocabulary_extension(
                        prior, admissions, ModelTopologySpecV2())

    def test_a02_replays_source_features_not_caller_claimed_factor_map(self):
        snapshot, prior = _allocation_fixture()
        forged_features = replace(
            prior.features,
            held_reasons=(("urn:invented", "IMPLEMENTATION_UNCOVERED"),))
        forged_prior = replace(
            prior,
            features=forged_features,
            extents=replace(
                prior.extents, factor_map_digest=forged_features.digest))
        with patch(
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            with self.assertRaises(BilqisError) as caught:
                plan_vocabulary_extension(
                    forged_prior, ("urn:concept:8191",),
                    ModelTopologySpecV2())
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_VOCABULARY_FEATURE_SOURCE_REPLAY_MISMATCH")

    def test_a02_rejects_coherent_caller_minted_feature_predecessor(self):
        snapshot, prior = _allocation_fixture()
        invented_predecessor = replace(
            prior.features, type_map=(
                ("NONE", 1), ("UNKNOWN", 0), ("urn:type:Entity", 77)),
            semantic_release="9" * 64,
            atlas_bundle_id=snapshot.prior_abi_sha256)
        forged_schema = replace(
            prior.feature_schema, predecessor=invented_predecessor)
        forged_features = build_feature_manifest(snapshot, forged_schema)
        self.assertEqual(dict(forged_features.type_map)["urn:type:Entity"], 77)
        forged_prior = replace(
            prior, feature_schema=forged_schema, features=forged_features,
            extents=replace(
                prior.extents, factor_map_digest=forged_features.digest))
        with patch(
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            with self.assertRaises(BilqisError) as caught:
                plan_vocabulary_extension(
                    forged_prior, ("urn:concept:8191",),
                    ModelTopologySpecV2())
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_VOCABULARY_PREDECESSOR_FEATURE_AUTHORITY_REQUIRED")
