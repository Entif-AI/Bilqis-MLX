"""Production capability-support provenance from B11, C05 acceptance and B13 custody."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.learning.atlas_candidate import (
    begin_candidate, candidate_step, resolve_candidate,
)
from bilqis_mlx.learning._retention.tests.execution_fixtures import execution_provenance
from bilqis_mlx.learning.source_atoms import SourceAtomRow
from bilqis_mlx.runtime.atlas_capability_support_owner import (
    CapabilitySupportArtifactOwner, load_capability_support_owner,
)
from bilqis_mlx.runtime.accepted_corrections import (
    _RUNTIME_OWNER, record_accepted_correction,
)
from bilqis_mlx.runtime.atlas_revalidation import apply_capability_support_correction
from bilqis_mlx.runtime.atlas_training_authority import _issue as issue_training_authority
from bilqis_mlx.runtime.atlas_training_contracts import (
    BamfDeliveryProvenance, BamfTrainingRow, _issue_training_batch,
)
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.runtime.source_execution import source_content_digest
from bilqis_mlx.runtime.bamf_bundle.admission import accept_and_publish
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    HP, NAME, candidate, parent_state, retention_decision, shape_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _ref, _result,
)
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef


TARGET = "capability:target"
SOURCE_ROW = "source:capability-support:row"
SOURCE_FAMILY = "source-family:capability-support"
EPISODE = "episode:capability-support"
SOURCE_RELEASE = "4" * 64
GENERATION = "5" * 64


def _training_authority():
    row = {"id": SOURCE_ROW, "capability": TARGET}
    provenance = BamfDeliveryProvenance(
        SOURCE_ROW, source_content_digest((row,)), "fixture-source", TARGET,
        None, (), 1, 1, None, 0,
        SOURCE_FAMILY, EPISODE)
    training_row = BamfTrainingRow(None, None, None, provenance)
    batch = _issue_training_batch(
        SOURCE_RELEASE, GENERATION, content_digest((row,)), TARGET,
        (training_row,))
    source = SourceAtomRow(
        AtlasArtifactSelection(
            "/fixture", "1" * 64, SOURCE_RELEASE, "2" * 64),
        row, {}, Path("."), 17, 1)
    return issue_training_authority(batch, source, provenance)


def _source_qualified_state():
    parent = parent_state()
    transaction = begin_candidate(parent)
    authority = _training_authority()
    spec = ModelTopologySpecV2()
    extents = GenerationExtents(
        1, 1, "a" * 64, parent.allocations.manifest.digest, "c" * 64)
    with shape_patch():
        transaction = candidate_step(
            transaction,
            {NAME: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32)},
            execution_provenance(
                transaction.parent, rows=(0,),
                candidate_step=transaction.update_steps + 1),
            HP, spec=spec, extents=extents, loss_bearing=True, max_norm=1.,
            training_authority=authority)
    return parent, transaction, resolve_candidate(transaction, accepted=True), authority


class CapabilitySupportOwnerTests(unittest.TestCase):
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

    def publish_support(self):
        parent, transaction, retained, authority = _source_qualified_state()
        bundle = candidate(retained)
        decision = retention_decision(parent=parent, retained=retained)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            published = accept_and_publish(
                self.run, bundle, retained, decision=decision,
                feature_sha256=bundle.extents.factor_map_digest,
                training_authorities=transaction.training_authorities)
        return published, authority

    def load_support(self, authority_registry=None):
        with shape_patch():
            return load_capability_support_owner(
                self.run, TARGET, authority_registry)

    def test_b13_acceptance_persists_exact_source_anchor_and_materializes_owner(self):
        published, authority = self.publish_support()
        acceptance_path = (
            self.run / "bamf-acceptance" / f"{published['manifest_sha256']}.json")
        record = json.loads(acceptance_path.read_text())
        self.assertEqual(record["source_anchors"][0][0], TARGET)
        self.assertEqual(record["source_anchors"][0][1], SOURCE_ROW)
        self.assertEqual(record["source_anchors"][0][2], authority.source_row_sha256)
        self.assertEqual(record["source_anchors"][0][8], authority.digest)

        owner = self.load_support()
        self.assertEqual(owner.support.source_anchor_ids, (SOURCE_ROW,))
        self.assertEqual(
            owner.support.retained_generation_sha256,
            published["manifest_sha256"])
        self.assertIn(
            DependencyRef(DependencyKind.SOURCE, SOURCE_ROW),
            owner.current_node.immediate_dependencies)
        self.assertIn(
            DependencyRef(
                DependencyKind.SOURCE,
                "source-proof:" + authority.digest,
            ),
            owner.current_node.immediate_dependencies)
        self.assertIn(
            DependencyRef(
                DependencyKind.RELEASE,
                "source-generation:" + GENERATION,
            ),
            owner.current_node.immediate_dependencies)
        self.assertIn(
            DependencyRef(
                DependencyKind.SOURCE,
                "training-batch:" + authority.training_batch_sha256,
            ),
            owner.current_node.immediate_dependencies)
        self.assertEqual(
            self.load_support().support,
            owner.support)
        with self.assertRaises(BilqisError):
            CapabilitySupportArtifactOwner()

    def test_source_correction_holds_read_equal_revalidation_releases_changed_requires_requalification(self):
        self.publish_support()
        owner = self.load_support()
        correction = _event(_ref(DependencyKind.SOURCE, SOURCE_ROW))
        self.assertTrue(apply_capability_support_correction(
            owner, correction, AUTHORITY))
        queue = owner.queue
        self.assertEqual(queue.held_artifact_ids, (owner.current_node.artifact_id,))
        with self.assertRaises(BilqisError):
            owner.require(TARGET)
        with self.assertRaises(BilqisError):
            self.load_support()
        reloaded = self.load_support(AUTHORITY)
        self.assertEqual(
            reloaded.queue.held_artifact_ids,
            (reloaded.current_node.artifact_id,))
        with self.assertRaises(BilqisError):
            reloaded.require(TARGET)

        node = owner.current_node
        owner.advance(
            _result(node, digest=node.content_digest, correction=correction), AUTHORITY)
        self.assertEqual(owner.require(TARGET).status, "QUALIFIED")
        with self.assertRaises(BilqisError):
            self.load_support()
        self.assertIsNone(self.load_support(AUTHORITY).queue)

        self.assertTrue(apply_capability_support_correction(
            owner, correction, AUTHORITY))
        node = owner.current_node
        owner.advance(_result(node, digest="f" * 64, correction=correction), AUTHORITY)
        self.assertEqual(owner.support.status, "REQUALIFICATION_REQUIRED")
        with self.assertRaises(BilqisError):
            owner.require(TARGET)
        self.assertEqual(
            self.load_support(AUTHORITY).support.status,
            "REQUALIFICATION_REQUIRED")

    def test_accepted_correction_stream_delivers_to_live_capability_support_owner(self):
        self.publish_support()
        owner = self.load_support(AUTHORITY)
        correction = _event(_ref(DependencyKind.SOURCE, SOURCE_ROW))
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
        self.assertEqual(
            owner.queue.held_artifact_ids,
            (owner.current_node.artifact_id,))
        with self.assertRaises(BilqisError):
            owner.require(TARGET)

        _RUNTIME_OWNER.clear()
        reloaded = self.load_support(AUTHORITY)
        self.assertEqual(
            reloaded.queue.held_artifact_ids,
            (reloaded.current_node.artifact_id,))
        with self.assertRaises(BilqisError):
            reloaded.require(TARGET)

    def test_deleting_active_hold_state_cannot_masquerade_as_clear(self):
        published, _authority = self.publish_support()
        owner = self.load_support()
        correction = _event(_ref(DependencyKind.SOURCE, SOURCE_ROW))
        self.assertTrue(apply_capability_support_correction(
            owner, correction, AUTHORITY))
        hold_dir = (
            self.run / "c09-capability-support" / published["manifest_sha256"])
        state_path = next(hold_dir.glob("*.json"))
        marker_path = state_path.with_suffix(state_path.suffix + ".seen")
        self.assertTrue(marker_path.is_file())
        state_path.unlink()
        with self.assertRaises(BilqisError):
            self.load_support(AUTHORITY)

    def test_deleting_both_local_hold_files_cannot_erase_data_plane_commitment(self):
        published, _authority = self.publish_support()
        owner = self.load_support()
        correction = _event(_ref(DependencyKind.SOURCE, SOURCE_ROW))
        self.assertTrue(apply_capability_support_correction(
            owner, correction, AUTHORITY))
        hold_dir = (
            self.run / "c09-capability-support" / published["manifest_sha256"])
        state_path = next(hold_dir.glob("*.json"))
        marker_path = state_path.with_suffix(state_path.suffix + ".seen")
        state_path.unlink()
        marker_path.unlink()
        with self.assertRaises(BilqisError):
            self.load_support(AUTHORITY)

    def test_replayed_transition_must_match_current_materialized_support_node(self):
        published, _authority = self.publish_support()
        owner = self.load_support()
        correction = _event(_ref(DependencyKind.SOURCE, SOURCE_ROW))
        self.assertTrue(apply_capability_support_correction(
            owner, correction, AUTHORITY))
        node = owner.current_node
        owner.advance(
            _result(node, digest=node.content_digest, correction=correction), AUTHORITY)
        hold_dir = (
            self.run / "c09-capability-support" / published["manifest_sha256"])
        state_path = next(hold_dir.glob("*.json"))
        record = json.loads(state_path.read_text())
        record["transition"]["previous_content_digest"] = "0" * 64
        state_path.write_text(json.dumps(record, sort_keys=True) + "\n")
        with self.assertRaises(BilqisError):
            self.load_support(AUTHORITY)


if __name__ == "__main__":
    unittest.main()
