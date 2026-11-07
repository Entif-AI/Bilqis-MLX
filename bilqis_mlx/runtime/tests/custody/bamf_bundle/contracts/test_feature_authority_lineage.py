"""Successor-lineage adversaries for B13.5 accepted feature authority."""
from __future__ import annotations

import hashlib
import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    read_accepted_generation_feature_lineage,
    verify_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.bamf_bundle import feature_authority
from bilqis_mlx.runtime.bamf_bundle.records import canonical
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.test_feature_authority import (
    ARBITRARY, feature_bound, frozen_snapshot, source_features,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, parent_state, publish_candidate, shape_patch,
)

SUCCESSOR_RELEASE = "c" * 64
SUCCESSOR_ATLAS_BUNDLE = "d" * 64
SUCCESSOR_SOURCE_BUNDLE = "e" * 64


class AcceptedFeatureLineageTests(unittest.TestCase):
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
        return patch.multiple(
            feature_authority,
            load_pinned_atlas_snapshot=frozen_snapshot,
            build_feature_manifest=lambda snapshot, schema: features,
        )

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

    def test_successor_rejects_resigned_historical_parent_acceptance(self):
        root = source_features()
        first = self.publish(feature_bound(candidate(parent_state()), root))
        retained = feature_bound(
            candidate(accepted_state(parent_state()), 1, first["manifest_sha256"]),
            root)
        self.publish(retained)

        parent_acceptance = (
            self.run / "bamf-acceptance" / f"{first['manifest_sha256']}.json")
        record = json.loads(parent_acceptance.read_text())
        record["policy_sha256"] = "0" * 64
        record["binding_sha256"] = hashlib.sha256(canonical({
            key: value for key, value in record.items()
            if key != "binding_sha256"
        })).hexdigest()
        parent_acceptance.write_text(json.dumps(record))

        with shape_patch(), self.source_replay(root), self.assertRaises(BilqisError):
            read_accepted_generation_feature_lineage(self.pointer, "/artifact")


if __name__ == "__main__":
    unittest.main()
