"""Issue #307 control-plane persistence and restart integration."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.control_plane import ControlPlaneClient, ControlPlaneService, EventFamily
from bilqis_mlx.mission_control import MissionControlQueryCatalog
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryRequest
from bilqis_mlx.mission_control.tests.samples import SAMPLES

from .support import start_service


class NotificationFeedIntegrationTests(unittest.TestCase):
    def test_service_persists_notification_across_restart_without_source_mutation(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "run"
            run.mkdir()
            socket = root / "cp.sock"
            projection = MissionControlProjection.create_empty(root / "notifications.sqlite3")
            source_record = replace(
                SAMPLES[5],
                meta=replace(SAMPLES[5].meta, record_id="capability:A.IDENTITY", materialized_at=200),
            )

            def query_source():
                return MissionControlQueryCatalog((*SAMPLES[:16], *projection.notifications()))

            service = ControlPlaneService(
                run, socket, query_source=query_source,
                notification_projection=projection,
            )
            thread = start_service(service)
            try:
                emitted = service.publish_event(
                    EventFamily.WARNING_FAILURE, source_record,
                    event_id="failure:A.IDENTITY:1")
                self.assertIsNotNone(emitted)
                with ControlPlaneClient(socket) as client:
                    page = client.query(QueryRequest(QueryFamily.NOTIFICATION))
                self.assertEqual(page["state"], "PRESENT")
                self.assertEqual(len(page["records"]), 1)
                self.assertEqual(page["records"][0]["kind"], "FAILURE")
                self.assertEqual(page["records"][0]["evidence_ref"], "evidence:a")
            finally:
                service.shutdown()
                thread.join(2)

            restarted = ControlPlaneService(
                run, socket, query_source=query_source,
                notification_projection=MissionControlProjection(projection.path),
            )
            restart_thread = start_service(restarted)
            try:
                next_source = replace(
                    source_record,
                    meta=replace(source_record.meta, materialized_at=210, observed_at=209),
                )
                second = restarted.publish_event(
                    EventFamily.WARNING_FAILURE, next_source,
                    event_id="failure:A.IDENTITY:2")
                self.assertIsNotNone(second)
                with ControlPlaneClient(socket) as client:
                    page = client.query(QueryRequest(QueryFamily.NOTIFICATION))
                self.assertEqual(len(page["records"]), 2)
                active = [item for item in page["records"] if item["state"] == "ACTIVE"]
                superseded = [item for item in page["records"] if item["state"] == "SUPERSEDED"]
                self.assertEqual(len(active), 1)
                self.assertEqual(len(superseded), 1)
                self.assertEqual(active[0]["source_event_id"], second.event_id)
                self.assertEqual(
                    active[0]["supersedes_notification_id"],
                    superseded[0]["notification_id"],
                )
            finally:
                restarted.shutdown()
                restart_thread.join(2)

            source_revisions = MissionControlProjection(projection.path).revisions(
                source_record.meta.record_id)
            self.assertEqual(source_revisions, (source_record, next_source))


if __name__ == "__main__":
    unittest.main()
