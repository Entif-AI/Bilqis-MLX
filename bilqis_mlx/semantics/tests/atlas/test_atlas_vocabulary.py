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


def _allocation_fixture(*, highest=16384):
    """Large *synthetic* ABI boundary fixture, not a source-admission witness."""
    names = {0: "urn:concept:prior", 8191: "urn:concept:8191",
             8192: "urn:concept:8192", 16384: "urn:concept:16384"}
    if highest >= 65536:
        names[65536] = "urn:concept:65536"
    entries = tuple(AbiEntry(
        index, index // BANK_SIZE, index % BANK_SIZE,
        names.get(index, f"urn:reserved:{index}"), None,
        "PRIOR_ACCEPTED_NATIVE_REGISTRY" if index == 0
        else "CANONICAL_SKOS" if index in names else "FORMAL_DOMAIN",
        index == 0, index == 0,
        "PRIOR_ACCEPTED_ABI" if index == 0 else "IMPLEMENTATION_UNCOVERED",
    ) for index in range(highest + 1))
    seed = _snapshot((("urn:concept:prior", ("urn:type:Entity",)),))
    original = seed.concepts[0]
    concepts = tuple(replace(
        original,
        concept=replace(original.concept, semantic_id=name),
        abi_index=index, abi_bank=index // BANK_SIZE,
        abi_row=index % BANK_SIZE,
        active=index == 0,
        implementation_status="ADMITTED" if index == 0 else "IMPLEMENTATION_UNCOVERED",
        teaching_candidate=index == 0,
        teaching_reason="SOURCE_ADMITTED" if index == 0 else "IMPLEMENTATION_UNCOVERED",
    ) for index, name in names.items())
    snapshot = replace(
        seed,
        abi_entries=entries, concepts=concepts,
        counts=AtlasCounts(
            highest + 1, highest + 1, len(names), highest + 1,
            highest // BANK_SIZE + 1, 1, 0, 0, 0, len(names) - 1),
        semantic_lookup=tuple(sorted(
            (item.semantic_id, item.index) for item in entries)),
        concept_lookup=tuple(sorted(
            (item.concept.semantic_id, position)
            for position, item in enumerate(concepts))),
        shape_policy_sha256=_atlas_sha256(_atlas_bytes(SHAPE_POLICY)),
        active_set_sha256=_atlas_sha256(_atlas_bytes([0])),
    )
    feature_schema = FeatureSchema((), ())
    features = build_feature_manifest(snapshot, feature_schema)
    extents = GenerationExtents(
        1, 1, _atlas_sha256(_atlas_bytes([0])), "b" * 64, features.digest)
    prior = VocabularyPrior(
        AtlasArtifactSelection(
            "synthetic-not-a-real-pin", snapshot.bundle_id,
            snapshot.release_sha256, snapshot.source_bundle_id),
        extents, features, feature_schema, ("urn:concept:prior",), "e" * 64,
    )
    return snapshot, prior


class AtlasVocabularyTests(unittest.TestCase):
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
            from bilqis_mlx.semantics.atlas_snapshot import load_pinned_atlas_snapshot
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
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
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
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            plan = plan_vocabulary_extension(
                prior, ("urn:concept:65536",), ModelTopologySpecV2())
        self.assertEqual(plan.allocations[0].abi_index, 65536)
        self.assertEqual((plan.allocations[0].bank, plan.allocations[0].row), (8, 0))
        self.assertEqual(plan.bank_count, 9)
        self.assertEqual(plan.active_indices, (0, 65536))



if __name__ == "__main__":
    unittest.main()
