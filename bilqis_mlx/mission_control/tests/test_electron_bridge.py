"""GUI20 consumes the accepted CP01 client without exposing its session identity."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.control_plane import ControlPlaneService
from bilqis_mlx.control_plane.__main__ import _default_socket
from bilqis_mlx.control_plane.contracts import ControlPlaneState
from bilqis_mlx.control_plane.tests.support import start_service
from bilqis_mlx.mission_control.electron_bridge import ElectronBridge, _socket_path
from bilqis_mlx.paths import active_run_dir


class ElectronBridgeTests(unittest.TestCase):
    def test_real_cp01_handshake_and_health_are_sanitized_for_electron_main(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            socket_path = root / "cp.sock"
            service = ControlPlaneService(root / "missing-run", socket_path)
            thread = start_service(service)
            try:
                with patch.dict(os.environ, {"BILQIS_CONTROL_PLANE_SOCKET": str(socket_path)}):
                    bridge = ElectronBridge()
                    connected = bridge.connect()
                    status = bridge.status()
                    disconnected = bridge.disconnect()
            finally:
                service.shutdown()
                thread.join(2)

        self.assertEqual(connected["protocolVersion"], "bilqis.bamf.control-plane/v1")
        self.assertEqual(connected["state"], "learner-unavailable")
        self.assertTrue(connected["serviceLive"])
        self.assertTrue(connected["serviceReady"])
        self.assertFalse(connected["learnerReady"])
        self.assertFalse(connected["learnerActive"])
        self.assertEqual(status["state"], "learner-unavailable")
        self.assertTrue(status["serviceLive"])
        self.assertEqual(disconnected["state"], "disconnected")
        serialized = repr((connected, status, disconnected))
        self.assertNotIn(str(socket_path), serialized)
        self.assertNotIn(str(root / "missing-run"), serialized)
        self.assertNotIn("session_id", serialized)
        self.assertNotIn("service_id", serialized)

    def test_permission_failure_preserves_cp01_unauthorized_state(self):
        client = Mock()
        client.state = ControlPlaneState.UNAUTHORIZED
        client.connect.side_effect = PermissionError("private socket")
        bridge = ElectronBridge()
        with patch(
            "bilqis_mlx.mission_control.electron_bridge.ControlPlaneClient",
            return_value=client,
        ):
            status = bridge.connect()

        self.assertEqual(status["state"], "unauthorized")
        self.assertFalse(status["serviceLive"])
        self.assertNotIn("private socket", repr(status))
        client.close.assert_called_once_with(preserve_state=True)

    def test_default_socket_path_matches_accepted_cp01_locator(self):
        with patch.dict(os.environ, {"BILQIS_CONTROL_PLANE_SOCKET": ""}):
            self.assertEqual(_socket_path(), _default_socket(active_run_dir()))


if __name__ == "__main__":
    unittest.main()
