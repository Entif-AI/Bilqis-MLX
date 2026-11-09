"""Composed C07 Factory -> B13 -> cold-read -> retry witness."""
from dataclasses import asdict, replace
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.data_plane import close_data_planes
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.jit_adoption import (
    _PreparedSuccessorRuntime, _accepted_lease_run_identity,
    _publish_native_staged_candidate,
)
from bilqis_mlx.runtime.tests.admission.atlas.atlas_adoption_executor_support import (
    AtlasAdoptionExecutorFixture,
)
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _lease
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    publish_genesis, shape_patch,
)


def _source_replay(features):
    from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
    from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
        frozen_snapshot as genesis_frozen_snapshot,
    )

    return (
        patch(
            "bilqis_mlx.runtime.bamf_bundle.feature_authority.build_feature_manifest",
            return_value=features),
        patch(
            "bilqis_mlx.runtime.bamf_bundle.feature_authority."
            "resolve_atlas_artifact_selection",
            side_effect=lambda identity: AtlasArtifactSelection(
                "/fixture/atlas", identity.bundle_id,
                identity.release_sha256, identity.source_bundle_id)),
        patch(
            "bilqis_mlx.runtime.bamf_bundle.feature_authority."
            "load_pinned_atlas_snapshot",
            side_effect=genesis_frozen_snapshot),
    )


def _stage_successor(test_case, parent, parent_manifest, parent_feature):
    from bilqis_mlx.runtime.bamf_bundle.admission import derive_successor_bundle

    raw_candidate = derive_successor_bundle(
        parent, parent.retained_state,
        parent_manifest_sha256=parent_manifest,
        delivery_events=({"event": "A02_C07_COMPOSED_WITNESS"},))
    active = "8" * 64
    raw_candidate = replace(
        raw_candidate,
        extents=replace(parent.extents, active_semantic_digest=active),
        semantic_abi={**parent.semantic_abi, "active_set_sha256": active},
        transition={
            "schema": "bilqis.mlx.bamf-generation-transition/v1",
            "kind": "PARAMETER_EXTENSION",
            "invalidate_derived_caches": True})
    return test_case._a02_staged(
        raw_candidate, parent_feature=parent_feature.digest)


def _assert_normalized_accepted(test_case, native_staged, accepted_pointer, accepted):
    from bilqis_mlx.runtime import checkpoint_outbox
    from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
        initial_generation_candidate_identity_digest,
    )

    test_case.assertEqual(
        initial_generation_candidate_identity_digest(accepted),
        initial_generation_candidate_identity_digest(native_staged.candidate))
    expected_outbox = tuple(checkpoint_outbox.with_delivery_outbox(
        {"run_id": native_staged.candidate.run_id,
         "generation": native_staged.candidate.generation},
        native_staged.candidate.outbox)["delivery_outbox"])
    test_case.assertEqual(accepted.outbox, expected_outbox)
    test_case.assertEqual(
        candidate_identity_digest(accepted.retained_state),
        native_staged.receipt.candidate_identity_sha256)
    test_case.assertEqual(
        accepted.retained_state.custody.manifest_sha256,
        accepted_pointer["manifest_sha256"])
    test_case.assertEqual(
        accepted.retained_state.custody.extents_digest,
        native_staged.candidate.extents.digest)


class AtlasAdoptionCommitWitnessTests(
        AtlasAdoptionExecutorFixture, unittest.TestCase):
    def test_factory_persist_b13_publish_cold_read_and_exact_retry(self):
        from bilqis_mlx.curriculum.scheduler import start_new
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        from bilqis_mlx.learning.champions import Checkpoint
        from bilqis_mlx.runtime import admission as factory_admission
        import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
        from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
        from bilqis_mlx.runtime.bamf_bundle import (
            load_bamf_generation_authority, read_accepted_generation_feature_receipt,
        )
        from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import accepted_generation
        from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
            source_features as genesis_source_features,
        )
        from bilqis_mlx.runtime.tests.operator.test_admission import _executable_fixture

        current, graph = _executable_fixture(seed=17)
        successor, successor_graph = _executable_fixture(seed=18)
        self.assertEqual(successor_graph, graph)
        self.assertNotEqual(successor.release_sha256, current.release_sha256)
        origin = Checkpoint("7" * 64, "bundles/foundation-origin", 0, True)
        features = genesis_source_features()

        environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        environment.start()
        self.addCleanup(environment.stop)
        close_data_planes()
        self.addCleanup(close_data_planes)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            pointer0 = publish_genesis(self.root)
        factory_admission._persist_executable_factory_release(self.root, current)
        replay = _source_replay(features)
        with replay[0], replay[1], replay[2], shape_patch():
            parent, parent_manifest = load_bamf_generation_authority(
                self.root / "bamf-state.json")
            parent_feature = read_accepted_generation_feature_receipt(
                self.root / "bamf-state.json")
        self.assertEqual(parent_manifest, pointer0["manifest_sha256"])
        self.assertEqual(parent.run_identity.factory_release_sha256, current.release_sha256)

        native_staged = _stage_successor(
            self, parent, parent_manifest, parent_feature)
        lease = replace(
            _lease(), run_identity=_accepted_lease_run_identity(parent.run_identity))
        selected = SimpleNamespace(successor=successor)
        proposal = SimpleNamespace(proposal_sha256="7" * 64)
        program = schedule_program_from_executable_release(current)
        runtime = _PreparedSuccessorRuntime(
            None, self.root, {"school": asdict(start_new(program, origin))},
            None, None, graph, object(), object(), 0.)

        replay = _source_replay(features)
        with patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease",
                return_value=lease), replay[0], replay[1], replay[2], shape_patch(), \
                patch.object(mlx_checkpoint, "assert_headroom"):
            pointer1 = _publish_native_staged_candidate(
                runtime, selected, proposal, native_staged, lease, object(),
                current=current, checkpoint=origin)
            cold = read_accepted_atlas_factory_release(self.root)
            bundles_before_retry = tuple(sorted(
                path.name for path in (self.root / "bamf-bundles").iterdir()
                if path.is_dir()))
            accepted_pointer, accepted = accepted_generation(
                self.root / "bamf-state.json")
            _assert_normalized_accepted(
                self, native_staged, accepted_pointer, accepted)
            pointer2 = _publish_native_staged_candidate(
                runtime, selected, proposal, native_staged, lease, object(),
                current=current, checkpoint=origin)
            bundles_after_retry = tuple(sorted(
                path.name for path in (self.root / "bamf-bundles").iterdir()
                if path.is_dir()))

        self.assertEqual(pointer1, pointer2)
        self.assertEqual(pointer1["generation"], 1)
        self.assertEqual(cold, successor)
        self.assertEqual(bundles_before_retry, bundles_after_retry)
        self.assertTrue((self.root / "bamf-state.json").is_file())
        self.assertFalse((self.root / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
