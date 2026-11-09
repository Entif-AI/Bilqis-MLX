"""Full-topology A02 staging through accepted B13 custody."""
from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge
from bilqis_mlx.runtime.bamf_bundle import (
    issue_initial_foundation_feature_authority, load_bamf_generation,
    publish_bamf_generation, publish_initial_generation, stage_vocabulary_extension,
)
from bilqis_mlx.runtime.bamf_bundle.genesis import foundation as genesis_foundation
from bilqis_mlx.runtime.bamf_bundle.admission import derive_successor_bundle
from bilqis_mlx.runtime.model_topology_v2 import (
    expected_bamf_shapes, initialize_bamf_row,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, genesis_preparation,
)
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas.vocabulary_factors import prepare_identity_factors
from bilqis_mlx.semantics.tests.atlas.vocabulary_fixtures import _allocation_fixture


@unittest.skipUnless(os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
                     "full v2 production-staging witness is explicitly gated")
class A02ProductionStagingTests(unittest.TestCase):
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

    def _accept(self, bundle, *, parent_state=None):
        return publish_bamf_generation(
            self.run, bundle,
            acceptance=acceptance(bundle, parent=parent_state), reserve_gib=0.)

    def _publish_source_parent(self):
        root_base, _ = _allocation_fixture(highest=8191)
        current_base, _ = _allocation_fixture(highest=8192)
        root_snapshot = replace(
            root_base, bundle_id="1" * 64, release_sha256="2" * 64,
            source_bundle_id="3" * 64, prior_abi_sha256=None)
        root_features = build_feature_manifest(root_snapshot, FeatureSchema((), ()))
        current_snapshot = replace(
            current_base, bundle_id="4" * 64, release_sha256="5" * 64,
            source_bundle_id="6" * 64, prior_abi_sha256=root_snapshot.bundle_id)
        current_features = build_feature_manifest(
            current_snapshot, FeatureSchema((), (), root_features))
        selection = AtlasArtifactSelection(
            "/artifact", root_snapshot.bundle_id, root_snapshot.release_sha256,
            root_snapshot.source_bundle_id)
        root_schema = FeatureSchema((), ())
        foundation_replay = patch.multiple(
            genesis_foundation,
            _source_owned_feature_schema=lambda _selection: (root_snapshot, root_schema),
            build_feature_manifest=lambda _snapshot, _schema: root_features,
        )
        with foundation_replay:
            authority = issue_initial_foundation_feature_authority(selection)
            prepared = genesis_preparation(
                run_id="a02-production-fixture", foundation_features=authority)
            with patch.object(mlx_checkpoint, "assert_headroom"):
                first = publish_initial_generation(
                    self.run, prepared, reserve_gib=0.)
        parent = load_bamf_generation(self.pointer, publish_missing_outbox=False)
        current = derive_successor_bundle(
            parent, parent.retained_state,
            parent_manifest_sha256=first["manifest_sha256"],
            delivery_events=({"event": "A02_SOURCE_GENERATION", "generation": 1},),
        )
        current = replace(
            current,
            extents=replace(parent.extents, factor_map_digest=current_features.digest),
            provenance=replace(parent.provenance, release_digest=current_snapshot.release_sha256),
            compiler_features={
                **parent.compiler_features,
                "factor_map_sha256": current_features.digest,
                "feature_source": {
                    "atlas_bundle_id": current_snapshot.bundle_id,
                    "release_sha256": current_snapshot.release_sha256,
                    "source_bundle_id": current_snapshot.source_bundle_id,
                },
            },
            correction_frontier={
                **parent.correction_frontier,
                "release_digest": current_snapshot.release_sha256,
            },
            transition={
                "schema": "bilqis.mlx.bamf-generation-transition/v1",
                "kind": "PARAMETER_EXTENSION",
                "invalidate_derived_caches": True,
            },
        )
        self._accept(current, parent_state=parent.retained_state)
        return (
            root_snapshot, current_snapshot, current_features,
            parent.retained_state.optimizer,
        )

    def _source_patches(self, root_snapshot, current_snapshot):
        def source_snapshot(selection):
            return (root_snapshot if selection.release_sha256 == root_snapshot.release_sha256
                    else current_snapshot)

        source_nt = (
            '<urn:concept:8192> <http://www.w3.org/2004/02/skos/core#definition> '
            '"semantic role 8192"@en .\n').encode("utf-8")
        stack = ExitStack()
        stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.feature_authority."
            "resolve_atlas_artifact_selection",
            side_effect=lambda identity: AtlasArtifactSelection(
                "/artifact", identity.bundle_id, identity.release_sha256,
                identity.source_bundle_id)))
        for target in (
                "bilqis_mlx.runtime.bamf_bundle.feature_authority.load_pinned_atlas_snapshot",
                "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission.load_pinned_atlas_snapshot",
                "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
                "bilqis_mlx.semantics.atlas.vocabulary_resources.load_pinned_atlas_snapshot"):
            stack.enter_context(patch(target, side_effect=source_snapshot))
        stack.enter_context(patch(
            "bilqis_mlx.semantics.atlas.vocabulary_resources._verify_bundle",
            return_value=(current_snapshot.source_bundle_id, {"canonical.nt": source_nt})))
        return stack

    def test_stages_bank_extension_without_granting_admission(self):
        root_snapshot, current_snapshot, current_features, optimizer = (
            self._publish_source_parent())
        parent = load_bamf_generation(self.pointer, publish_missing_outbox=False)
        with self._source_patches(root_snapshot, current_snapshot):
            with self.assertRaises(BilqisError):
                stage_vocabulary_extension(
                    self.run, "/artifact", Path("/source"),
                    ("urn:concept:not-present",))
            staged = stage_vocabulary_extension(
                self.run, "/artifact", Path("/source"), ("urn:concept:8192",))
        self.assertEqual(
            load_bamf_generation(self.pointer, publish_missing_outbox=False).generation, 1)
        self.assertEqual(staged.receipt.generation, 2)
        self.assertEqual(staged.receipt.semantic_bank_count, 2)
        self.assertEqual(staged.receipt.status, "STAGED_NOT_ADMITTED")
        self.assertNotEqual(
            parent.run_identity.run_seed, parent.topology.default_run_seed)
        feature_names = (
            "features.type", "features.project_type",
            "features.project_graph", "features.gates",
        )
        _, factors = prepare_identity_factors(
            current_snapshot, current_features, ("urn:concept:8192",),
            {name: parent.retained_state.optimizer.parameters[name]
             for name in feature_names},
            extents=parent.extents,
        )
        specs = {
            item.name: item for item in expected_bamf_shapes(
                parent.topology, staged.candidate.extents)
        }
        expected_row = initialize_bamf_row(
            specs["identity.bank.1"], run_seed=parent.run_identity.run_seed,
            row_id="urn:concept:8192", factor=factors[0][1],
        )
        np.testing.assert_array_equal(
            np.asarray(staged.candidate.retained_state.optimizer.parameters[
                "identity.bank.1"][0]),
            expected_row,
        )
        np.testing.assert_array_equal(
            np.asarray(staged.candidate.retained_state.optimizer.parameters["identity.bank.0"]),
            np.asarray(optimizer.parameters["identity.bank.0"]))
        self.assertTrue(bool(mx.all(
            staged.candidate.retained_state.optimizer.update_counts["identity.bank.1"] == 0)))
        self.assertIn(IdentityRowAge(1, 0, 0), staged.candidate.retained_state.policy.row_ages)
        with self.assertRaises(BilqisError) as failure:
            publish_bamf_generation(
                self.run, staged.candidate,
                acceptance=acceptance(
                    staged.candidate, parent=parent.retained_state),
                reserve_gib=0.)
        self.assertEqual(
            failure.exception.context["reason"], "BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED")


if __name__ == "__main__":
    unittest.main()
