"""Behavioral acceptance for the standalone local CP01 service."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.control_plane import (
    ControlPlaneClient,
    ControlPlaneService,
    ControlPlaneState,
    PROTOCOL_VERSION,
)
from bilqis_mlx.control_plane.discovery import discover_learner
from bilqis_mlx.presentation.operator_cli.tests.bamf_lifecycle.create_resume_support import (
    BamfCreateResumeCase,
    TOPOLOGY,
)
from bilqis_mlx.runtime.bamf_operator.locking import bamf_operator_lock


def _start(service: ControlPlaneService) -> Thread:
    thread = Thread(target=service.serve_forever, daemon=True)
    thread.start()
    return thread


class ControlPlaneTransportTests(unittest.TestCase):
    def test_cp01_state_vocabulary_is_distinct_and_complete(self):
        self.assertEqual(
            [item.value for item in ControlPlaneState],
            [
                "connecting", "healthy", "degraded", "incompatible-version",
                "unauthorized", "learner-unavailable", "service-restarting",
                "stale", "disconnected",
            ])

    def test_handshake_precedes_health_and_version_mismatch_fails_closed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = root / "cp.sock"
            service = ControlPlaneService(root / "missing-run", socket_path)
            thread = _start(service)
            raw = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            raw.connect(str(socket_path))
            stream = raw.makefile("rwb")
            stream.write(b'{"type":"health"}\n')
            stream.flush()
            rejected = json.loads(stream.readline())
            self.assertEqual(rejected["state"], "connecting")
            self.assertEqual(rejected["reason"], "CONTROL_PLANE_HANDSHAKE_REQUIRED")
            stream.close()
            raw.close()

            wrong = ControlPlaneClient(
                socket_path, protocol_version="bilqis.bamf.control-plane/v0")
            response = wrong.connect()
            self.assertFalse(response["accepted"])
            self.assertEqual(response["state"], "incompatible-version")
            self.assertEqual(response["protocol_version"], PROTOCOL_VERSION)
            service.shutdown()
            thread.join(2)

    def test_health_distinguishes_live_service_from_unavailable_learner(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = root / "cp.sock"
            service = ControlPlaneService(root / "missing-run", socket_path)
            thread = _start(service)
            with ControlPlaneClient(socket_path, client_id="electron-fixture") as client:
                handshake = client.request("health")
                self.assertEqual(handshake["service_state"], "healthy")
                self.assertTrue(handshake["service_live"])
                self.assertTrue(handshake["service_ready"])
                self.assertFalse(handshake["learner_ready"])
                self.assertEqual(
                    handshake["learner"]["state"], "learner-unavailable")
                self.assertEqual(handshake["state"], "learner-unavailable")
            self.assertEqual(
                os.stat(socket_path).st_mode & 0o777, 0o600)
            service.shutdown()
            thread.join(2)

    def test_transport_is_unix_only_and_occupied_path_fails_typed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = root / "cp.sock"
            service = ControlPlaneService(root / "missing-run", socket_path)
            self.assertEqual(service._server.socket.family, socket.AF_UNIX)
            service.server_close()

            socket_path.write_text("not-a-socket", encoding="utf-8")
            with self.assertRaises(BilqisError) as caught:
                ControlPlaneService(root / "missing-run", socket_path)
            self.assertEqual(
                caught.exception.code, "SCHOOL.BAMF_CONTROL_PLANE.INVALID")
            self.assertEqual(
                caught.exception.context["reason"],
                "CONTROL_PLANE_SOCKET_PATH_OCCUPIED")

    def test_disconnected_client_failure_uses_typed_error_control_plane(self):
        with TemporaryDirectory() as temporary:
            client = ControlPlaneClient(Path(temporary) / "missing.sock")
            with self.assertRaises(BilqisError) as caught:
                client.request("health")
        self.assertEqual(
            caught.exception.code, "SCHOOL.BAMF_CONTROL_PLANE.INVALID")
        self.assertEqual(
            caught.exception.context["reason"],
            "CONTROL_PLANE_CLIENT_DISCONNECTED")

    def test_client_classifies_permission_and_restart_transport_states(self):
        with TemporaryDirectory() as temporary:
            socket_path = Path(temporary) / "cp.sock"
            unauthorized = ControlPlaneClient(socket_path)
            with patch("socket.socket.connect", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    unauthorized.connect()
            self.assertEqual(
                unauthorized.state, ControlPlaneState.UNAUTHORIZED)

            restarting = ControlPlaneClient(socket_path)
            with patch(
                    "socket.socket.connect",
                    side_effect=ConnectionRefusedError):
                with self.assertRaises(ConnectionRefusedError):
                    restarting.connect()
            self.assertEqual(
                restarting.state, ControlPlaneState.SERVICE_RESTARTING)

    def test_discovery_distinguishes_stale_from_degraded_learner_state(self):
        with TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            run_dir.mkdir()
            (run_dir / "bamf-state.json").write_text("{}", encoding="utf-8")
            with patch(
                    "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                    side_effect=FileNotFoundError):
                stale = discover_learner(run_dir)
            with patch(
                    "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                    side_effect=ValueError("invalid fixture")):
                degraded = discover_learner(run_dir)
        self.assertEqual(stale.state, ControlPlaneState.STALE)
        self.assertEqual(degraded.state, ControlPlaneState.DEGRADED)

    def test_direct_python_entrypoint_starts_without_gui(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = root / "entry.sock"
            process = subprocess.Popen(
                [
                    sys.executable, "-m", "bilqis_mlx.control_plane",
                    "--run-dir", str(root / "missing-run"),
                    "--socket", str(socket_path),
                ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                deadline = time.monotonic() + 3
                while not socket_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(socket_path.exists())
                with ControlPlaneClient(socket_path, client_id="cli-fixture") as client:
                    self.assertEqual(client.state, ControlPlaneState.LEARNER_UNAVAILABLE)
                    self.assertEqual(
                        client.request("liveness")["service_state"], "healthy")
            finally:
                process.send_signal(signal.SIGINT)
                process.wait(timeout=3)
            self.assertEqual(process.returncode, 0)


class ControlPlaneLearnerIntegrationTests(BamfCreateResumeCase):
    def _create_disposable_generation_zero(self) -> Path:
        target = self.root / "created-bamf"
        manifest = self.root / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        with self.foundation_create_context():
            code, _output, errors = self.invoke([
                "--human-run", "--model-topology", str(TOPOLOGY),
                "--atlas-release-manifest", str(manifest),
                "--run-dir", str(target), *self.FOUNDATION_ARGS,
            ])
        self.assertEqual((code, errors), (0, ""))
        return target

    def test_restart_rediscovers_same_generation_without_mutating_learner(self):
        target = self._create_disposable_generation_zero()
        pointer = target / "bamf-state.json"
        before = pointer.read_bytes()
        socket_path = self.root / "cp.sock"
        with self.accepted_read_context():
            first = ControlPlaneService(target, socket_path)
            first_thread = _start(first)
            with ControlPlaneClient(socket_path, client_id="electron-fixture") as client:
                first_handshake = client.request("health")
            first_service_id = first_handshake["service"]["service_id"]
            first_learner = first_handshake["learner"]
            first.shutdown()
            first_thread.join(2)

            second = ControlPlaneService(target, socket_path)
            second_thread = _start(second)
            with ControlPlaneClient(socket_path, client_id="electron-fixture") as client:
                second_handshake = client.request("health")
            second.shutdown()
            second_thread.join(2)

        self.assertNotEqual(
            first_service_id, second_handshake["service"]["service_id"])
        self.assertEqual(first_learner, second_handshake["learner"])
        self.assertEqual(first_learner["run_id"], "operator-first-student")
        self.assertEqual(first_learner["generation"], 0)
        self.assertEqual(pointer.read_bytes(), before)

    def test_client_disconnect_leaves_disposable_operator_owner_running(self):
        target = self._create_disposable_generation_zero()
        pointer = target / "bamf-state.json"
        before = pointer.read_bytes()
        socket_path = self.root / "cp.sock"
        locked, release = Event(), Event()

        def learner_owner():
            with bamf_operator_lock(target):
                locked.set()
                release.wait(3)

        owner = Thread(target=learner_owner, daemon=True)
        owner.start()
        self.assertTrue(locked.wait(1))
        with self.accepted_read_context():
            service = ControlPlaneService(target, socket_path)
            service_thread = _start(service)
            client = ControlPlaneClient(socket_path, client_id="crash-fixture")
            client.connect()
            client.close()
            self.assertTrue(owner.is_alive())
            self.assertEqual(pointer.read_bytes(), before)
            service.shutdown()
            service_thread.join(2)
        release.set()
        owner.join(2)
        self.assertFalse(owner.is_alive())


if __name__ == "__main__":
    unittest.main()
