"""GUI20 consumes the accepted CP01 client without exposing its session identity."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane import ControlPlaneService
from bilqis_mlx.control_plane.tests.support import start_service
from bilqis_mlx.mission_control.electron_bridge import ElectronBridge


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


if __name__ == "__main__":
    unittest.main()
