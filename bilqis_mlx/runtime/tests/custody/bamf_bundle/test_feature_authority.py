"""B13.5 accepted-generation to predecessor-feature authority witnesses."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    AcceptedGenerationFeatureReceipt,
    publish_bamf_generation,
    read_accepted_generation_feature_receipt,
    verify_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate, parent_state, shape_patch
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, GenerationProvenance, ModelTopologySpecV2
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas.vocabulary import plan_vocabulary_extension
from bilqis_mlx.semantics.tests.atlas.vocabulary_fixtures import _allocation_fixture


class AcceptedGenerationFeatureAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_bamf_generation(self.run, candidate(parent_state()))

    def test_published_generation_reproduces_one_feature_authority_receipt(self):
        pointer = self.publish()
        with shape_patch():
            receipt = read_accepted_generation_feature_receipt(self.run / "bamf-state.json")
            verified = verify_accepted_generation_feature_receipt(
                self.run / "bamf-state.json", receipt)
        self.assertEqual(receipt.generation_manifest_sha256, pointer["manifest_sha256"])
        self.assertEqual(receipt.predecessor_feature_sha256, "c" * 64)
        self.assertEqual(receipt.semantic_release, "d" * 64)
        self.assertEqual(verified, receipt)
        self.assertEqual(
            AcceptedGenerationFeatureReceipt.from_record(receipt.to_record()), receipt)

    def test_substituted_generation_or_feature_binding_rejects(self):
        self.publish()
        with shape_patch():
            receipt = read_accepted_generation_feature_receipt(self.run / "bamf-state.json")
            for forged in (
                replace(receipt, predecessor_feature_sha256="0" * 64),
                replace(receipt, generation_manifest_sha256="1" * 64),
            ):
                with self.subTest(forged=forged), self.assertRaises(BilqisError):
                    verify_accepted_generation_feature_receipt(
                        self.run / "bamf-state.json", forged)

    def test_unpublished_candidate_cannot_mint_accepted_receipt(self):
        self.run.mkdir()
        with self.assertRaises(BilqisError):
            read_accepted_generation_feature_receipt(self.run / "bamf-state.json")

    def test_verified_b13_receipt_unlocks_a02_but_plain_receipt_does_not(self):
        first_snapshot, prior = _allocation_fixture()
        snapshot = replace(
            first_snapshot,
            release_sha256="7" * 64,
            bundle_id="8" * 64,
            prior_abi_sha256=prior.features.atlas_bundle_id,
        )
        schema = FeatureSchema(
            prior.feature_schema.role_ids,
            prior.feature_schema.schema_ids,
            predecessor=prior.features,
            source_bindings=prior.feature_schema.source_bindings,
        )
        features = build_feature_manifest(snapshot, schema)
        source = candidate(parent_state())
        extents = GenerationExtents(
            prior.extents.semantic_bank_count,
            source.extents.motif_page_count,
            prior.extents.active_semantic_digest,
            source.extents.motif_key_map_digest,
            features.digest,
        )
        source = replace(
            source,
            extents=extents,
            provenance=GenerationProvenance(
                source.provenance.source_identity, features.semantic_release,
                source.provenance.teacher_identity, source.provenance.teacher_epoch),
            semantic_abi={**source.semantic_abi,
                          "active_set_sha256": extents.active_semantic_digest},
            compiler_features={**source.compiler_features,
                               "factor_map_sha256": features.digest},
            correction_frontier={**source.correction_frontier,
                                 "release_digest": features.semantic_release},
        )
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            publish_bamf_generation(self.run, source)
            receipt = read_accepted_generation_feature_receipt(self.run / "bamf-state.json")
            verify_accepted_generation_feature_receipt(
                self.run / "bamf-state.json", receipt)
            successor = replace(
                prior, extents=extents, features=features, feature_schema=schema,
                generation_id=receipt.generation_manifest_sha256)
            with patch(
                "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
                return_value=snapshot,
            ):
                plan = plan_vocabulary_extension(
                    successor, ("urn:concept:8191",), ModelTopologySpecV2(),
                    predecessor_receipt=receipt,
                    accepted_generation_pointer=self.run / "bamf-state.json")
                self.assertEqual(plan.parent_generation_id, receipt.generation_manifest_sha256)
                with self.assertRaises(BilqisError):
                    plan_vocabulary_extension(
                        successor, ("urn:concept:8191",), ModelTopologySpecV2(),
                        predecessor_receipt=receipt)


if __name__ == "__main__":
    unittest.main()
