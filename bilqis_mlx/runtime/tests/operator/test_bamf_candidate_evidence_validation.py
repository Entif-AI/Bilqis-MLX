"""Cold replay and event binding tests for BAMF candidate evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory

from bilqis_mlx.runtime.bamf_operator.evidence_parts import prepare_candidate_evidence_root
from bilqis_mlx.runtime.bamf_operator.evidence_parts.validation import (
    read_candidate_horizon_evidence, validate_candidate_horizon_event,
)
from bilqis_mlx.runtime.tests.operator.candidate_evidence_test_support import (
    CandidateEvidenceTestCase,
)


class CandidateEvidenceValidationTests(CandidateEvidenceTestCase):
    def test_crash_after_staging_durability_does_not_create_observation_credit(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_candidate_evidence_root(root)
            first = self.capture(root)
            self.deliver(first, count=2, wall_seconds=0.01)
            orphan = first.finalize(
                accepted=False, decision={"decision": "REJECTED", "reason": "fixture"})
            resumed = self.capture(root)
            self.deliver(resumed, count=2, wall_seconds=0.02)
            committed = resumed.finalize(
                accepted=False, decision={"decision": "REJECTED", "reason": "fixture"})
            self.assertEqual(orphan["attempt_id"], committed["attempt_id"])
            self.assertNotEqual(orphan["object"], committed["object"])

            event = {
                "event": "BAMF_CANDIDATE_REJECTED",
                "generation": 3,
                "student_manifest_sha256": "a" * 64,
                "evidence": {
                    "schema": "bilqis.bamf.c16.3-rejection/v2",
                    "rejection_journal_ordinal": 1,
                    "rejection_attempt_ordinal": 1,
                    "visit_id": "visit:evidence",
                    "selected_policy_key": "policy:evidence",
                    "selected_option_id": "option:evidence",
                    "capability": "capability:evidence",
                    "candidate_optimizer_step": 12,
                    "retained_optimizer_step": 10,
                    "decision": {"decision": "REJECTED", "reason": "fixture"},
                    "candidate_evidence": committed,
                },
            }
            payload = validate_candidate_horizon_event(root, event, self.release())
            self.assertEqual(payload["attempt_id"], committed["attempt_id"])
            self.assertNotEqual(
                event["evidence"]["candidate_evidence"]["object"], orphan["object"])

    def test_cold_read_rejects_tampered_horizon_bytes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_candidate_evidence_root(root)
            capture = self.capture(root)
            self.deliver(capture, count=1)
            receipt = capture.finalize(
                accepted=False, decision={"decision": "REJECTED"})
            path = root / receipt["object"]["file"]
            path.write_text("{}\n")
            with self.assertRaises(ValueError):
                read_candidate_horizon_evidence(root, receipt)

    def test_same_parent_retry_keeps_attempt_identity_until_rejection_is_durable(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_candidate_evidence_root(root)
            first = self.capture(root, candidate_attempt_ordinal=1)
            crash_retry = self.capture(root, candidate_attempt_ordinal=1)
            next_rejection = self.capture(root, candidate_attempt_ordinal=2)
        self.assertEqual(first.attempt_id, crash_retry.attempt_id)
        self.assertNotEqual(first.attempt_id, next_rejection.attempt_id)

    def test_cold_validator_binds_rejection_event_to_exact_horizon(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_candidate_evidence_root(root)
            capture = self.capture(root)
            self.deliver(capture, count=2)
            decision = {"decision": "REJECTED", "reason": "fixture"}
            receipt = capture.finalize(accepted=False, decision=decision)
            event = {
                "event": "BAMF_CANDIDATE_REJECTED",
                "generation": 3,
                "student_manifest_sha256": "a" * 64,
                "evidence": {
                    "schema": "bilqis.bamf.c16.3-rejection/v2",
                    "rejection_journal_ordinal": 1,
                    "rejection_attempt_ordinal": 1,
                    "visit_id": "visit:evidence",
                    "selected_policy_key": "policy:evidence",
                    "selected_option_id": "option:evidence",
                    "capability": "capability:evidence",
                    "candidate_optimizer_step": 12,
                    "retained_optimizer_step": 10,
                    "decision": decision,
                    "candidate_evidence": receipt,
                },
            }
            payload = validate_candidate_horizon_event(root, event, self.release())
            self.assertEqual(payload["steps"][-1]["step"], 12)
            event["evidence"]["rejection_journal_ordinal"] = 2
            with self.assertRaises(ValueError):
                validate_candidate_horizon_event(root, event, self.release())

    def test_cold_validator_binds_accepted_event_to_exact_horizon(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_candidate_evidence_root(root)
            capture = self.capture(root)
            self.deliver(capture, count=2)
            receipt = capture.finalize(
                accepted=True, decision={"decision": "ACCEPTED"})
            persistence = receipt["persistence"]
            event = {
                "event": "BAMF_C16_3_ACCEPTED",
                "optimizer_step": 12,
                "parent_generation": 3,
                "accepted_manifest_sha256": "a" * 64,
                "candidate_attempt_ordinal": 1,
                "capability": "capability:evidence",
                "visit_id": "visit:evidence",
                "selected_policy_key": "policy:evidence",
                "selected_option_id": "option:evidence",
                "resource": {
                    "optimizer_steps": 2,
                    "evidence_bytes_written": persistence["bytes_written"],
                    "evidence_file_fsyncs": persistence["file_fsyncs"],
                    "evidence_directory_fsyncs": persistence["directory_fsyncs"],
                    "evidence_objects": persistence["evidence_objects"],
                },
                "candidate_evidence": receipt,
            }
            payload = validate_candidate_horizon_event(root, event, self.release())
            self.assertTrue(payload["outcome"]["accepted"])
            event["optimizer_step"] = 13
            with self.assertRaises(ValueError):
                validate_candidate_horizon_event(root, event, self.release())
