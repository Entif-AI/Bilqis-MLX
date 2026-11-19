"""CP05 admission and idempotency behavior."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError, ErrorBus, SCHOOL
from bilqis_mlx.mission_control.operator import (
    ActionParameter, ActionReceiptState,
)
from bilqis_mlx.control_plane.command.model import CommandMode
from bilqis_mlx.control_plane.command.manager import CommandManager

from ..command_support import FakeExecutor, Launcher, meta, request


class CommandLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run_dir = self.root / "run"
        self.store_root = self.root / "commands"

    def tearDown(self):
        self.temporary.cleanup()

    def manager(self, mode=CommandMode.DRY_RUN):
        executor = FakeExecutor(self.run_dir, mode)
        launcher = Launcher()
        return (
            CommandManager(
                self.run_dir,
                self.store_root,
                executor=executor,
                launcher=launcher,
            ),
            executor,
            launcher,
        )

    def test_dry_run_is_terminal_deterministic_and_never_launches_worker(self):
        manager, executor, launcher = self.manager()
        first = manager.submit(request())
        retry = manager.submit(request(
            request_id="request-2", requested_at=101))

        self.assertEqual(first.state, ActionReceiptState.COMPLETED)
        self.assertEqual(retry, first)
        self.assertEqual(executor.preflight_calls, 1)
        self.assertEqual(launcher.calls, [])
        self.assertIsNotNone(first.postcondition_ref)
        self.assertEqual(
            manager.store.read_accepted(first.operation_id).state,
            ActionReceiptState.ACCEPTED,
        )

    def test_idempotency_conflict_rejects_without_repeating_effect(self):
        manager, _executor, launcher = self.manager()
        original = manager.submit(request())
        conflict = manager.submit(request(
            request_id="request-conflict",
            parameters=(ActionParameter("minutes", 9),),
        ))

        self.assertEqual(original.state, ActionReceiptState.COMPLETED)
        self.assertEqual(conflict.state, ActionReceiptState.REJECTED)
        self.assertEqual(conflict.operation_id, original.operation_id)
        self.assertEqual(launcher.calls, [])

    def test_request_id_cannot_be_rebound_to_a_different_operation(self):
        manager, _executor, _launcher = self.manager()
        manager.submit(request())
        conflict = manager.submit(request(
            idempotency_key="different-idem",
            parameters=(ActionParameter("minutes", 3),),
        ))
        self.assertEqual(conflict.state, ActionReceiptState.REJECTED)

    def test_same_mutating_identity_never_launches_twice_after_lost_ack(self):
        manager, _executor, launcher = self.manager(CommandMode.MUTATING)
        action = request(
            action="create", dry_run=False, human_authorized=True)
        first = manager.submit(action)
        retry = manager.submit(replace(
            action,
            meta=meta("request:retry", 101),
            request_id="request-retry",
            requested_at=101,
        ))

        self.assertEqual(first.state, ActionReceiptState.ACCEPTED)
        self.assertEqual(retry.state, ActionReceiptState.OUTCOME_UNKNOWN)
        self.assertEqual(len(launcher.calls), 1)

    def test_restart_reconciles_by_readback_without_relaunch(self):
        manager, _executor, launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        restarted_executor = FakeExecutor(
            self.run_dir, CommandMode.MUTATING)
        restarted_executor.reconcile_value = {
            "kind": "authoritative-readback"}
        restarted_launcher = Launcher()
        restarted = CommandManager(
            self.run_dir,
            self.store_root,
            executor=restarted_executor,
            launcher=restarted_launcher,
        )

        terminal = restarted.status(accepted.operation_id)
        self.assertEqual(terminal.state, ActionReceiptState.COMPLETED)
        self.assertEqual(restarted_launcher.calls, [])
        self.assertEqual(len(launcher.calls), 1)

    def test_late_authoritative_no_effect_proof_terminalizes_without_relaunch(self):
        manager, executor, launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        manager.store.write_worker_result(
            accepted.operation_id,
            returncode=None,
            error_ref="command-error:custody:" + "1" * 64,
            finished_at=102,
        )
        executor.reconcile_no_effect_value = {
            "kind": "reconciled-no-effect",
            "before": executor.preflight(request(), accepted.operation_id)[0].target.to_record(),
        }

        terminal = manager.status(accepted.operation_id)

        self.assertEqual(terminal.state, ActionReceiptState.FAILED_BEFORE_EFFECT)
        self.assertEqual(len(launcher.calls), 1)
        self.assertIsNotNone(manager.store.read_reconciliation(accepted.operation_id))

    def test_permanently_unresolvable_operation_remains_unknown_and_never_relaunches(self):
        manager, _executor, launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        manager.store.write_worker_result(
            accepted.operation_id,
            returncode=7,
            error_ref="command-error:7:" + "1" * 64,
            finished_at=102,
        )

        first = manager.status(accepted.operation_id)
        second = manager.status(accepted.operation_id)

        self.assertEqual(first.state, ActionReceiptState.OUTCOME_UNKNOWN)
        self.assertEqual(second.state, ActionReceiptState.OUTCOME_UNKNOWN)
        self.assertIsNone(manager.store.read_terminal(accepted.operation_id))
        self.assertEqual(len(launcher.calls), 1)

    def test_stale_trainer_identity_does_not_block_late_completion_proof(self):
        manager, executor, _launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        manager.store.write_trainer_process(
            accepted.operation_id, pid=43210, identity_sha256="9" * 64)
        executor.trainer_process_state_value = "inactive"
        executor.reconcile_value = {"kind": "authoritative-readback"}

        completed = manager.status(accepted.operation_id)

        self.assertEqual(completed.state, ActionReceiptState.COMPLETED)

    def test_unknown_outcome_quarantines_new_same_learner_mutation(self):
        manager, _executor, launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        manager.store.write_worker_result(
            accepted.operation_id,
            returncode=7,
            error_ref="command-error:7:" + "1" * 64,
            finished_at=102,
        )

        blocked = manager.submit(request(
            request_id="request-2",
            idempotency_key="idem-2",
            action="create",
            dry_run=False,
            human_authorized=True,
            requested_at=103,
        ))

        self.assertEqual(blocked.state, ActionReceiptState.REJECTED)
        self.assertEqual(len(launcher.calls), 1)
        self.assertIsNone(manager.store.read_dispatch(blocked.operation_id))

    def test_pending_same_learner_mutation_is_quarantined_before_ambiguity(self):
        executor = FakeExecutor(self.run_dir, CommandMode.MUTATING)
        launcher = Launcher(pid=os.getpid())
        manager = CommandManager(
            self.run_dir, self.store_root, executor=executor, launcher=launcher)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        self.assertEqual(
            manager.status(accepted.operation_id).state,
            ActionReceiptState.PENDING,
        )

        blocked = manager.submit(request(
            request_id="request-2",
            idempotency_key="idem-2",
            action="create",
            dry_run=False,
            human_authorized=True,
            requested_at=103,
        ))

        self.assertEqual(blocked.state, ActionReceiptState.REJECTED)
        self.assertEqual(len(launcher.calls), 1)
        self.assertIsNone(manager.store.read_dispatch(blocked.operation_id))

    def test_unknown_outcome_still_allows_read_only_reconciliation_surfaces(self):
        manager, executor, launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        manager.store.write_worker_result(
            accepted.operation_id,
            returncode=7,
            error_ref="command-error:7:" + "1" * 64,
            finished_at=102,
        )
        self.assertEqual(
            manager.status(accepted.operation_id).state,
            ActionReceiptState.OUTCOME_UNKNOWN,
        )

        executor.mode = CommandMode.DRY_RUN
        read_only = manager.submit(request(
            request_id="request-status",
            idempotency_key="idem-status",
            action="status",
            dry_run=True,
            requested_at=103,
        ))

        self.assertEqual(read_only.state, ActionReceiptState.COMPLETED)
        self.assertEqual(len(launcher.calls), 1)

    def test_unknown_outcome_does_not_blanket_block_stop_boundary(self):
        manager, executor, launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        manager.store.write_trainer_process(
            accepted.operation_id, pid=43210, identity_sha256="9" * 64)
        executor.trainer_process_state_value = "current"
        self.assertEqual(
            manager.status(accepted.operation_id).state,
            ActionReceiptState.OUTCOME_UNKNOWN,
        )

        stop = manager.submit(request(
            request_id="request-stop",
            idempotency_key="idem-stop",
            action="stop",
            parameters=(ActionParameter("operation_id", accepted.operation_id),),
            dry_run=False,
            human_authorized=True,
            requested_at=103,
        ))

        self.assertEqual(stop.state, ActionReceiptState.ACCEPTED)
        self.assertEqual(len(launcher.calls), 2)

    def test_unknown_outcome_stop_must_name_the_blocking_operation(self):
        manager, executor, launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        manager.store.write_trainer_process(
            accepted.operation_id, pid=43210, identity_sha256="9" * 64)
        executor.trainer_process_state_value = "current"

        blocked = manager.submit(request(
            request_id="request-stop-wrong",
            idempotency_key="idem-stop-wrong",
            action="stop",
            parameters=(ActionParameter(
                "operation_id", "operation:" + "a" * 64),),
            dry_run=False,
            human_authorized=True,
            requested_at=103,
        ))

        self.assertEqual(blocked.state, ActionReceiptState.REJECTED)
        self.assertEqual(len(launcher.calls), 1)

    def test_live_worker_or_current_trainer_never_reconciles_to_terminal(self):
        manager, executor, _launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        with (
            patch(
                "bilqis_mlx.control_plane.command.status.pid_live",
                return_value=True,
            ),
            patch.object(
                executor, "reconcile",
                side_effect=AssertionError("live operation must not reconcile"),
            ),
        ):
            pending = manager.status(accepted.operation_id)
        self.assertEqual(pending.state, ActionReceiptState.PENDING)
        self.assertIsNone(manager.store.read_terminal(accepted.operation_id))

        manager.store.write_trainer_process(
            accepted.operation_id, pid=43210, identity_sha256="9" * 64)
        executor.trainer_process_state_value = "current"

    def test_unknown_process_identity_keeps_operation_unresolved(self):
        manager, executor, _launcher = self.manager(CommandMode.MUTATING)
        accepted = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))
        manager.store.write_trainer_process(
            accepted.operation_id, pid=43210, identity_sha256="9" * 64)
        executor.trainer_process_state_value = "unknown"
        executor.reconcile_value = {"kind": "authoritative-readback"}

        receipt = manager.status(accepted.operation_id)

        self.assertEqual(receipt.state, ActionReceiptState.OUTCOME_UNKNOWN)
        self.assertIsNone(manager.store.read_terminal(accepted.operation_id))
        with (
            patch(
                "bilqis_mlx.control_plane.command.status.pid_live",
                return_value=False,
            ),
            patch.object(
                executor, "reconcile",
                side_effect=AssertionError("recorded trainer must not reconcile"),
            ),
        ):
            unknown = manager.status(accepted.operation_id)
        self.assertEqual(unknown.state, ActionReceiptState.OUTCOME_UNKNOWN)
        self.assertIsNone(manager.store.read_terminal(accepted.operation_id))

    def test_target_conflict_rejects_before_dispatch(self):
        manager, executor, launcher = self.manager(CommandMode.MUTATING)
        try:
            ErrorBus.raise_(
                SCHOOL.BAMF_CONTROL_PLANE.INVALID,
                reason="CONTROL_PLANE_COMMAND_TARGET_CONFLICT",
            )
        except BilqisError as error:
            executor.preflight_error = error
        receipt = manager.submit(request(
            action="create", dry_run=False, human_authorized=True))

        self.assertEqual(receipt.state, ActionReceiptState.REJECTED)
        self.assertEqual(launcher.calls, [])
        self.assertIsNone(manager.store.read_dispatch(receipt.operation_id))

    def test_expected_preview_target_blocks_stale_authorization_before_dispatch(self):
        manager, executor, launcher = self.manager(CommandMode.MUTATING)
        action = request(action="create", dry_run=False, human_authorized=True)
        stale = "command-target:" + "f" * 64
        receipt = manager.submit(action, expected_target_ref=stale)

        self.assertEqual(receipt.state, ActionReceiptState.REJECTED)
        self.assertEqual(executor.preflight_calls, 1)
        self.assertEqual(launcher.calls, [])
        self.assertIsNone(manager.store.read_dispatch(receipt.operation_id))
        self.assertNotEqual(receipt.target_ref, stale)

    def test_matching_preview_target_preserves_existing_single_dispatch_semantics(self):
        manager, executor, launcher = self.manager(CommandMode.MUTATING)
        action = request(action="create", dry_run=False, human_authorized=True)
        plan, _ = executor.preview(action, "operation:" + "a" * 64)
        executor.preflight_calls = 0
        receipt = manager.submit(action, expected_target_ref=plan.target.ref)

        self.assertEqual(receipt.state, ActionReceiptState.ACCEPTED)
        self.assertEqual(executor.preflight_calls, 1)
        self.assertEqual(len(launcher.calls), 1)


if __name__ == "__main__":
    unittest.main()
