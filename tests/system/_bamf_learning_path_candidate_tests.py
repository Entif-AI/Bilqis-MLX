"""C13.1 candidate-accounting and cold-restart unit contracts."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.bamf.c13 import delivery_runtime
from scripts.bamf.c13.contracts import CandidateAttemptReceipt


class BamfLearningPathCandidateAccountingTests(unittest.TestCase):
    @staticmethod
    def student(generation, step):
        return SimpleNamespace(
            generation=generation,
            retained_state=SimpleNamespace(optimizer_step=step),
        )

    def test_owner_candidate_acceptance_must_advance_generation_and_optimizer(self):
        parent, current = self.student(0, 0), self.student(1, 1)
        result = SimpleNamespace(status="VISIT_LIMIT", visits=1, accepted=1, rejected=0)
        with patch.object(
                delivery_runtime, "load_accepted_generation",
                side_effect=(parent, current)), patch.object(
                delivery_runtime, "operate_bamf", return_value=result) as operate, patch.object(
                delivery_runtime, "_identity", side_effect=("1" * 64, "2" * 64)), patch.object(
                delivery_runtime, "event_offset", return_value=10), patch.object(
                delivery_runtime, "owner_event_after",
                return_value=("BAMF_C16_3_ACCEPTED", "a" * 64)):
            receipt = delivery_runtime.attempt_owner_candidate(Path("/tmp/disposable"))
        self.assertEqual(receipt.outcome, "ACCEPTED")
        self.assertEqual(receipt.attempted_steps, 1)
        self.assertEqual((receipt.current_generation, receipt.current_optimizer_step), (1, 1))
        self.assertEqual(receipt.owner_event, "BAMF_C16_3_ACCEPTED")
        self.assertEqual(receipt.owner_evidence_sha256, "a" * 64)
        self.assertEqual(operate.call_args.kwargs["reserve_gib"], 100.0)

    def test_owner_candidate_rejection_and_hold_preserve_accepted_parent(self):
        cases = (
            (SimpleNamespace(status="REJECTED_HOLD", visits=1, accepted=0, rejected=1),
             "REJECTED", 1),
            (SimpleNamespace(status="PRIORITY_HOLD", visits=0, accepted=0, rejected=0),
             "HELD", 0),
        )
        for result, expected, attempted in cases:
            with self.subTest(outcome=expected):
                parent, current = self.student(3, 7), self.student(3, 7)
                with patch.object(
                        delivery_runtime, "load_accepted_generation",
                        side_effect=(parent, current)), patch.object(
                        delivery_runtime, "operate_bamf", return_value=result), patch.object(
                        delivery_runtime, "_identity", side_effect=("3" * 64, "3" * 64)), patch.object(
                        delivery_runtime, "event_offset", return_value=10), patch.object(
                        delivery_runtime, "owner_event_after", return_value=(
                            ("BAMF_CANDIDATE_REJECTED", "b" * 64)
                            if expected == "REJECTED" else (None, None))):
                    receipt = delivery_runtime.attempt_owner_candidate(Path("/tmp/disposable"))
                self.assertEqual(receipt.outcome, expected)
                self.assertEqual(receipt.attempted_steps, attempted)

    def test_candidate_loop_stops_at_first_rejection_after_acceptance(self):
        accepted = CandidateAttemptReceipt(
            "ACCEPTED", 0, 1, 0, 1, "1" * 64, "2" * 64, 1)
        rejected = CandidateAttemptReceipt(
            "REJECTED", 1, 1, 1, 1, "2" * 64, "2" * 64, 1)
        with patch.object(
                delivery_runtime, "attempt_owner_candidate",
                side_effect=(accepted, rejected, AssertionError("must stop"))):
            attempts = delivery_runtime.run_candidate_attempts(Path("/tmp/disposable"), 64)
        self.assertEqual(attempts, (accepted, rejected))

    def test_cold_restart_identity_uses_fresh_process_and_preserves_full_candidate_digest(self):
        parent = self.student(4, 9)
        with patch.object(
                delivery_runtime, "load_accepted_generation", return_value=parent), patch.object(
                delivery_runtime, "_identity", return_value="7" * 64), patch.object(
                delivery_runtime.subprocess, "run") as run:
            run.return_value = SimpleNamespace(
                returncode=0, stderr="",
                stdout=json.dumps({
                    "generation": 4,
                    "optimizer_step": 9,
                    "candidate_identity_sha256": "7" * 64,
                }) + "\n")
            receipt = delivery_runtime.cold_restart_identity(Path("/tmp/disposable"))
        self.assertEqual(receipt["candidate_identity_sha256"], "7" * 64)
        self.assertIn("-c", run.call_args.args[0])


__all__ = ("BamfLearningPathCandidateAccountingTests",)
