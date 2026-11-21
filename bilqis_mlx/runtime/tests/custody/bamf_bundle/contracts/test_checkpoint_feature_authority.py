"""Checkpoint-backed current feature authentication avoids historical replay."""
from dataclasses import replace
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.bamf_bundle import feature_authority
from bilqis_mlx.runtime.bamf_bundle.feature.receipt import (
    AcceptedFeatureArtifactCommitment,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.feature_authority_lineage_support import (
    FeatureLineageCase, SUCCESSOR_ATLAS_BUNDLE, SUCCESSOR_RELEASE,
    SUCCESSOR_SOURCE_BUNDLE, frozen_snapshot,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.test_feature_authority import (
    ARBITRARY, feature_bound, source_features,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, parent_state, shape_patch,
)
from bilqis_mlx.semantics.atlas.feature_io import persist_feature_manifest


class CheckpointFeatureAuthorityTests(FeatureLineageCase):
    def _accepted_successor(self):
        root = replace(
            source_features(),
            type_map=(("NONE", 1), ("UNKNOWN", 0)),
            role_map=(("NONE", 1), ("UNKNOWN", 0)),
            schema_map=(("NONE", 1), ("UNKNOWN", 0)),
        )
        first = self.publish_feature_genesis(root)
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
        with self.source_replay(successor):
            self.publish(proposed)

        def replay(_snapshot, schema):
            return successor if schema.predecessor is not None else root

        with shape_patch(), patch.object(
                feature_authority, "load_pinned_atlas_snapshot",
                side_effect=frozen_snapshot), patch.object(
                feature_authority, "build_feature_manifest", side_effect=replay):
            receipt = feature_authority.read_accepted_generation_feature_receipt(
                self.pointer)
        artifact = persist_feature_manifest(
            successor, self.root / "features", predecessor=root)
        with shape_patch():
            student = load_bamf_generation(self.pointer)
        commitment = AcceptedFeatureArtifactCommitment(
            receipt, artifact.bundle_id, successor.predecessor_digest)
        return student, successor, artifact, commitment

    def test_current_checkpoint_path_never_replays_feature_or_bundle_history(self):
        student, successor, artifact, commitment = self._accepted_successor()
        with patch.object(
                feature_authority, "_accepted_feature_context",
                side_effect=AssertionError("historical feature replay")), patch.object(
                feature_authority, "load_bamf_bundle",
                side_effect=AssertionError("historical bundle load")), patch.object(
                feature_authority, "build_feature_manifest",
                side_effect=AssertionError("feature rebuild")), patch.object(
                feature_authority, "load_pinned_atlas_snapshot",
                side_effect=frozen_snapshot):
            context = (
                feature_authority.authenticate_checkpointed_bamf_generation_feature_context(
                    student, "/artifact", artifact.path, commitment))
        self.assertEqual(context.features, successor)
        self.assertEqual(context.commitment, commitment)
        self.assertEqual(context.feature_artifact_path, artifact.path)
        self.assertEqual(context.atlas_reload_count, 1)
        self.assertEqual(context.feature_manifest_rebuild_count, 0)

    def test_checkpoint_path_rejects_generation_and_artifact_binding_drift(self):
        student, successor, artifact, commitment = self._accepted_successor()
        self.assertEqual(
            AcceptedFeatureArtifactCommitment.from_record(commitment.to_record()),
            commitment)
        forged_receipt = replace(commitment.receipt, feature_sha256=ARBITRARY)
        forged_commitment = AcceptedFeatureArtifactCommitment(
            forged_receipt, artifact.bundle_id, successor.predecessor_digest)
        with patch.object(
                feature_authority, "load_pinned_atlas_snapshot",
                side_effect=frozen_snapshot), self.assertRaises(BilqisError) as failure:
            feature_authority.authenticate_checkpointed_bamf_generation_feature_context(
                student, "/artifact", artifact.path, forged_commitment)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_CHECKPOINT_FEATURE_BINDING_DRIFT")

        wrong_predecessor = AcceptedFeatureArtifactCommitment(
            commitment.receipt, artifact.bundle_id, ARBITRARY)
        with patch.object(
                feature_authority, "load_pinned_atlas_snapshot",
                side_effect=frozen_snapshot), self.assertRaises(BilqisError) as failure:
            feature_authority.authenticate_checkpointed_bamf_generation_feature_context(
                student, "/artifact", artifact.path, wrong_predecessor)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FEATURE_ARTIFACT_CHECKPOINT_MISMATCH")


if __name__ == "__main__":
    import unittest
    unittest.main()
