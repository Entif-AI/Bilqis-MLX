"""B13.5 accepted-generation feature authority witnesses.

A caller-created candidate must never ratify its own factor-map digest. The
receipt is minted from custody and from the replayed admitted source release.
"""
from __future__ import annotations

import os
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    publish_bamf_generation, read_accepted_generation_feature_receipt,
    verify_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.bamf_bundle import feature_authority
from bilqis_mlx.semantics.atlas_features import AtlasFeatures

from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    publish_candidate,
    candidate, parent_state, shape_patch,
)

RELEASE = "1" * 64
ATLAS_BUNDLE = "2" * 64
SOURCE_BUNDLE = "3" * 64
ARBITRARY = "b" * 64
def feature_schema() -> dict:
    """One recorded feature schema shape with no categorical bindings."""
    return {"role_ids": [], "schema_ids": [], "source_bindings": []}


def source_features() -> AtlasFeatures:
    return AtlasFeatures(
        RELEASE, ATLAS_BUNDLE, SOURCE_BUNDLE, None, (), (), (), (), ())


def feature_bound(source, features: AtlasFeatures, *, digest=None, release=RELEASE):
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
                "atlas_bundle_id": ATLAS_BUNDLE,
                "release_sha256": release,
                "source_bundle_id": SOURCE_BUNDLE},
            "feature_schema": feature_schema()},
        correction_frontier={
            **source.correction_frontier, "release_digest": release})


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
            load_pinned_atlas_snapshot=lambda selection: selection,
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
        second = self.read_receipt(features)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first, second)

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
