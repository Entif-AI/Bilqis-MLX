"""Successor-lineage adversaries for B13.5 accepted feature authority."""
from dataclasses import replace
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.runtime.bamf_bundle import (
    publish_bamf_generation, read_accepted_generation_feature_lineage,
    verify_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.bamf_bundle import feature_authority
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.feature_authority_lineage_support import (
    FeatureLineageCase, SUCCESSOR_ATLAS_BUNDLE, SUCCESSOR_RELEASE,
    SUCCESSOR_SOURCE_BUNDLE, frozen_snapshot,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.test_feature_authority import (
    ARBITRARY, feature_bound, source_features,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, next_accepted_step, parent_state,
    retention_decision, shape_patch,
)


class AcceptedFeatureLineageTests(FeatureLineageCase):
    def test_successor_receipt_replays_accepted_predecessor_lineage(self):
        root = source_features()
        first = self.publish(feature_bound(candidate(parent_state()), root))
        successor = replace(
            root, semantic_release=SUCCESSOR_RELEASE,
            atlas_bundle_id=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle_id=SUCCESSOR_SOURCE_BUNDLE,
            predecessor_digest=root.digest)
        proposed = feature_bound(
            candidate(accepted_state(parent_state()), 1, first["manifest_sha256"]),
            successor, release=SUCCESSOR_RELEASE,
            atlas_bundle=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle=SUCCESSOR_SOURCE_BUNDLE)
        proposed = replace(proposed, transition={
            **proposed.transition, "kind": "PARAMETER_EXTENSION",
            "invalidate_derived_caches": True})
        self.publish(proposed)

        def replay(snapshot, schema):
            return successor if schema.predecessor is not None else root

        with shape_patch(), patch.object(
                feature_authority, "load_pinned_atlas_snapshot",
                side_effect=frozen_snapshot), patch.object(
                feature_authority, "build_feature_manifest", side_effect=replay):
            receipt, current, predecessor = read_accepted_generation_feature_lineage(
                self.pointer)
            self.assertEqual(
                verify_accepted_generation_feature_receipt(
                    self.pointer, receipt), receipt)
        self.assertEqual(receipt.generation, 1)
        self.assertEqual(receipt.feature_sha256, successor.digest)
        self.assertEqual(receipt.predecessor_feature_sha256, root.digest)
        self.assertEqual((current, predecessor), (successor, root))

        with shape_patch(), patch.object(
                feature_authority, "load_pinned_atlas_snapshot",
                side_effect=frozen_snapshot), patch.object(
                feature_authority, "build_feature_manifest", side_effect=replay):
            for forged in (
                    replace(receipt, generation=0),
                    replace(receipt, generation_manifest_sha256=ARBITRARY),
                    replace(receipt, predecessor_feature_sha256=ARBITRARY)):
                with self.subTest(forged=forged), self.assertRaises(BilqisError):
                    verify_accepted_generation_feature_receipt(
                        self.pointer, forged)

    def test_retained_successor_binds_the_feature_map_its_parent_consumed(self):
        root = source_features()
        first = self.publish(feature_bound(candidate(parent_state()), root))
        retained = feature_bound(
            candidate(accepted_state(parent_state()), 1, first["manifest_sha256"]),
            root)
        self.publish(retained)

        with shape_patch(), self.source_replay(root):
            receipt, current, predecessor = read_accepted_generation_feature_lineage(
                self.pointer)

        self.assertEqual(receipt.generation, 1)
        self.assertEqual(receipt.feature_sha256, root.digest)
        self.assertEqual(receipt.predecessor_feature_sha256, root.digest)
        self.assertEqual((current, predecessor), (root, root))

    def test_retained_successor_allows_independent_correction_epoch_advance(self):
        root = source_features()
        first = self.publish(feature_bound(candidate(parent_state()), root))
        retained = feature_bound(
            candidate(accepted_state(parent_state()), 1, first["manifest_sha256"]),
            root)
        retained = replace(
            retained,
            compiler_features={
                **retained.compiler_features,
                "correction_generation": retained.compiler_features["correction_generation"] + 1,
            },
            correction_frontier={
                **retained.correction_frontier,
                "correction_generation": retained.correction_frontier["correction_generation"] + 1,
            },
        )
        self.publish(retained)

        with shape_patch(), self.source_replay(root):
            receipt, current, predecessor = read_accepted_generation_feature_lineage(
                self.pointer)

        self.assertEqual(receipt.generation, 1)
        self.assertEqual(receipt.feature_sha256, root.digest)
        self.assertEqual(receipt.predecessor_feature_sha256, root.digest)
        self.assertEqual((current, predecessor), (root, root))

    def test_retained_descendant_preserves_changed_map_construction_lineage(self):
        root = source_features()
        first = self.publish(feature_bound(candidate(parent_state()), root))
        changed = replace(
            root, semantic_release=SUCCESSOR_RELEASE,
            atlas_bundle_id=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle_id=SUCCESSOR_SOURCE_BUNDLE,
            predecessor_digest=root.digest)
        changed_candidate = feature_bound(
            candidate(accepted_state(parent_state()), 1, first["manifest_sha256"]),
            changed, release=SUCCESSOR_RELEASE,
            atlas_bundle=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle=SUCCESSOR_SOURCE_BUNDLE)
        changed_candidate = replace(changed_candidate, transition={
            **changed_candidate.transition, "kind": "PARAMETER_EXTENSION",
            "invalidate_derived_caches": True})
        second = self.publish(changed_candidate)
        retained = feature_bound(
            candidate(
                next_accepted_step(accepted_state(parent_state())), 2,
                second["manifest_sha256"]),
            changed, release=SUCCESSOR_RELEASE,
            atlas_bundle=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle=SUCCESSOR_SOURCE_BUNDLE)
        binding = mint_acceptance_binding(
            retention_decision(
                parent=changed_candidate.retained_state,
                retained=retained.retained_state),
            retained.retained_state, run_id=retained.run_id,
            generation=retained.generation,
            feature_sha256=retained.extents.factor_map_digest)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            publish_bamf_generation(self.run, retained, acceptance=binding)

        def replay(snapshot, schema):
            return changed if schema.predecessor is not None else root

        with shape_patch(), patch.object(
                feature_authority, "load_pinned_atlas_snapshot",
                side_effect=frozen_snapshot), patch.object(
                feature_authority, "build_feature_manifest", side_effect=replay):
            receipt, current, predecessor = read_accepted_generation_feature_lineage(
                self.pointer)
            self.assertEqual(
                verify_accepted_generation_feature_receipt(
                    self.pointer, receipt), receipt)

        self.assertEqual(receipt.generation, 2)
        self.assertEqual(receipt.feature_sha256, changed.digest)
        self.assertEqual(receipt.predecessor_feature_sha256, changed.digest)
        self.assertEqual((current, predecessor), (changed, changed))
