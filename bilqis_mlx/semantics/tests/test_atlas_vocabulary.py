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
from bilqis_mlx.semantics.tests.test_atlas_features import (
    BROADER, _features, _snapshot,
)
from bilqis_mlx.semantics.tests.test_atlas_projection import (
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
            mirror = build_registry_mirror_delta(prior, plan)
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


if __name__ == "__main__":
    unittest.main()
