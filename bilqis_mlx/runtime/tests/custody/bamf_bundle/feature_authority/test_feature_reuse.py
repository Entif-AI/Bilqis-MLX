"""Accepted parameter extensions may reuse an unchanged feature authority."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.bamf_bundle import (
    publish_bamf_generation, read_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.bamf_bundle import feature_authority
from bilqis_mlx.runtime.bamf_bundle._vocabulary_admission_records import (
    A02VocabularyStagingReceipt, STAGED_EVENT,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.feature_authority_test_support import (
    ATLAS_BUNDLE, RELEASE, SOURCE_BUNDLE, SUCCESSOR_ATLAS_BUNDLE,
    SUCCESSOR_RELEASE, SUCCESSOR_SOURCE_BUNDLE, feature_bound,
    source_features, source_snapshot,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, next_accepted_step, parent_state,
    publish_candidate, retention_decision, shape_patch,
)


class FeatureReuseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.pointer = self.run / "bamf-state.json"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_candidate(self.run, source)

    def test_generic_retention_cannot_activate_semantic_rows(self):
        root_features = source_features()
        first = self.publish(feature_bound(candidate(parent_state()), root_features))
        state = accepted_state(parent_state())
        successor_features = replace(
            root_features, semantic_release=SUCCESSOR_RELEASE,
            atlas_bundle_id=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle_id=SUCCESSOR_SOURCE_BUNDLE,
            predecessor_digest=root_features.digest)
        second_candidate = feature_bound(
            candidate(state, 1, first["manifest_sha256"]), successor_features,
            release=SUCCESSOR_RELEASE, atlas_bundle=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle=SUCCESSOR_SOURCE_BUNDLE)
        second_candidate = replace(second_candidate, transition={
            **second_candidate.transition, "kind": "PARAMETER_EXTENSION",
            "invalidate_derived_caches": True})
        second = self.publish(second_candidate)
        next_state = next_accepted_step(state)
        third_candidate = feature_bound(
            candidate(next_state, 2, second["manifest_sha256"]), successor_features,
            release=SUCCESSOR_RELEASE, atlas_bundle=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle=SUCCESSOR_SOURCE_BUNDLE)
        third_candidate = replace(
            third_candidate,
            extents=replace(third_candidate.extents, active_semantic_digest="8" * 64),
            semantic_abi={**third_candidate.semantic_abi,
                          "active_set_sha256": "8" * 64},
            transition={**third_candidate.transition, "kind": "PARAMETER_EXTENSION",
                        "invalidate_derived_caches": True})
        decision = retention_decision(parent=state, retained=next_state)
        binding = mint_acceptance_binding(
            decision, next_state, run_id=third_candidate.run_id, generation=2,
            feature_sha256=successor_features.digest)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            from bilqis_mlx.errors import BilqisError
            with self.assertRaises(BilqisError):
                publish_bamf_generation(self.run, third_candidate, acceptance=binding)
        def replay_features(student, *args, **kwargs):
            if student.generation == 0:
                return root_features
            self.assertEqual(student.generation, 1)
            self.assertEqual(kwargs.get("predecessor"), root_features)
            self.assertEqual(successor_features.predecessor_digest, root_features.digest)
            return successor_features
        with shape_patch(), patch.object(
                feature_authority, "_authenticate_features",
                side_effect=replay_features):
            receipt = read_accepted_generation_feature_receipt(self.pointer)
        self.assertEqual(receipt.generation, 1)
        self.assertEqual(receipt.feature_sha256, successor_features.digest)
        self.assertEqual(receipt.predecessor_feature_sha256, root_features.digest)

    def test_c07_accepted_a02_active_set_growth_replays_unchanged_features(self):
        root_features = source_features()
        parent = feature_bound(candidate(parent_state()), root_features)
        parent = replace(parent, generation=0, parent_manifest_sha256=None)
        child_state = accepted_state(parent_state())
        child = feature_bound(candidate(child_state, 1, "a" * 64), root_features)
        active = "8" * 64
        child = replace(
            child,
            extents=replace(child.extents, active_semantic_digest=active),
            semantic_abi={**child.semantic_abi, "active_set_sha256": active},
            transition={**child.transition, "kind": "PARAMETER_EXTENSION",
                        "invalidate_derived_caches": True},
        )
        staging = A02VocabularyStagingReceipt(
            run_id=child.run_id,
            generation=child.generation,
            parent_manifest_sha256=child.parent_manifest_sha256,
            parent_feature_receipt_sha256="1" * 64,
            candidate_identity_sha256=candidate_identity_digest(child.retained_state),
            source_allocation_sha256="2" * 64,
            plan_sha256="3" * 64,
            prepared_extents_sha256=child.extents.digest,
            active_mask_sha256="4" * 64,
            registry_mirror_sha256="5" * 64,
            resource_estimate_sha256="6" * 64,
            active_set_sha256=active,
            feature_sha256=root_features.digest,
            semantic_bank_count=child.extents.semantic_bank_count,
        )
        child = replace(child, outbox=({
            "event": STAGED_EVENT,
            "staging_receipt": staging.to_record(),
        },))
        child_binding = SimpleNamespace(
            digest="7" * 64,
            staging_receipt_sha256=staging.digest,
        )
        parent_binding = SimpleNamespace(digest="9" * 64)

        def binding_for(_run_dir, manifest_sha256, *_args, **_kwargs):
            return child_binding if manifest_sha256 == "b" * 64 else parent_binding

        with patch.object(
                feature_authority, "accepted_binding_for_manifest",
                side_effect=binding_for), patch.object(
                feature_authority, "parent_acceptance_anchor_from_manifest",
                return_value="9" * 64), patch.object(
                feature_authority, "load_bamf_bundle", return_value=parent), patch.object(
                feature_authority, "_authenticate_features", return_value=root_features):
            features, binding, predecessor, construction = (
                feature_authority._accepted_feature_context(
                    self.run, "b" * 64, child,
                    expected_acceptance_sha256=child_binding.digest))
        self.assertEqual(features, root_features)
        self.assertIs(binding, child_binding)
        self.assertEqual(predecessor, root_features)
        self.assertIsNone(construction)

        forged_binding = SimpleNamespace(
            digest="7" * 64,
            staging_receipt_sha256="0" * 64,
        )

        def forged_binding_for(_run_dir, manifest_sha256, *_args, **_kwargs):
            return forged_binding if manifest_sha256 == "b" * 64 else parent_binding

        with patch.object(
                feature_authority, "accepted_binding_for_manifest",
                side_effect=forged_binding_for), patch.object(
                feature_authority, "parent_acceptance_anchor_from_manifest",
                return_value="9" * 64), patch.object(
                feature_authority, "load_bamf_bundle", return_value=parent), patch.object(
                feature_authority, "_authenticate_features", return_value=root_features):
            from bilqis_mlx.errors import BilqisError
            with self.assertRaises(BilqisError):
                feature_authority._accepted_feature_context(
                    self.run, "b" * 64, child,
                    expected_acceptance_sha256=forged_binding.digest)


if __name__ == "__main__":
    unittest.main()
