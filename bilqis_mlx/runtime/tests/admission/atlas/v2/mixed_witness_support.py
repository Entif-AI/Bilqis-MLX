"""Authority-correct support for the #955 same-v2-lease mixed witness."""
from contextlib import ExitStack
from dataclasses import asdict, replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from bilqis_mlx.data_plane import close_data_planes
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_delta_adapter_fixtures import AtlasDeltaAdapterFixture
from bilqis_mlx.factory.tests.events.support import LEGACY
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.runtime import admission as factory_admission
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_admission import (
    AtlasSourceApproval, ResourceCeilingV2, _accepted_run_lease_identity,
    issue_atlas_lease_v2, persist_accepted_atlas_lease_v2,
)
from bilqis_mlx.runtime.atlas_admission_policy import AtlasAdmissionContext
from bilqis_mlx.runtime.atlas_admission_policy_v2 import AtlasAdmissionContextV2
from bilqis_mlx.runtime.bamf_bundle import issue_initial_foundation_feature_authority, publish_initial_generation
from bilqis_mlx.runtime.bamf_bundle import stage_vocabulary_extension
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _REGISTRY
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import genesis_preparation
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.runtime.tests.admission.atlas.v2.mixed_source_support import MixedSourceSupport
from bilqis_mlx.source_adapters import event_frames


class MixedWitnessSupport(MixedSourceSupport):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()
        close_data_planes()
        self.z = AtlasDeltaAdapterFixture()
        self.z.setUp()
        self.z.doCleanups()

    def tearDown(self):
        close_data_planes()
        self.environment.stop()
        self.temporary.cleanup()

    def publish_matching_genesis(self, snapshot, schema, features):
        selection = AtlasArtifactSelection(
            "/artifact", snapshot.bundle_id, snapshot.release_sha256,
            snapshot.source_bundle_id)
        executable = patch(
            "bilqis_mlx.runtime.tests.operator.test_admission._executable_fixture",
            return_value=(self.current, self.parent_graph))
        with self.source_replay(snapshot, schema, features), executable:
            authority = issue_initial_foundation_feature_authority(selection)
            prepared = genesis_preparation(
                run_id="mixed-v2-witness", foundation_features=authority)
        with self.source_replay(snapshot, schema, features), executable, patch(
                "bilqis_mlx.runtime.mlx_checkpoint.assert_headroom"):
            pointer = publish_initial_generation(self.run, prepared, reserve_gib=0.)
        factory_admission._persist_executable_factory_release(self.run, self.current)
        return pointer

    def runtime(self, current_release, checkpoint):
        from bilqis_mlx.curriculum.scheduler import start_new
        from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
        program = schedule_program_from_executable_release(current_release)
        return _PreparedSuccessorRuntime(
            None, self.run, {"school": asdict(start_new(program, checkpoint))},
            None, LEGACY, self.parent_graph, object(), object(), 0.)

    def issue_mixed_lease(self, h1, event_candidate, snapshot):
        event_operator = event_frames.SYMBOLS["D.EVENT_OCCURRENCE"]
        approval = _signed(replace(
            AtlasSourceApproval(
                "mixed-v2-witness-approval", snapshot.release_sha256,
                tuple(sorted(set(h1.family_ids)
                             | set(event_candidate.census.required_source_family_ids))),
                tuple(sorted(set(h1.operator_ids) | {event_operator})),
                "b" * 64, 1, "c" * 64, "d" * 64, "e" * 64,
                True, True, "fixture:salience-owner", "0" * 128),
            signature_hex="0" * 128))
        lease = issue_atlas_lease_v2(
            "mixed-v2-witness-lease", _accepted_run_lease_identity(self.run),
            approval, ResourceCeilingV2(8, 8, 65536, 1 << 44, 1 << 44),
            requested_at="2026-11-10T20:45:00Z",
            human_command_sha256="9" * 64, human_started=True,
            registry=_REGISTRY)
        with self.host_registry():
            source_authority = AcceptedRuntimeHost(self.run).source_authority()
            persist_accepted_atlas_lease_v2(
                self.run, lease, source_authority=source_authority)
        return approval, lease, source_authority

    def accepted_source_authority(self):
        with self.host_registry():
            return AcceptedRuntimeHost(self.run).source_authority()

    def capability_context(self, handoff, plan, learner, approval, source_authority):
        checkpoint = Checkpoint(
            learner.checkpoint_sha256, "bundles/mixed-v2-capability", learner.optimizer_step,
            True)
        legacy = AtlasAdmissionContext(
            _accepted_run_lease_identity(self.run), self.current,
            handoff.candidate_frontier, learner.ledger, plan, checkpoint,
            approval, _REGISTRY, self.combined_source_registry(), self.answer_registry)
        return AtlasAdmissionContextV2(
            legacy, self.run,
            runtime=self.runtime(self.current, checkpoint),
            source_authority=source_authority)

    def a02_source_patches(self, snapshot, semantic_id):
        source_nt = (
            f'<{semantic_id}> <http://www.w3.org/2004/02/skos/core#definition> '
            '"mixed witness semantic role"@en .\n').encode("utf-8")
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
            stack.enter_context(patch(target, return_value=snapshot))
        stack.enter_context(patch(
            "bilqis_mlx.semantics.atlas.vocabulary_resources._verify_bundle",
            return_value=(snapshot.source_bundle_id, {"canonical.nt": source_nt})))
        stack.enter_context(patch(
            "bilqis_mlx.runtime.bamf_bundle.vocabulary_admission.shutil.disk_usage",
            return_value=type("Disk", (), {"free": 1 << 50})()))
        return stack

    def stage_event_a02(self, snapshot, semantic_id):
        with self.a02_source_patches(snapshot, semantic_id):
            return stage_vocabulary_extension(
                self.run, "/artifact", Path("/source"), (semantic_id,))

    def parameter_context(
            self, handoff, plan, ledger, checkpoint_sha256, step,
            approval, native_staged, source_authority, current_release):
        checkpoint = Checkpoint(
            checkpoint_sha256, "bundles/mixed-v2-parameter", step, True)
        runtime = self.runtime(current_release, checkpoint)
        legacy = AtlasAdmissionContext(
            _accepted_run_lease_identity(self.run), current_release,
            handoff.candidate_frontier, ledger, plan, checkpoint,
            approval, _REGISTRY, self.combined_source_registry(), self.answer_registry,
            runtime, native_staged, source_authority)
        return AtlasAdmissionContextV2(legacy, self.run)

    def complete_parameter_leg(
            self, *, semantic_id, h2, plan2, ledger2, checkpoint2, step2,
            approval, lease, cold1, pointer1, accepted1, binding1,
            snapshot, schema, features, combined):
        from bilqis_mlx.runtime.atlas_admission import (
            adopt_parameter_extension_atlas_successor_v2,
            read_accepted_atlas_factory_release,
        )
        from bilqis_mlx.runtime.atlas_admission_policy_v2 import AtlasDeltaEnvelopeV2
        from bilqis_mlx.runtime.bamf_bundle.atlas_admission import ParsedAtlasAdmissionBinding
        from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
            accepted_binding_for_manifest, accepted_generation,
        )
        from bilqis_mlx.runtime.bamf_bundle.vocabulary.admission_facts import (
            read_issued_a02_staged_admission_facts_v2,
        )

        native2 = self.stage_event_a02(snapshot, semantic_id)
        facts2 = read_issued_a02_staged_admission_facts_v2(native2)
        self.assertEqual(facts2.allocation_semantic_ids, (semantic_id,))
        self.assertEqual(native2.receipt.parent_manifest_sha256,
                         pointer1["manifest_sha256"])
        current2 = self.parameter_context(
            h2, plan2, ledger2, checkpoint2, step2, approval, native2,
            self.accepted_source_authority(), cold1)
        with patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=combined), patch(
                    "bilqis_mlx.factory.live_answers.live_answer_registry",
                    return_value=self.answer_registry), self.source_replay(
                        snapshot, schema, features), patch(
                            "bilqis_mlx.runtime.mlx_checkpoint.assert_headroom"):
            result2 = adopt_parameter_extension_atlas_successor_v2(
                current2, AtlasDeltaEnvelopeV2(h2, native2), lease)
        self.assertEqual(result2.accepted_generation, 2)
        pointer2, accepted2 = accepted_generation(self.run / "bamf-state.json")
        binding2 = accepted_binding_for_manifest(
            self.run, pointer2["manifest_sha256"], accepted2,
            expected_acceptance_sha256=pointer2["acceptance_sha256"])
        self.assertIsInstance(binding2, ParsedAtlasAdmissionBinding)
        self.assertEqual(binding2.lease_sha256, lease.digest())
        self.assertEqual(binding2.lease_sha256, binding1.lease_sha256)
        self.assertEqual(read_accepted_atlas_factory_release(self.run).release_sha256,
                         h2.staged_candidate.successor.release_sha256)
        self.assertEqual(accepted2.topology, accepted1.topology)
        self.assertEqual(accepted2.optimizer_hyperparameters,
                         accepted1.optimizer_hyperparameters)
        self.assertEqual(accepted2.provenance, accepted1.provenance)
        self.assertEqual(accepted2.correction_frontier, accepted1.correction_frontier)
        self.assertEqual(accepted2.teacher_state, accepted1.teacher_state)
        self.assertEqual(accepted2.evaluation_contract, accepted1.evaluation_contract)
        self.assertEqual(accepted2.retained_state.allocations,
                         native2.candidate.retained_state.allocations)
        self.assertEqual(accepted2.retained_state.policy,
                         native2.candidate.retained_state.policy)
        self.assertEqual(accepted2.extents, native2.candidate.extents)
        self.assertEqual(native2.candidate.retained_state.policy,
                         accepted1.retained_state.policy)
        self.assertNotEqual(native2.candidate.extents.digest, accepted1.extents.digest)
        for field in ("parameters", "m", "v", "update_counts"):
            self.assert_tree_prefix(
                self, getattr(accepted1.retained_state.optimizer, field),
                getattr(accepted2.retained_state.optimizer, field))
        self.assertEqual(self.neural_fingerprint(accepted2),
                         self.neural_fingerprint(native2.candidate))
        fingerprint = self.run_fingerprint()
        with self.source_replay(snapshot, schema, features), patch(
                "bilqis_mlx.runtime.atlas_adoption_v2.advance_atlas_frontier_v2",
                side_effect=AssertionError("exact retry reached verifier")), patch(
                    "bilqis_mlx.runtime.atlas_parameter_adoption_v2."
                    "publish_native_staged_candidate_v2",
                    side_effect=AssertionError("exact retry reached publisher")):
            retry2 = adopt_parameter_extension_atlas_successor_v2(
                current2, AtlasDeltaEnvelopeV2(h2, native2), lease)
        self.assertEqual(retry2.accepted_manifest_sha256, pointer2["manifest_sha256"])
        self.assertEqual(self.run_fingerprint(), fingerprint)
        self.assertFalse((self.run / "autonomy/atlas-admission/current.json").exists())
