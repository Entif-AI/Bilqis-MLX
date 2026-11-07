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
from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, PlasticityPolicy
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWHyperparameters, _create_unbound_bamf_optimizer,
)
from bilqis_mlx.runtime.bamf_bundle import (
    BamfBundleCandidate, load_bamf_generation, publish_bamf_generation,
    stage_vocabulary_extension,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, GenerationProvenance, ModelTopologySpecV2,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import retention_decision
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.tests.atlas.vocabulary_fixtures import _allocation_fixture


HP = AdamWHyperparameters(.001, (.9, .95), 1e-8, .01)


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

    def _bundle(self, state, extents, features, snapshot, generation, parent):
        return BamfBundleCandidate(
            "a02-production-fixture", generation, parent, "e" * 64,
            ModelTopologySpecV2(), extents, state, HP,
            GenerationProvenance("a02-source", snapshot.release_sha256, "a02-teacher", 1),
            {"schema": "bilqis.mlx.bamf-semantic-abi/v1",
             "active_set_sha256": extents.active_semantic_digest,
             "semantic_bank_count": extents.semantic_bank_count,
             "bank_identities": [f"bank:{index}" for index in range(extents.semantic_bank_count)]},
            {"schema": "bilqis.mlx.bamf-compiler-features/v1",
             "factor_map_sha256": features.digest, "compiler_sha256": "f" * 64,
             "rights_epoch": 1, "correction_generation": 1,
             "feature_source": {"atlas_bundle_id": snapshot.bundle_id,
                                "release_sha256": snapshot.release_sha256,
                                "source_bundle_id": snapshot.source_bundle_id},
             "feature_schema": {"role_ids": [], "schema_ids": [], "source_bindings": []}},
            {"schema": "bilqis.mlx.bamf-correction-frontier/v1",
             "source_identity": "a02-source", "release_digest": snapshot.release_sha256,
             "rights_epoch": 1, "correction_generation": 1, "frontier": []},
            {"schema": "bilqis.mlx.bamf-teacher-state/v1", "teacher_identity": "a02-teacher",
             "teacher_epoch": 1, "next_seed": 1, "cursor": "a02"},
            {"schema": "bilqis.mlx.bamf-evaluation-contract/v1",
             "contract_sha256": "9" * 64},
            {"schema": "bilqis.mlx.bamf-generation-transition/v1",
             "kind": "INITIAL" if generation == 0 else "PARAMETER_EXTENSION",
             "invalidate_derived_caches": generation > 0},
            ({"event": "A02_SOURCE_GENERATION", "generation": generation},))

    def _accept(self, bundle, *, parent_state=None):
        decision = retention_decision(
            parent=parent_state or bundle.retained_state,
            retained=bundle.retained_state)
        binding = mint_acceptance_binding(
            decision, bundle.retained_state, run_id=bundle.run_id,
            generation=bundle.generation, feature_sha256=bundle.extents.factor_map_digest)
        return publish_bamf_generation(self.run, bundle, acceptance=binding)

    def _publish_source_parent(self):
        snapshot, _ = _allocation_fixture(highest=8192)
        root_snapshot = replace(
            snapshot, bundle_id="1" * 64, release_sha256="2" * 64,
            source_bundle_id="3" * 64, prior_abi_sha256=None)
        root_features = build_feature_manifest(root_snapshot, FeatureSchema((), ()))
        current_snapshot = replace(
            snapshot, bundle_id="4" * 64, release_sha256="5" * 64,
            source_bundle_id="6" * 64, prior_abi_sha256=root_snapshot.bundle_id)
        current_features = build_feature_manifest(
            current_snapshot, FeatureSchema((), (), root_features))
        allocations = MotifAllocationSnapshot(MotifManifest(root_snapshot.release_sha256))
        root_extents = GenerationExtents(
            1, 1, root_snapshot.active_set_sha256,
            allocations.manifest.digest, root_features.digest)
        optimizer, _decay, _manifest = _create_unbound_bamf_optimizer(
            ModelTopologySpecV2(), root_extents, run_seed=0)
        root_state = CandidateState(
            optimizer, PlasticityPolicy("FOUNDATION", 0, (IdentityRowAge(0, 0, 0),)),
            allocations, 0)
        first = self._accept(self._bundle(
            root_state, root_extents, root_features, root_snapshot, 0, None))
        current_extents = replace(root_extents, factor_map_digest=current_features.digest)
        current = self._bundle(
            root_state, current_extents, current_features, current_snapshot,
            1, first["manifest_sha256"])
        self._accept(current, parent_state=root_state)
        return root_snapshot, current_snapshot, optimizer

    def _source_patches(self, root_snapshot, current_snapshot):
        def source_snapshot(selection):
            return (root_snapshot if selection.release_sha256 == root_snapshot.release_sha256
                    else current_snapshot)

        source_nt = (
            '<urn:concept:8192> <http://www.w3.org/2004/02/skos/core#definition> '
            '"semantic role 8192"@en .\n').encode("utf-8")
        stack = ExitStack()
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

    def _generic_binding(self, parent, staged):
        state = staged.candidate.retained_state
        decision = retention_decision(parent=parent.retained_state, retained=state)
        return mint_acceptance_binding(
            decision, state, run_id=staged.candidate.run_id,
            generation=staged.candidate.generation,
            feature_sha256=staged.candidate.extents.factor_map_digest)

    def test_stages_bank_extension_without_granting_admission(self):
        root_snapshot, current_snapshot, optimizer = self._publish_source_parent()
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
        np.testing.assert_array_equal(
            np.asarray(staged.candidate.retained_state.optimizer.parameters["identity.bank.0"]),
            np.asarray(optimizer.parameters["identity.bank.0"]))
        self.assertTrue(bool(mx.all(
            staged.candidate.retained_state.optimizer.update_counts["identity.bank.1"] == 0)))
        self.assertIn(IdentityRowAge(1, 0, 0), staged.candidate.retained_state.policy.row_ages)
        with self.assertRaises(BilqisError) as failure:
            publish_bamf_generation(
                self.run, staged.candidate,
                acceptance=self._generic_binding(parent, staged))
        self.assertEqual(
            failure.exception.context["reason"], "BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED")


if __name__ == "__main__":
    unittest.main()
