"""Accepted observation does not depend on eligibility to resume training."""
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane.command.executor import C11CommandExecutor
from bilqis_mlx.control_plane.command.model import CommandMode, operation_id_for
from bilqis_mlx.control_plane.tests.command_support import request
from bilqis_mlx.errors import BilqisError
from .native_source_support import NativeSourceFixture


class ReadOnlyCommandTests(NativeSourceFixture, unittest.TestCase):
    def test_status_and_checkpoint_inspect_without_resume_or_recovery(self):
        self.parent()
        pointer = self.run / "bamf-state.json"
        before = pointer.read_bytes()
        executor = C11CommandExecutor(self.run)
        with patch.object(executor, "_resume_preflight",
                          side_effect=AssertionError("read-only called resume")):
            for action in ("status", "checkpoint-verify"):
                with self.subTest(action=action):
                    command = request(action=action, dry_run=False)
                    plan, report = executor.preflight(command, operation_id_for(action))
                    self.assertEqual(plan.mode, CommandMode.READ_ONLY)
                    self.assertFalse(plan.requires_worker)
                    self.assertIsNone(report["c11_report"]["ready_for_training"])
                    self.assertEqual(plan.target.generation, 0)
                    self.assertEqual(plan.target.generation_manifest_sha256,
                                     self._parent_pointer["manifest_sha256"])
                    proof = executor.inert_postcondition(plan, report)
                    self.assertEqual(proof["inspection"]["generation_manifest_sha256"],
                                     self._parent_pointer["manifest_sha256"])
                    self.assertEqual(proof["target"], plan.target.to_record())
        self.assertEqual(pointer.read_bytes(), before)

    def test_read_only_receipt_cannot_claim_a_different_generation(self):
        self.parent()
        executor = C11CommandExecutor(self.run)
        plan, report = executor.preflight(
            request(action="status", dry_run=False), operation_id_for("status"))
        self.publish_successor()
        with self.assertRaises(BilqisError) as caught:
            executor.inert_postcondition(plan, report)
        self.assertEqual(caught.exception.context["reason"],
                         "CONTROL_PLANE_COMMAND_TARGET_DRIFT")
