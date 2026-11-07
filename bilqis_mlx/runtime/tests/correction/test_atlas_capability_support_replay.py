"""Durable replay and requalification for accepted capability support."""
from __future__ import annotations

import json

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_corrections import (
    _RUNTIME_OWNER, record_accepted_correction, record_accepted_revalidation,
)
from bilqis_mlx.runtime.akasha_outbox import pending_events
from bilqis_mlx.runtime.atlas_revalidation import apply_capability_support_correction
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _ref, _result,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

from .capability_support_owner_support import (
    CapabilitySupportOwnerFixture, SOURCE_ROW, TARGET,
)


class CapabilitySupportReplayTests(CapabilitySupportOwnerFixture):
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
        self.assertEqual(len(owner.ledger.pending_source_tasks), 1)
        self.assertEqual(
            owner.ledger.pending_source_tasks[0].capability_id, TARGET)
        self.assertEqual(len(owner.ledger.pending_c10_intents), 1)
        expected_ledger = owner.ledger
        with self.assertRaises(BilqisError):
            owner.require(TARGET)
        reloaded = self.load_support(AUTHORITY)
        self.assertEqual(reloaded.support.status, "REQUALIFICATION_REQUIRED")
        self.assertEqual(reloaded.ledger, expected_ledger)

    def test_accepted_correction_stream_delivers_to_live_capability_support_owner(self):
        self.publish_support()
        owner = self.load_support(AUTHORITY)
        correction = _event(_ref(DependencyKind.SOURCE, SOURCE_ROW))
        with shape_patch():
            record_accepted_correction(self.run, correction, AUTHORITY)
        self.assertEqual(
            owner.queue.held_artifact_ids, (owner.current_node.artifact_id,))
        with self.assertRaises(BilqisError):
            owner.require(TARGET)

        _RUNTIME_OWNER.clear()
        reloaded = self.load_support(AUTHORITY)
        self.assertEqual(
            reloaded.queue.held_artifact_ids,
            (reloaded.current_node.artifact_id,))
        with self.assertRaises(BilqisError):
            reloaded.require(TARGET)

        node = reloaded.current_node
        with shape_patch():
            record_accepted_revalidation(
                self.run,
                _result(node, digest="f" * 64, correction=correction),
                AUTHORITY,
            )
        self.assertEqual(reloaded.support.status, "REQUALIFICATION_REQUIRED")
        self.assertEqual(len(reloaded.ledger.pending_source_tasks), 1)
        self.assertEqual(len(reloaded.ledger.pending_c10_intents), 1)
        self.assertEqual(len(pending_events(self.run / "akasha-outbox.sqlite3")), 1)

    def test_deleting_active_hold_state_cannot_masquerade_as_clear(self):
        published, _authority = self.publish_support()
        owner = self.load_support()
        correction = _event(_ref(DependencyKind.SOURCE, SOURCE_ROW))
        self.assertTrue(apply_capability_support_correction(
            owner, correction, AUTHORITY))
        hold_dir = self.run / "c09-capability-support" / published["manifest_sha256"]
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
        hold_dir = self.run / "c09-capability-support" / published["manifest_sha256"]
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
        hold_dir = self.run / "c09-capability-support" / published["manifest_sha256"]
        state_path = next(hold_dir.glob("*.json"))
        record = json.loads(state_path.read_text())
        record["transition"]["previous_content_digest"] = "0" * 64
        state_path.write_text(json.dumps(record, sort_keys=True) + "\n")
        with self.assertRaises(BilqisError):
            self.load_support(AUTHORITY)


if __name__ == "__main__":
    import unittest
    unittest.main()
