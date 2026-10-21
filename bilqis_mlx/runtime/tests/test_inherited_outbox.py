"""Outbox receipts belong to their immutable generation, never its successor."""
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import tempfile
import unittest

from bilqis_mlx.trainer import (
    _advance, _reconcile_delivery_outbox, _with_delivery_outbox,
)
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

    def test_uncommitted_successor_cannot_publish_inherited_outbox(self):
        journal = self._publish()
        before = journal.read_bytes()
        with self.assertRaisesRegex(ValueError, "UNCOMMITTED_SOURCE"):
            _advance(self.root, self.current, _School(), persist=False)
        self.assertEqual(journal.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
