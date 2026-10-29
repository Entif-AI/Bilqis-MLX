"""A02 stable source-replayed vocabulary planning witnesses."""
from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.semantics.atlas_projection import (
    compile_atlas_release, persist_atlas_release,
    _canonical_bytes as _atlas_bytes, _digest as _atlas_sha256,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas.vocabulary import VocabularyPrior, plan_vocabulary_extension
from bilqis_mlx.semantics.atlas.vocabulary_resources import build_registry_mirror_delta
from bilqis_mlx.semantics.tests.test_atlas_projection import PRIOR_ABI, _bindings
from bilqis_mlx.semantics.tests.atlas.vocabulary_fixtures import _allocation_fixture


class AtlasVocabularyPlanningTests(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("BILQIS_ATLAS_REAL_CORPUS"),
        "real A01 source bundle is an optional integration witness",
    )
    def test_a02_real_pinned_source_allocation_plan(self):
        bundle = Path(os.environ["BILQIS_ATLAS_REAL_CORPUS"])
        release = compile_atlas_release(
            bundle, json.loads((bundle / "coverage.json").read_text()),
            PRIOR_ABI, _bindings())
        with TemporaryDirectory() as directory:
            receipt = persist_atlas_release(release, Path(directory))
            selection = AtlasArtifactSelection(
                receipt.path, receipt.bundle_id, release.digest,
                release.source_bundle_id)
            from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
            snapshot = load_pinned_atlas_snapshot(selection)
            feature_schema = FeatureSchema((), ())
            features = build_feature_manifest(snapshot, feature_schema)
            active = tuple(
                entry.semantic_id for entry in snapshot.abi_entries
                if entry.active)
            prior = VocabularyPrior(
                selection,
                GenerationExtents(
                    1, 1, snapshot.active_set_sha256, "b" * 64,
                    features.digest),
                features, feature_schema, active, "e" * 64)
            next_source = next(
                entry for entry in snapshot.abi_entries
                if entry.source == "CANONICAL_SKOS" and not entry.active
                and any(item.concept.semantic_id == entry.semantic_id
                        for item in snapshot.concepts)
                and not any(
                    row.semantic_id == entry.semantic_id
                    and row.source_disposition != "SOURCE_ELIGIBLE"
                    for row in snapshot.withheld_rows))
            plan = plan_vocabulary_extension(
                prior, (next_source.semantic_id,), ModelTopologySpecV2())
            mirror = build_registry_mirror_delta(
                prior, plan, source_bundle_path=bundle)
            held = next(
                row.semantic_id for row in snapshot.withheld_rows
                if row.semantic_id is not None
                and row.source_disposition == "SOURCE_HELD"
                and row.semantic_id not in active)
            with self.assertRaises(BilqisError):
                plan_vocabulary_extension(
                    prior, (held,), ModelTopologySpecV2())
        self.assertEqual(plan.allocations[0].abi_index, next_source.index)
        self.assertEqual(plan.source_bundle_id, release.source_bundle_id)
        self.assertEqual(plan.status, "STAGED_NOT_ADMITTED")
        self.assertEqual(mirror.active_indices, plan.active_indices)
        self.assertEqual(mirror.rows[0].semantic_id, next_source.semantic_id)
        self.assertTrue(mirror.rows[0].description)
        self.assertEqual(prior.extents.semantic_bank_count, 1)

    def test_a02_planner_stable_boundary_indices_and_bank_extents(self):
        snapshot, prior = _allocation_fixture()
        with patch(
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            first = plan_vocabulary_extension(
                prior, ("urn:concept:8192", "urn:concept:8191"),
                ModelTopologySpecV2())
            reordered = plan_vocabulary_extension(
                prior, ("urn:concept:8191", "urn:concept:8192"),
                ModelTopologySpecV2())
            third = plan_vocabulary_extension(
                prior, ("urn:concept:16384",), ModelTopologySpecV2())
        self.assertEqual(first, reordered)
        self.assertEqual(
            tuple((item.abi_index, item.bank, item.row)
                  for item in first.allocations),
            ((8191, 0, 8191), (8192, 1, 0)))
        self.assertEqual(first.bank_count, 2)
        self.assertEqual(first.active_indices, (0, 8191, 8192))
        self.assertEqual(
            first.active_semantic_digest,
            _atlas_sha256(_atlas_bytes([0, 8191, 8192])))
        self.assertEqual(
            tuple((item.abi_index, item.bank, item.row)
                  for item in third.allocations), ((16384, 2, 0),))
        self.assertEqual(third.bank_count, 3)

    def test_a02_extended_uint32_index_beyond_65535_is_not_aliased(self):
        snapshot, prior = _allocation_fixture(highest=65536)
        with patch(
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            plan = plan_vocabulary_extension(
                prior, ("urn:concept:65536",), ModelTopologySpecV2())
        self.assertEqual(plan.allocations[0].abi_index, 65536)
        self.assertEqual((plan.allocations[0].bank, plan.allocations[0].row), (8, 0))
        self.assertEqual(plan.bank_count, 9)
        self.assertEqual(plan.active_indices, (0, 65536))

    def test_a02_planner_rejects_unpinned_and_duplicate_admissions(self):
        snapshot, prior = _allocation_fixture()
        with self.assertRaises(BilqisError):
            plan_vocabulary_extension(
                prior, ("urn:concept:8191",), ModelTopologySpecV2())
        with patch(
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
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
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
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
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            with self.assertRaises(BilqisError) as caught:
                plan_vocabulary_extension(
                    forged_prior, ("urn:concept:8191",),
                    ModelTopologySpecV2())
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_VOCABULARY_PREDECESSOR_FEATURE_AUTHORITY_REQUIRED")
