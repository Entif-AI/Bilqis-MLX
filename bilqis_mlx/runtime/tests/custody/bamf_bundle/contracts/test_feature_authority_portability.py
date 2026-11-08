"""Portable real-loader witnesses for accepted B13 feature lineage."""
from __future__ import annotations

import os
import shutil
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import read_accepted_generation_feature_lineage
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.test_feature_authority import (
    feature_bound,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state,
    candidate,
    parent_state,
    publish_candidate,
    shape_patch,
)
from bilqis_mlx.semantics.atlas import snapshot as atlas_snapshot
from bilqis_mlx.semantics.atlas.snapshot_materialize import load_atlas_snapshot
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_projection import (
    compile_atlas_release,
    persist_atlas_release,
)
from bilqis_mlx.semantics.tests.atlas.projection.helpers import (
    PRIOR_ABI,
    _bindings,
    _fixture_bundle,
)


class AcceptedFeaturePortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.pointer = self.run / "bamf-state.json"
        self.environment = patch.dict(
            os.environ, {
                "BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3"),
                "BILQIS_ATLAS_ARTIFACT_ROOT": str(self.root / "atlas"),
            })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def _publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_candidate(self.run, source)

    def _two_releases(self):
        source_root = self.root / "source"
        source_root.mkdir()
        bundle, coverage, *_ = _fixture_bundle(source_root)
        artifact_root = self.root / "atlas"

        first_release = compile_atlas_release(
            bundle, coverage, PRIOR_ABI, _bindings())
        first_artifact = persist_atlas_release(first_release, artifact_root)
        first_snapshot = load_atlas_snapshot(
            first_artifact.path,
            expected_bundle_id=first_artifact.bundle_id,
            expected_release_sha256=first_release.digest,
            expected_source_bundle_id=first_release.source_bundle_id,
        )
        first_features = build_feature_manifest(
            first_snapshot, FeatureSchema((), ()))

        second_release = compile_atlas_release(
            bundle, coverage, first_snapshot, _bindings())
        second_artifact = persist_atlas_release(second_release, artifact_root)
        second_snapshot = load_atlas_snapshot(
            second_artifact.path,
            expected_bundle_id=second_artifact.bundle_id,
            expected_release_sha256=second_release.digest,
            expected_source_bundle_id=second_release.source_bundle_id,
        )
        second_features = build_feature_manifest(
            second_snapshot, FeatureSchema((), (), first_features))
        return (
            artifact_root,
            (first_release, first_artifact, first_snapshot, first_features),
            (second_release, second_artifact, second_snapshot, second_features),
        )

    def _publish_lineage(self):
        artifact_root, first, second = self._two_releases()
        first_release, first_artifact, first_snapshot, first_features = first
        second_release, second_artifact, second_snapshot, second_features = second
        first_published = self._publish(feature_bound(
            candidate(parent_state()), first_features,
            release=first_release.digest,
            atlas_bundle=first_artifact.bundle_id,
            source_bundle=first_release.source_bundle_id,
            active_set=first_snapshot.active_set_sha256,
        ))
        successor = feature_bound(
            candidate(
                accepted_state(parent_state()), 1,
                first_published["manifest_sha256"]),
            second_features,
            release=second_release.digest,
            atlas_bundle=second_artifact.bundle_id,
            source_bundle=second_release.source_bundle_id,
            active_set=second_snapshot.active_set_sha256,
        )
        successor = replace(
            successor, transition={
                **successor.transition,
                "kind": "PARAMETER_EXTENSION",
                "invalidate_derived_caches": True,
            })
        self._publish(successor)
        allowed = {
            (first_artifact.bundle_id, first_release.digest, first_release.source_bundle_id),
            (second_artifact.bundle_id, second_release.digest, second_release.source_bundle_id),
        }
        return artifact_root, first, second, allowed

    def _fixture_pins(self, allowed):
        def require_fixture_pin(selection):
            self.assertIn((
                selection.bundle_id,
                selection.release_sha256,
                selection.source_bundle_id,
            ), allowed)
        return patch.object(
            atlas_snapshot, "_require_registered_source_pin",
            side_effect=require_fixture_pin)

    def test_real_loader_replays_accepted_lineage_across_two_atlas_releases(self):
        _, first, second, allowed = self._publish_lineage()
        first_release, first_artifact, _first_snapshot, first_features = first
        second_release, second_artifact, _second_snapshot, second_features = second
        with shape_patch(), self._fixture_pins(allowed):
            receipt, current, predecessor = read_accepted_generation_feature_lineage(
                self.pointer)

        self.assertEqual(receipt.feature_sha256, second_features.digest)
        self.assertEqual(receipt.predecessor_feature_sha256, first_features.digest)
        self.assertEqual(current, second_features)
        self.assertEqual(predecessor, first_features)

    def test_relocated_artifact_root_reproduces_exact_receipt(self):
        artifact_root, _, _, allowed = self._publish_lineage()
        with shape_patch(), self._fixture_pins(allowed):
            original = read_accepted_generation_feature_lineage(self.pointer)[0]

        replica_root = self.root / "replica" / "atlas"
        shutil.copytree(artifact_root, replica_root)
        with patch.dict(
                os.environ, {"BILQIS_ATLAS_ARTIFACT_ROOT": str(replica_root)}), \
                shape_patch(), self._fixture_pins(allowed):
            relocated = read_accepted_generation_feature_lineage(self.pointer)[0]

        self.assertEqual(relocated, original)
        self.assertEqual(relocated.digest, original.digest)

    def test_missing_historical_artifact_fails_closed(self):
        artifact_root, first, _, allowed = self._publish_lineage()
        missing = artifact_root / first[1].bundle_id
        shutil.rmtree(missing)
        with shape_patch(), self._fixture_pins(allowed), self.assertRaises(BilqisError) as caught:
            read_accepted_generation_feature_lineage(self.pointer)
        self.assertEqual(
            caught.exception.context["reason"], "ATLAS_SNAPSHOT_BUNDLE_PATH_INVALID")

    def test_unregistered_historical_artifact_fails_before_loading_bytes(self):
        self._publish_lineage()
        with shape_patch(), self.assertRaises(BilqisError) as caught:
            read_accepted_generation_feature_lineage(self.pointer)
        self.assertEqual(
            caught.exception.context["reason"], "ATLAS_SOURCE_PIN_NOT_REGISTERED")

    def test_substituted_bundle_bytes_fail_identity_verification(self):
        artifact_root, first, second, allowed = self._publish_lineage()
        first_path = artifact_root / first[1].bundle_id
        shutil.rmtree(first_path)
        shutil.copytree(artifact_root / second[1].bundle_id, first_path)
        with shape_patch(), self._fixture_pins(allowed), self.assertRaises(BilqisError) as caught:
            read_accepted_generation_feature_lineage(self.pointer)
        self.assertEqual(
            caught.exception.context["reason"], "ATLAS_SNAPSHOT_BUNDLE_ID_MISMATCH")


if __name__ == "__main__":
    unittest.main()
