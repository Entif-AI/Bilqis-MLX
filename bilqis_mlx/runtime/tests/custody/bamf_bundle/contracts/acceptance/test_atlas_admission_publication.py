"""C07-authorized parameter extensions publish through ordinary B13 custody."""
from dataclasses import replace
import numpy as np

from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation_authority, publish_atlas_admission_generation,
    read_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
    _issue_atlas_admission_binding,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    frozen_snapshot as genesis_frozen_snapshot,
    source_features as genesis_source_features,
)

from ._generation_acceptance_support import *


class AtlasAdmissionPublicationTests(GenerationAcceptanceFixture, unittest.TestCase):
    def extension(self):
        parent = self.parent()
        source = candidate(
            parent.retained_state, 1, self._parent_pointer["manifest_sha256"])
        active = "8" * 64
        return parent, replace(
            source,
            run_identity=parent.run_identity,
            implementation_sha256=parent.implementation_sha256,
            topology=parent.topology,
            extents=replace(parent.extents, active_semantic_digest=active),
            provenance=parent.provenance,
            semantic_abi={**parent.semantic_abi, "active_set_sha256": active},
            compiler_features=dict(parent.compiler_features),
            correction_frontier=dict(parent.correction_frontier),
            teacher_state=dict(parent.teacher_state),
            evaluation_contract=dict(parent.evaluation_contract),
            transition={
                "schema": "bilqis.mlx.bamf-generation-transition/v1",
                "kind": "PARAMETER_EXTENSION",
                "invalidate_derived_caches": True,
            },
        )

    def test_retention_acceptance_cannot_publish_vocabulary_extension(self):
        _parent, source = self.extension()
        with self.assertRaises(BilqisError) as failure:
            self.publish(source, acceptance=self.binding(source))
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED")
        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text()),
            self._parent_pointer)

    def test_c07_binding_publishes_and_cold_replays_exact_generation(self):
        parent, source = self.extension()
        features = genesis_source_features()
        with shape_patch(), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature_authority."
                "build_feature_manifest", return_value=features), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature_authority."
                "resolve_atlas_artifact_selection",
                side_effect=lambda identity: AtlasArtifactSelection(
                    "/fixture/atlas", identity.bundle_id,
                    identity.release_sha256, identity.source_bundle_id)), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature_authority."
                "load_pinned_atlas_snapshot",
                side_effect=genesis_frozen_snapshot), patch.object(
                mlx_checkpoint, "assert_headroom"):
            binding = _issue_atlas_admission_binding(
                source, parent,
                lease_sha256="9" * 64,
                source_approval_sha256="8" * 64,
                proposal_sha256="7" * 64,
                factory_release_sha256="6" * 64,
                staging_receipt_sha256="5" * 64,
                parent_feature_receipt_sha256="4" * 64,
            )
            pointer = publish_atlas_admission_generation(
                self.run, source, admission=binding, reserve_gib=0.)
            loaded, manifest = load_bamf_generation_authority(
                self.run / "bamf-state.json")
            receipt = read_accepted_generation_feature_receipt(
                self.run / "bamf-state.json")

        self.assertEqual(pointer["generation"], 1)
        self.assertEqual(manifest, pointer["manifest_sha256"])
        self.assertEqual(loaded.extents, source.extents)
        self.assertEqual(
            set(loaded.retained_state.optimizer.update_counts),
            set(source.retained_state.optimizer.update_counts))
        for name, expected in source.retained_state.optimizer.update_counts.items():
            np.testing.assert_array_equal(
                np.asarray(loaded.retained_state.optimizer.update_counts[name]),
                np.asarray(expected))
        self.assertEqual(receipt.generation_manifest_sha256, manifest)
        self.assertEqual(receipt.acceptance_sha256, binding.digest)
        self.assertEqual(receipt.active_set_sha256,
                         source.extents.active_semantic_digest)


if __name__ == "__main__":
    unittest.main()
