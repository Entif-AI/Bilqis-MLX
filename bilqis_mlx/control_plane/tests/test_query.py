"""CP03 query transport over the accepted CP01 local service boundary."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane import ControlPlaneClient, ControlPlaneService
from bilqis_mlx.control_plane.contracts import ERROR_SCHEMA
from bilqis_mlx.mission_control.query_contracts import (
    QUERY_PAGE_SCHEMA, QueryFamily, QueryRequest, QueryState,
)
from bilqis_mlx.mission_control.query_catalog import MissionControlQueryCatalog
from bilqis_mlx.mission_control.tests.samples import SAMPLES

from .support import start_service


class ControlPlaneQueryTests(unittest.TestCase):
    def test_query_round_trip_uses_cp02_records_without_health_side_effect(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "run"
            run_dir.mkdir()
            sentinel = run_dir / "checkpoint.marker"
            sentinel.write_bytes(b"immutable-checkpoint")
            before = {
                path.name: path.read_bytes()
                for path in run_dir.iterdir() if path.is_file()
            }
            service = ControlPlaneService(
                run_dir, root / "cp.sock",
                query_source=lambda: MissionControlQueryCatalog(SAMPLES[:16]),
            )
            thread = start_service(service)
            try:
                with ControlPlaneClient(root / "cp.sock") as client:
                    previous_state = client.state
                    with patch(
                            "bilqis_mlx.control_plane.service.discover_learner",
                            side_effect=AssertionError(
                                "query called learner discovery")):
                        page = client.query(QueryRequest(QueryFamily.RUN))
                    self.assertEqual(client.state, previous_state)
                self.assertEqual(page["schema"], QUERY_PAGE_SCHEMA)
                self.assertTrue(page["accepted"])
                self.assertEqual(page["state"], QueryState.PRESENT.value)
                self.assertEqual(
                    page["request"], QueryRequest(QueryFamily.RUN).to_record())
                self.assertEqual(
                    {row["schema_version"] for row in page["records"]},
                    {
                        "bilqis.bamf.mission-control.run-context/v1",
                        "bilqis.bamf.mission-control.operator-view/v1",
                    },
                )
                after = {
                    path.name: path.read_bytes()
                    for path in run_dir.iterdir() if path.is_file()
                }
                self.assertEqual(after, before)
            finally:
                service.shutdown()
                thread.join(2)

    def test_query_source_is_re_evaluated_for_each_current_request(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = [SAMPLES[1]]

            def source():
                return MissionControlQueryCatalog(tuple(records))

            service = ControlPlaneService(
                root / "missing-run", root / "cp.sock", query_source=source)
            thread = start_service(service)
            try:
                with ControlPlaneClient(root / "cp.sock") as client:
                    first = client.query(QueryRequest(QueryFamily.RUN))
                    records[:] = [SAMPLES[0], SAMPLES[1]]
                    second = client.query(QueryRequest(QueryFamily.RUN))
                self.assertEqual(first["total_matches"], 1)
                self.assertEqual(second["total_matches"], 2)
            finally:
                service.shutdown()
                thread.join(2)

    def test_default_service_reports_query_source_unavailable_not_empty(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = ControlPlaneService(root / "missing-run", root / "cp.sock")
            thread = start_service(service)
            try:
                with ControlPlaneClient(root / "cp.sock") as client:
                    page = client.query(QueryRequest(QueryFamily.CAPABILITY))
                self.assertEqual(page["state"], QueryState.UNAVAILABLE.value)
                self.assertEqual(page["records"], [])
            finally:
                service.shutdown()
                thread.join(2)

    def test_malformed_query_is_transport_error_not_health_envelope(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = ControlPlaneService(root / "missing-run", root / "cp.sock")
            thread = start_service(service)
            try:
                with ControlPlaneClient(root / "cp.sock") as client:
                    response = client._send({
                        "type": "query",
                        "query": {"schema": "wrong"},
                    })
                self.assertEqual(response["schema"], ERROR_SCHEMA)
                self.assertFalse(response["accepted"])
                self.assertEqual(
                    response["reason"], "CONTROL_PLANE_QUERY_INVALID")
                self.assertNotIn("state", response)
            finally:
                service.shutdown()
                thread.join(2)


if __name__ == "__main__":
    unittest.main()
