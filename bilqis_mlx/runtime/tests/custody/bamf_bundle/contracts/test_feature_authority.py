"""B13.5 accepted-generation feature authority witnesses.

A caller-created candidate must never ratify its own factor-map digest. The
receipt is minted from custody and from the replayed admitted source release.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    authenticate_bamf_candidate_features, publish_bamf_generation,
    read_accepted_generation_feature_lineage, read_accepted_generation_feature_receipt,
    verify_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.bamf_bundle import feature_authority
from bilqis_mlx.semantics.atlas_features import AtlasFeatures
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from bilqis_mlx.semantics.atlas_projection_parts.releases import AtlasCounts

from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, publish_candidate,
    candidate, parent_state, shape_patch,
)

RELEASE = "1" * 64
ATLAS_BUNDLE = "2" * 64
SOURCE_BUNDLE = "3" * 64
SUCCESSOR_RELEASE = "c" * 64
SUCCESSOR_ATLAS_BUNDLE = "d" * 64
SUCCESSOR_SOURCE_BUNDLE = "e" * 64
ARBITRARY = "b" * 64
def feature_schema() -> dict:
    """One recorded feature schema shape with no categorical bindings."""
    return {"role_ids": [], "schema_ids": [], "source_bindings": []}


def source_features() -> AtlasFeatures:
    return AtlasFeatures(
        RELEASE, ATLAS_BUNDLE, SOURCE_BUNDLE, None, (), (), (), (), ())


def feature_bound(source, features: AtlasFeatures, *, digest=None, release=RELEASE,
                  atlas_bundle=ATLAS_BUNDLE, source_bundle=SOURCE_BUNDLE):
    """Bind a candidate to a recorded source release and feature map."""
    factor_map = digest or features.digest
    return replace(
        source,
        extents=replace(source.extents, factor_map_digest=factor_map),
        provenance=replace(source.provenance, release_digest=release),
        compiler_features={
            **source.compiler_features,
            "factor_map_sha256": factor_map,
            "feature_source": {
                "atlas_bundle_id": atlas_bundle,
                "release_sha256": release,
                "source_bundle_id": source_bundle},
            "feature_schema": feature_schema()},
        correction_frontier={
            **source.correction_frontier, "release_digest": release})


def frozen_snapshot(selection):
    return FrozenAtlasSnapshot(
        "bilqis.atlas.snapshot/v1", selection.bundle_id,
        selection.release_sha256, selection.source_bundle_id,
        "4" * 64, "5" * 64, "6" * 64, "7" * 64, "8" * 64, "9" * 64,
        "a" * 64, AtlasCounts(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (), (), (), (), (), (), (),
    )


class AcceptedGenerationFeatureAuthorityTests(unittest.TestCase):
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

    def source_replay(self, features):
        """Stand in for the externally supplied admitted source artifact."""
        return patch.multiple(
            feature_authority,
            load_pinned_atlas_snapshot=frozen_snapshot,
            build_feature_manifest=lambda snapshot, schema: features,
        )

    def read_receipt(self, features):
        """Read the live accepted receipt under the custody and source seams."""
        with shape_patch(), self.source_replay(features):
            return read_accepted_generation_feature_receipt(self.pointer, "/artifact")

    def test_accepted_generation_mints_source_replayed_receipt(self):
        features = source_features()
        published = self.publish(feature_bound(candidate(parent_state()), features))
        receipt = self.read_receipt(features)
        self.assertEqual(receipt.run_id, "fixture-run")
        self.assertEqual(receipt.generation, 0)
        self.assertEqual(receipt.generation_manifest_sha256, published["manifest_sha256"])
        self.assertEqual(receipt.feature_sha256, features.digest)
        self.assertEqual(receipt.semantic_release, RELEASE)
        self.assertEqual(receipt.source_atlas_bundle_id, ATLAS_BUNDLE)
        self.assertIsNone(receipt.predecessor_feature_sha256)

    def test_unaccepted_candidate_can_only_replay_its_recorded_source_features(self):
        features = source_features()
        proposed = feature_bound(candidate(parent_state()), features)
        with self.source_replay(features):
            replayed = authenticate_bamf_candidate_features(proposed, "/artifact")
        self.assertEqual(replayed, features)

        forged = feature_bound(proposed, features, digest=ARBITRARY)
        with self.source_replay(features), self.assertRaises(BilqisError) as failure:
            authenticate_bamf_candidate_features(forged, "/artifact")
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FEATURE_SOURCE_REPLAY_MISMATCH")

    def test_arbitrary_digest_candidate_cannot_self_ratify(self):
        features = source_features()
        adversary = feature_bound(
            candidate(parent_state()), features, digest=ARBITRARY)
        self.publish(adversary)
        with self.assertRaises(BilqisError) as failure:
            self.read_receipt(features)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FEATURE_SOURCE_REPLAY_MISMATCH")

    def test_forged_receipt_is_rejected_by_live_verification(self):
        features = source_features()
        self.publish(feature_bound(candidate(parent_state()), features))
        receipt = self.read_receipt(features)
        forged = replace(receipt, feature_sha256=ARBITRARY)
        with shape_patch(), self.source_replay(features):
            with self.assertRaises(BilqisError) as failure:
                verify_accepted_generation_feature_receipt(
                    self.pointer, "/artifact", forged)
        self.assertEqual(
            failure.exception.context["reason"], "BAMF_FEATURE_RECEIPT_MISMATCH")

    def test_generation_without_recorded_source_binding_refuses_receipt(self):
        features = source_features()
        self.publish(candidate(parent_state()))
        with self.assertRaises(BilqisError) as failure:
            self.read_receipt(features)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FEATURE_SOURCE_BINDING_MISSING")

    def test_release_drift_between_custody_and_source_refuses_receipt(self):
        features = source_features()
        self.publish(feature_bound(
            candidate(parent_state()), features, release="4" * 64))
        with self.assertRaises(BilqisError) as failure:
            self.read_receipt(features)
        self.assertEqual(
            failure.exception.context["reason"], "BAMF_FEATURE_SOURCE_IDENTITY_DRIFT")

    def test_cold_resume_reproduces_the_same_receipt_identity(self):
        features = source_features()
        self.publish(feature_bound(candidate(parent_state()), features))
        first = self.read_receipt(features)
        child = subprocess.run(
            [sys.executable, "-B", "-c", """
from pathlib import Path
from unittest.mock import patch
from bilqis_mlx.runtime.bamf_bundle import feature_authority, read_accepted_generation_feature_receipt
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.test_feature_authority import source_features, frozen_snapshot
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch

features = source_features()
with shape_patch(), patch.object(
        feature_authority, "load_pinned_atlas_snapshot",
        side_effect=frozen_snapshot), patch.object(
        feature_authority, "build_feature_manifest", return_value=features):
    print(read_accepted_generation_feature_receipt(Path(__import__('sys').argv[1]), "/artifact").digest)
""", str(self.pointer)],
            cwd=Path.cwd(), env=os.environ.copy(), text=True,
            capture_output=True, check=True)
        self.assertEqual(first.digest, child.stdout.strip().splitlines()[-1])

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
                self.pointer, "/artifact")
            self.assertEqual(
                verify_accepted_generation_feature_receipt(
                    self.pointer, "/artifact", receipt), receipt)
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
                        self.pointer, "/artifact", forged)

    def test_retained_successor_binds_the_feature_map_its_parent_consumed(self):
        root = source_features()
        first = self.publish(feature_bound(candidate(parent_state()), root))
        retained = feature_bound(
            candidate(accepted_state(parent_state()), 1, first["manifest_sha256"]),
            root)
        self.publish(retained)

        with shape_patch(), self.source_replay(root):
            receipt, current, predecessor = read_accepted_generation_feature_lineage(
                self.pointer, "/artifact")

        self.assertEqual(receipt.generation, 1)
        self.assertEqual(receipt.feature_sha256, root.digest)
        self.assertEqual(receipt.predecessor_feature_sha256, root.digest)
        self.assertEqual((current, predecessor), (root, root))

    def test_receipt_record_round_trip_detects_tampering(self):
        features = source_features()
        self.publish(feature_bound(candidate(parent_state()), features))
        receipt = self.read_receipt(features)
        record = receipt.to_record()
        self.assertEqual(
            feature_authority.AcceptedGenerationFeatureReceipt.from_record(record),
            receipt)
        tampered = {**record, "feature_sha256": ARBITRARY}
        with self.assertRaises(BilqisError) as failure:
            feature_authority.AcceptedGenerationFeatureReceipt.from_record(tampered)
        self.assertEqual(
            failure.exception.context["reason"], "BAMF_FEATURE_RECEIPT_INVALID")


if __name__ == "__main__":
    unittest.main()
