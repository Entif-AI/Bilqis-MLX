"""Production #1010 A09 projection over accepted B13 custody, without a C07 lease."""
from unittest.mock import patch
import unittest

from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier import _rights
from bilqis_mlx.paths import LEGACY_SOURCE
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_lease_storage import classify_accepted_atlas_epoch
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
from bilqis_mlx.runtime.priority_authority import _priority_planning
from bilqis_mlx.runtime.tests.admission.atlas.v2.mixed_witness_support import (
    MixedWitnessSupport,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection


class PriorityPlanningRuntimeTests(MixedWitnessSupport, unittest.TestCase):
    def test_accepted_a09_projection_needs_no_c07_lease_or_neural_mutation(self):
        with shape_patch():
            snapshot, candidate, schema, features = self.common_atlas()
            selection = AtlasArtifactSelection(
                "/artifact", snapshot.bundle_id, snapshot.release_sha256,
                snapshot.source_bundle_id)
            source_frontier, policy = _rights()
            source_authority = type("Authority", (), {
                "frontier": source_frontier,
                "policy": policy,
            })()
            combined = self.combined_source_registry()
            self.publish_matching_genesis(snapshot, schema, features)
            before, _manifest = load_bamf_generation_authority(
                self.run / "bamf-state.json")
            self.assertEqual(classify_accepted_atlas_epoch(self.run), "staged")

            with self.source_replay(snapshot, schema, features), self.host_registry(), patch(
                    "bilqis_mlx.runtime.atlas_flywheel_runtime."
                    "resolve_atlas_artifact_selection",
                    return_value=selection), patch(
                        "bilqis_mlx.factory.skos_curriculum."
                        "compile_semantic_curriculum",
                        return_value=candidate), patch(
                            "bilqis_mlx.factory.skos_curriculum."
                            "issue_source_context_transition_authority",
                            return_value=source_authority), patch(
                                "bilqis_mlx.runtime.atlas_flywheel_runtime."
                                "_candidate_frontier",
                                return_value=self.frontier), patch(
                                    "bilqis_mlx.runtime.atlas_flywheel_runtime."
                                    "live_source_registry",
                                    return_value=combined), patch(
                                        "bilqis_mlx.runtime.atlas_flywheel_runtime."
                                        "live_answer_registry",
                                        return_value=self.answer_registry), patch(
                                            "bilqis_mlx.source_adapters.school."
                                            "live_source_registry",
                                            return_value=combined), patch(
                                                "bilqis_mlx.factory.live_answers."
                                                "live_answer_registry",
                                                return_value=self.answer_registry):
                context = AcceptedRuntimeHost(self.run).source_context(
                    source_root=LEGACY_SOURCE.resolve())
                planning = _priority_planning(
                    self.run, context, selection.path)

            after, _manifest = load_bamf_generation_authority(
                self.run / "bamf-state.json")
            planning.progress.verify()
            planning.closure.verify()
            self.assertEqual(
                planning.progress.input_snapshot_sha256,
                planning.closure.snapshot_sha256)
            self.assertEqual(classify_accepted_atlas_epoch(self.run), "staged")
            self.assertEqual(
                after.retained_state.optimizer_step,
                before.retained_state.optimizer_step)
            self.assertEqual(after.teacher_state, before.teacher_state)
            self.assertFalse((self.run / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
