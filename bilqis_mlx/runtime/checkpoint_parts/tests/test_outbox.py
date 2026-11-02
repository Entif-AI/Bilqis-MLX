"""Outbox receipts belong to their immutable generation, never its successor."""
from dataclasses import asdict, dataclass
from copy import deepcopy
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.trainer import (
    _advance, _observed_outbox_events, _reconcile_delivery_outbox,
    _with_delivery_outbox,
)
from bilqis_mlx.data_plane import close_data_planes
from bilqis_mlx.factory.tests.support import synthetic_release_inputs
from bilqis_mlx.factory.release import (
    admit_factory_release, compile_factory_release,
)
from bilqis_mlx.runtime.admission import _persist_factory_release


@dataclass(frozen=True)
class _School:
    marker: str = "no-neural-change"


class InheritedOutboxTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.previous_data_plane = os.environ.get("BILQIS_DATA_PLANE")
        os.environ["BILQIS_DATA_PLANE"] = str(self.root / "plane.sqlite3")
        close_data_planes()
        self.addCleanup(self._restore_data_plane)
        (self.root / "states").mkdir()
        self.event = {"event": "SCHOOL_TEACHER_VISIT_COMMITTED",
                      "generation": 7, "optimizer_step": 9}
        course, registry = synthetic_release_inputs()
        release = compile_factory_release(course, registry)
        v1_path = _persist_factory_release(self.root, release)
        v1_admission = admit_factory_release(
            release, student_sha256="a" * 64, optimizer_step=9,
            semantic_graph_sha256="d" * 64)
        self.previous = _with_delivery_outbox({
            "generation": 7, "run_id": "test-prometheus",
            "school": {"course_digest": release.course.digest(),
                       "current_student": {"sha256": "a" * 64,
                                           "optimizer_step": 9}},
            "model_bundle": "bundles/working-seven",
            "source_manifest_sha256": "b" * 64,
            "teacher_source_sha256": "c" * 64,
            "semantic_graph_sha256": "d" * 64,
            "curriculum_mode": course.version,
            "factory_release_sha256": release.release_sha256,
            "factory_release_file": v1_path,
            "factory_admission": asdict(v1_admission),
            "factory_admission_v2": None,
        }, (self.event,))
        self.current = {
            **self.previous, "generation": 8,
            "school": {**self.previous["school"], "course_digest": "e" * 64},
            "factory_release_sha256": "e" * 64,
            "factory_release_file": "factory-releases/" + "e" * 64 + ".json",
            "factory_release_schema": "bilqis.mlx.factory-release/v2",
            "factory_admission_v2": {
                "factory_release_sha256": "e" * 64,
                "student_sha256": "a" * 64, "optimizer_step": 9,
                "semantic_graph_sha256": "d" * 64,
            },
        }
        (self.root / "states" / "0000007.json").write_text(
            json.dumps(self.previous))

    def _restore_data_plane(self):
        close_data_planes()
        if self.previous_data_plane is None:
            os.environ.pop("BILQIS_DATA_PLANE", None)
        else:
            os.environ["BILQIS_DATA_PLANE"] = self.previous_data_plane

    def _publish(self):
        journal = self.root / "events.jsonl"
        journal.write_text(json.dumps(self.previous["delivery_outbox"][0]) + "\n")
        return journal

    def test_readonly_inherited_receipts_recover_only_when_published(self):
        journal = self._publish()
        before = journal.read_bytes()
        self.assertTrue(_reconcile_delivery_outbox(self.root, self.current))
        self.assertEqual(journal.read_bytes(), before)
        self.assertEqual(self.current["delivery_outbox"],
                         self.previous["delivery_outbox"])

    def test_inherited_receipt_requires_complete_original_journal(self):
        with self.assertRaises(ValueError):
            _reconcile_delivery_outbox(self.root, self.current)

    def test_inherited_receipt_rejects_duplicate_published_event(self):
        journal = self._publish()
        with journal.open("a") as output:
            output.write(json.dumps(self.previous["delivery_outbox"][0]) + "\n")
        with self.assertRaises(ValueError):
            _reconcile_delivery_outbox(self.root, self.current)

    def test_warmed_outbox_lookup_does_not_json_decode_full_ledger_again(self):
        self._publish()
        event = self.previous["delivery_outbox"][0]
        expected = {event["event_id"]: event}
        observed, counts = _observed_outbox_events(self.root, expected)
        self.assertEqual(observed, set(expected))
        self.assertEqual(counts[event["event_id"]], 1)

        with patch(
                "bilqis_mlx.trainer.json.loads",
                side_effect=AssertionError("full ledger decode")):
            observed, counts = _observed_outbox_events(self.root, expected)

        self.assertEqual(observed, set(expected))
        self.assertEqual(counts[event["event_id"]], 1)

    def test_preflight_reads_without_publishing_unwritten_normal_receipts(self):
        self.assertFalse((self.root / "events.jsonl").exists())
        self.assertFalse(_reconcile_delivery_outbox(
            self.root, self.previous, publish_missing=False))
        self.assertFalse((self.root / "events.jsonl").exists())

    def test_inherited_receipt_cannot_claim_a_different_predecessor(self):
        self._publish()
        changed = {**self.current, "school": {"current_student": {
            "sha256": "f" * 64, "optimizer_step": 9}}}
        with self.assertRaises(ValueError):
            _reconcile_delivery_outbox(self.root, changed)

    def test_advancing_reconciles_prior_intent_instead_of_copying_old_receipt(self):
        journal = self._publish()
        before = journal.read_bytes()
        (self.root / "states" / "0000008.json").write_text(
            json.dumps(self.current))
        next_record = _advance(self.root, self.current, _School(), persist=False)
        self.assertEqual(next_record["generation"], 9)
        self.assertNotIn("delivery_outbox", next_record)
        self.assertEqual(journal.read_bytes(), before)

    def test_advancing_ordinary_outbox_does_not_rehydrate_full_generation(self):
        ordinary = _with_delivery_outbox(
            {key: value for key, value in self.current.items()
             if key != "delivery_outbox"},
            ({"event": "SCHOOL_TEACHER_VISIT_COMMITTED",
              "generation": 8, "optimizer_step": 9},),
        )
        (self.root / "states" / "0000008.json").write_text(
            json.dumps(ordinary))
        with patch(
                "bilqis_mlx.state_dag.read_generation",
                side_effect=AssertionError("full generation read")):
            next_record = _advance(self.root, ordinary, _School(), persist=False)
        self.assertEqual(next_record["generation"], 9)

    def test_advancing_transient_governance_edit_uses_committed_outbox_source(self):
        journal = self._publish()
        original_bytes = journal.read_bytes()
        (self.root / "states" / "0000008.json").write_text(
            json.dumps(self.current))
        # Resume legitimately repairs governance *before* advancing. That
        # proposed record must not be mistaken for the immutable event owner.
        edited = {**self.current, "championship_checkpoint_origin_ambiguities": {
            "test-origin": ["A", "B"]}}
        successor = _advance(self.root, edited, _School(), persist=False)
        self.assertEqual(successor["generation"], 9)
        self.assertEqual(successor["championship_checkpoint_origin_ambiguities"],
                         edited["championship_checkpoint_origin_ambiguities"])
        self.assertNotIn("delivery_outbox", successor)
        self.assertEqual(journal.read_bytes(), original_bytes)

    def test_advance_discards_mutated_transient_payload_but_keeps_signed_receipts(self):
        journal = self._publish()
        original_journal = journal.read_bytes()
        path = self.root / "states" / "0000008.json"
        path.write_text(json.dumps(self.current))
        original_state = path.read_bytes()
        proposed = deepcopy(self.current)
        proposed["delivery_outbox"][0]["optimizer_step"] = 888

        # The event_id still points to the immutable committed event; this
        # transient payload is never authority to republish or inherit it.
        next_record = _advance(self.root, proposed, _School(), persist=False)
        self.assertEqual(next_record["generation"], 9)
        self.assertNotIn("delivery_outbox", next_record)
        self.assertEqual(journal.read_bytes(), original_journal)
        self.assertEqual(path.read_bytes(), original_state)

    def test_advance_does_not_discard_unrecognized_transient_event_id(self):
        self._publish()
        (self.root / "states" / "0000008.json").write_text(
            json.dumps(self.current))
        proposed = deepcopy(self.current)
        proposed["delivery_outbox"][0]["event_id"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "OUTBOX_ADVANCE_SOURCE_DRIFT"):
            _advance(self.root, proposed, _School(), persist=False)

    def test_advance_rejects_drifted_durable_student_identity(self):
        self._publish()
        (self.root / "states" / "0000008.json").write_text(
            json.dumps(self.current))
        proposed = deepcopy(self.current)
        proposed["school"]["current_student"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "OUTBOX_ADVANCE_SOURCE_DRIFT"):
            _advance(self.root, proposed, _School(), persist=False)

    def test_uncommitted_successor_cannot_publish_inherited_outbox(self):
        journal = self._publish()
        before = journal.read_bytes()
        with self.assertRaisesRegex(ValueError, "UNCOMMITTED_SOURCE"):
            _advance(self.root, self.current, _School(), persist=False)
        self.assertEqual(journal.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
