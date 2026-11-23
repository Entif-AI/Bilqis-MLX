"""Durability and batching tests for persistent BAMF candidate evidence."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator.evidence_parts import prepare_candidate_evidence_root
from bilqis_mlx.runtime.bamf_operator.evidence_parts.validation import read_candidate_horizon_evidence
from bilqis_mlx.runtime.teacher_observation_capture import store_sidecar
from bilqis_mlx.runtime.tests.operator.candidate_evidence_test_support import (
    CandidateEvidenceTestCase,
)


class CandidateEvidencePersistenceTests(CandidateEvidenceTestCase):
    def test_evidence_root_is_durably_installed_once_before_hot_execution(self):
        with TemporaryDirectory() as temporary, patch(
                "bilqis_mlx.runtime.bamf_operator.evidence_parts.support.os.fsync",
                wraps=os.fsync) as fsync:
            root = Path(temporary)
            objects = prepare_candidate_evidence_root(root)
            self.assertTrue(objects.is_dir())
            self.assertEqual(fsync.call_count, 4)
            prepare_candidate_evidence_root(root)
            self.assertEqual(fsync.call_count, 4)

    def test_preexisting_hierarchy_is_refsynced_once_after_process_restart(self):
        from bilqis_mlx.runtime.bamf_operator.evidence_parts import support as evidence_support

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "teacher-observations" / "objects").mkdir(parents=True)
            evidence_support._PREPARED_ROOTS.discard(root)
            with patch(
                    "bilqis_mlx.runtime.bamf_operator.evidence_parts.support.os.fsync",
                    wraps=os.fsync) as fsync:
                prepare_candidate_evidence_root(root)
                self.assertEqual(fsync.call_count, 4)
                prepare_candidate_evidence_root(root)
                self.assertEqual(fsync.call_count, 4)

    def test_one_horizon_write_preserves_all_steps_and_deduplicates_rows(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_candidate_evidence_root(root)
            capture = self.capture(root)
            with patch("bilqis_mlx.runtime.state.os.fsync", wraps=os.fsync) as fsync:
                self.deliver(capture)
                self.assertEqual(fsync.call_count, 0)
                receipt = capture.finalize(
                    accepted=False,
                    decision={"decision": "REJECTED", "reason": "fixture"})
                self.assertEqual(fsync.call_count, 2)
            self.assertEqual(receipt["persistence"]["file_fsyncs"], 1)
            self.assertEqual(receipt["persistence"]["directory_fsyncs"], 1)
            self.assertGreater(receipt["persistence"]["bytes_written"], 0)
            self.assertEqual(receipt["persistence"]["delivery_records"], 16)

            payload = read_candidate_horizon_evidence(root, receipt)
            self.assertEqual(len(payload["steps"]), 16)
            self.assertEqual(len(payload["source_objects"]), 1)
            row_digest = next(iter(payload["source_objects"]))
            self.assertTrue(all(
                [position["row"] for position in step["positions"]]
                == [row_digest, row_digest]
                for step in payload["steps"]))
            self.assertTrue(all(
                step["delivered_teaching"]["provider_id"] == "provider:evidence"
                for step in payload["steps"]))
            self.assertFalse(payload["outcome"]["accepted"])
            self.assertEqual(payload["outcome"]["decision"]["reason"], "fixture")

    def test_mid_install_failure_leaves_no_declared_horizon_object(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_candidate_evidence_root(root)
            capture = self.capture(root)
            self.deliver(capture, count=2)
            with patch(
                    "bilqis_mlx.runtime.state.os.link",
                    side_effect=OSError("simulated crash after file fsync")):
                with self.assertRaises(OSError):
                    capture.finalize(
                        accepted=False, decision={"decision": "REJECTED"})
            self.assertEqual(list(root.glob("teacher-observations/objects/*.json")), [])
            self.assertEqual(list(root.glob("teacher-observations/objects/*.tmp")), [])

    def test_replay_of_already_durable_horizon_is_idempotent_and_cold_readable(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_candidate_evidence_root(root)
            first = self.capture(root)
            self.deliver(first, count=4)
            first_receipt = first.finalize(
                accepted=True, decision={"decision": "ACCEPTED"})
            replay = self.capture(root)
            self.deliver(replay, count=4)
            with patch("bilqis_mlx.runtime.state.os.fsync", wraps=os.fsync) as fsync:
                replay_receipt = replay.finalize(
                    accepted=True, decision={"decision": "ACCEPTED"})
            self.assertEqual(fsync.call_count, 0)
            self.assertEqual(replay_receipt["object"], first_receipt["object"])
            self.assertEqual(replay_receipt["persistence"]["bytes_written"], 0)
            self.assertEqual(replay_receipt["persistence"]["file_fsyncs"], 0)
            self.assertEqual(replay_receipt["persistence"]["directory_fsyncs"], 0)
            self.assertEqual(
                read_candidate_horizon_evidence(root, replay_receipt)["steps"],
                read_candidate_horizon_evidence(root, first_receipt)["steps"])

    def test_disposable_fsync_latency_fixture_favors_one_horizon_write(self):
        real_fsync = os.fsync

        def delayed_fsync(fd):
            time.sleep(0.002)
            return real_fsync(fd)

        with TemporaryDirectory() as legacy_tmp, TemporaryDirectory() as batch_tmp:
            legacy_root = Path(legacy_tmp)
            batch_root = Path(batch_tmp)
            prepare_candidate_evidence_root(legacy_root)
            prepare_candidate_evidence_root(batch_root)
            with patch("bilqis_mlx.runtime.state.os.fsync", side_effect=delayed_fsync):
                started = time.perf_counter()
                for ordinal in range(1, 17):
                    store_sidecar(legacy_root, {
                        "schema": "legacy-per-step-fixture", "step": ordinal,
                        "row": {"id": "row:one", "tokens": [1, 2, 3]},
                    })
                legacy_seconds = time.perf_counter() - started
                capture = self.capture(batch_root)
                self.deliver(capture)
                started = time.perf_counter()
                receipt = capture.finalize(
                    accepted=False, decision={"decision": "REJECTED"})
                batch_seconds = time.perf_counter() - started

        self.assertEqual(receipt["persistence"]["file_fsyncs"], 1)
        self.assertEqual(receipt["persistence"]["directory_fsyncs"], 1)
        self.assertLess(batch_seconds, legacy_seconds / 2)
