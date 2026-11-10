"""C09 learned-support dependencies observed by the real retained-motif B11 path."""
from unittest import TestCase, skipUnless

from bilqis_mlx.learning.atlas_readout import ControlAction, DecisionOutput
from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch, bamf_value_and_grad
from bilqis_mlx.runtime.atlas_training_authority import _issue as issue_training_authority
from bilqis_mlx.runtime.atlas_training_contracts import (
    BamfDeliveryProvenance, BamfTrainingRow, _issue_training_batch,
)
from bilqis_mlx.runtime.bamf_bundle.execution_cache import bind_motif_artifact_owner
from bilqis_mlx.runtime.source_execution import source_content_digest
from bilqis_mlx.runtime.tests.model.test_atlas_model_retained import (
    AtlasModelRetainedMotifTests,
)
from bilqis_mlx.runtime.tests.model.execution.active_semantic_rows_support import snapshot_active_semantic_rows
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import visit_provenance
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE


def _training_authority(compiled, source, generation):
    row = source.source_row
    dependencies = {
        DependencyRef(DependencyKind.SOURCE, row["id"]),
        DependencyRef(DependencyKind.RELEASE, "release:" + compiled.features.semantic_release),
    }
    for node in compiled.packed_frame_artifact_owner.require_row(compiled.compiled.rows[0]):
        dependencies.update(node.immediate_dependencies)
    provenance = BamfDeliveryProvenance(
        row["id"], source_content_digest((row,)), row.get("source_id"),
        row.get("capability", "A.IDENTITY"), None, (), 1, 1, None, 0,
        visit_provenance(row.get("capability", "A.IDENTITY")),
        "source-family:test-retained", "episode:test-retained",
        tuple(sorted(dependencies)),
    )
    training_row = BamfTrainingRow(None, None, None, provenance)
    batch = _issue_training_batch(
        source.selection.release_sha256, generation, "a" * 64,
        provenance.capability_id, (training_row,),
    )
    return issue_training_authority(batch, source, provenance)


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class AtlasModelLearnedDependencyTests(TestCase):
    """Keep the C09 dependency witness separate from retained-model behavior tests."""

    def test_loss_execution_freezes_c09_dependencies_for_retained_motif_support(self):
        fixture = AtlasModelRetainedMotifTests(
            "test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace")
        (compiled, parameters, source, feature_schema, plan, cache,
         _spec, _extents, _manifest, slot_id) = fixture._runtime_fixture()
        authority = _training_authority(compiled, source, plan.generation_binding)
        batch = BamfCompiledBatch(
            compiled, (source,), feature_schema,
            snapshot_active_semantic_rows(
                compiled, plan.snapshot, run_id=cache.run_id,
                generation=cache.generation),
            training_authority=authority)
        execution = bamf_value_and_grad(
            parameters, batch, plan,
            (DecisionOutput("finish", ControlAction.END_FRAME),),
            {"finish": True}, cache=cache).execution
        self.assertEqual(
            tuple(read.participating_slots for read in execution.motif_reads),
            ((slot_id,), (slot_id,)),
        )
        motif_owner = bind_motif_artifact_owner(cache, compiled)
        learned = set(execution.training_authority.immediate_dependencies)
        for dependency in motif_owner.source_dependencies:
            self.assertIn(dependency, learned)
        feature = batch.atlas_feature_artifact_owner.current_node
        for dependency in feature.immediate_dependencies:
            if dependency.kind is not DependencyKind.ARTIFACT:
                self.assertIn(dependency, learned)
        for node in compiled.packed_frame_artifact_owner.require_row(compiled.compiled.rows[0]):
            for dependency in node.immediate_dependencies:
                if dependency.kind is not DependencyKind.ARTIFACT:
                    self.assertIn(dependency, learned)
