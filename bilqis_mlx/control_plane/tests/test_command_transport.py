"""CP05 local transport and C11 adapter boundary."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control.operator import ActionReceiptState
from bilqis_mlx.control_plane import ControlPlaneClient, ControlPlaneService
from bilqis_mlx.control_plane.command.executor import C11CommandExecutor
from bilqis_mlx.control_plane.command.model import (
    CommandMode, operation_id_for,
)
from bilqis_mlx.control_plane.command.manager import CommandManager

from .command_support import DIGESTS, FakeExecutor, Launcher, request
from .support import start_service


class CommandTransportTests(unittest.TestCase):
    def test_service_client_round_trip_uses_cp05_v2_receipt(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "run"
            manager = CommandManager(
                run_dir,
                root / "commands",
                executor=FakeExecutor(run_dir, CommandMode.DRY_RUN),
                launcher=Launcher(),
            )
            service = ControlPlaneService(
                run_dir, root / "cp.sock", command_manager=manager)
            thread = start_service(service)
            try:
                with ControlPlaneClient(root / "cp.sock") as client:
                    receipt = client.submit_command(request())
                    observed = client.command_status(receipt.operation_id)
                self.assertEqual(
                    receipt.state, ActionReceiptState.COMPLETED)
                self.assertEqual(observed, receipt)
            finally:
                service.shutdown()
                thread.join(2)

    def test_returned_command_state_is_projected_into_cp04_events(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "run"
            manager = CommandManager(
                run_dir,
                root / "commands",
                executor=FakeExecutor(run_dir, CommandMode.MUTATING),
                launcher=Launcher(),
            )
            service = ControlPlaneService(
                run_dir, root / "cp.sock", command_manager=manager)
            opened = service.events.open_subscription(None)
            thread = start_service(service)
            try:
                with ControlPlaneClient(root / "cp.sock") as client:
                    receipt = client.submit_command(request(
                        action="create",
                        dry_run=False,
                        human_authorized=True,
                    ))
                event = opened.subscription.next_record(0.25)
                self.assertEqual(receipt.state, ActionReceiptState.ACCEPTED)
                self.assertEqual(event["event_family"], "operator.action.state")
                self.assertEqual(
                    event["payload_record_id"], receipt.meta.record_id)
            finally:
                opened.subscription.close()
                service.shutdown()
                thread.join(2)

    def test_default_store_is_outside_fresh_run_directory(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "run"
            service = ControlPlaneService(run_dir, root / "cp.sock")
            try:
                with self.assertRaises(ValueError):
                    service.command_store_path.relative_to(run_dir)
            finally:
                service.server_close()

    def test_service_restart_recovers_operation_by_id_without_relaunch(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "run"
            store = root / "commands"
            first_launcher = Launcher()
            first = CommandManager(
                run_dir,
                store,
                executor=FakeExecutor(run_dir, CommandMode.MUTATING),
                launcher=first_launcher,
            )
            service = ControlPlaneService(
                run_dir, root / "cp.sock", command_manager=first)
            thread = start_service(service)
            try:
                with ControlPlaneClient(root / "cp.sock") as client:
                    accepted = client.submit_command(request(
                        action="create",
                        dry_run=False,
                        human_authorized=True,
                    ))
            finally:
                service.shutdown()
                thread.join(2)

            restarted_executor = FakeExecutor(
                run_dir, CommandMode.MUTATING)
            restarted_executor.reconcile_value = {
                "kind": "authoritative-readback"}
            restarted_launcher = Launcher()
            restarted = CommandManager(
                run_dir,
                store,
                executor=restarted_executor,
                launcher=restarted_launcher,
            )
            service = ControlPlaneService(
                run_dir, root / "cp.sock", command_manager=restarted)
            thread = start_service(service)
            try:
                with ControlPlaneClient(root / "cp.sock") as client:
                    receipt = client.command_status(accepted.operation_id)
                self.assertEqual(
                    receipt.state, ActionReceiptState.COMPLETED)
                self.assertEqual(restarted_launcher.calls, [])
                self.assertEqual(len(first_launcher.calls), 1)
            finally:
                service.shutdown()
                thread.join(2)


class C11CommandAdapterTests(unittest.TestCase):
    def test_mutation_requires_explicit_human_authorization(self):
        root = Path("/tmp/cp05-adapter-fixture")
        executor = C11CommandExecutor(root)
        report = {
            "run_identity": {
                "run_id": "run-a",
                "run_seed": 1,
                "run_identity_sha256": DIGESTS[0],
                "initial_candidate_identity_sha256": DIGESTS[1],
                "factory_release_sha256": DIGESTS[2],
                "initial_source_identity": "source:a",
            },
            "model_topology": {"digest": DIGESTS[3]},
            "atlas_release_manifest": {"release_sha256": DIGESTS[4]},
        }
        with patch.object(
            executor,
            "_create_preflight",
            return_value=(
                report,
                ("train", "--dry-run", "--run-dir", str(root)),
            ),
        ):
            with self.assertRaises(BilqisError) as caught:
                executor.preflight(
                    request(action="create", dry_run=False),
                    operation_id_for("adapter-idem"),
                )
        self.assertEqual(
            caught.exception.context["reason"],
            "CONTROL_PLANE_COMMAND_HUMAN_AUTHORIZATION_REQUIRED",
        )

    def test_pause_and_stop_are_unavailable_before_runtime_action(self):
        executor = C11CommandExecutor(
            Path("/tmp/cp05-adapter-fixture"))
        for action in ("pause", "stop"):
            with self.subTest(action=action):
                with self.assertRaises(BilqisError) as caught:
                    executor.preflight(
                        request(action=action),
                        operation_id_for(f"idem-{action}"),
                    )
                self.assertEqual(
                    caught.exception.context["reason"],
                    "CONTROL_PLANE_COMMAND_ACTION_UNAVAILABLE",
                )

    def test_authorized_mutation_plan_adds_human_run_and_removes_dry_run(self):
        root = Path("/tmp/cp05-adapter-fixture")
        executor = C11CommandExecutor(root)
        report = {
            "run_identity": {
                "run_id": "run-a",
                "run_seed": 1,
                "run_identity_sha256": DIGESTS[0],
                "initial_candidate_identity_sha256": DIGESTS[1],
                "factory_release_sha256": DIGESTS[2],
                "initial_source_identity": "source:a",
            },
            "model_topology": {"digest": DIGESTS[3]},
            "atlas_release_manifest": {"release_sha256": DIGESTS[4]},
        }
        with patch.object(
            executor,
            "_create_preflight",
            return_value=(
                report,
                ("train", "--dry-run", "--run-dir", str(root)),
            ),
        ):
            plan, _ = executor.preflight(
                request(
                    action="create",
                    dry_run=False,
                    human_authorized=True,
                ),
                operation_id_for("authorized-adapter-idem"),
            )
        self.assertIn("--human-run", plan.argv)
        self.assertNotIn("--dry-run", plan.argv)


if __name__ == "__main__":
    unittest.main()
