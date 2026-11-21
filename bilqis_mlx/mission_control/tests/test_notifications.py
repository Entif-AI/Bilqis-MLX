"""Issue #307 persistent Mission Control notification projection acceptance."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.control_plane.event_stream import EventFamily, EventStreamBroker
from bilqis_mlx.mission_control.notifications import NotificationState
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryRequest
from bilqis_mlx.mission_control.tests.samples import SAMPLES


class NotificationProjectionTests(unittest.TestCase):
    def _projection(self, temporary):
        return MissionControlProjection.create_empty(Path(temporary) / "projection.sqlite3")

    @staticmethod
    def _event(broker, family, payload, event_id):
        base = broker.publish_record(
            EventFamily.WARNING_FAILURE, payload, event_id=event_id)
        return replace(base, event_family=family)

    def test_required_milestone_families_project_with_evidence(self):
        with TemporaryDirectory() as temporary:
            projection = self._projection(temporary)
            broker = EventStreamBroker(stream_id="mission-control", epoch_id="epoch-a")
            families = (
                "capability.graduated",
                "grade.promoted",
                "semantic.release.changed",
                "graph.materialized",
                "qualification.gate.changed",
                "blocker.changed",
                "drift.detected",
                "warning.failure",
            )
            for index, family in enumerate(families):
                payload = replace(
                    SAMPLES[5],
                    meta=replace(
                        SAMPLES[5].meta,
                        record_id=f"subject:{index}",
                        materialized_at=200 + index,
                        observed_at=190 + index,
                    ),
                )
                event = self._event(broker, family, payload, f"event:{index}")
                projection.ingest_event(event, payload)

            page = projection.catalog().query(QueryRequest(QueryFamily.NOTIFICATION, limit=32))
            self.assertEqual(len(page.records), len(families))
            self.assertTrue(all(item.meta.evidence_refs for item in page.records))
            self.assertTrue(all(item.meta.authority.value == "DERIVED" for item in page.records))

    def test_duplicate_restart_acknowledgement_and_supersession_are_durable(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "projection.sqlite3"
            projection = MissionControlProjection.create_empty(path)
            broker = EventStreamBroker(stream_id="mission-control", epoch_id="epoch-a")
            payload = replace(
                SAMPLES[5], meta=replace(SAMPLES[5].meta, record_id="grade:A", materialized_at=200))
            first = self._event(
                broker, "capability.graduated", payload, "graduation:A:1")
            projection.ingest_event(first, payload)
            projection.ingest_event(first, payload)

            restarted = MissionControlProjection(path)
            records = restarted.catalog().query(
                QueryRequest(QueryFamily.NOTIFICATION, limit=32)).records
            self.assertEqual(len(records), 1)
            first_notice = records[0]
            self.assertIs(first_notice.state, NotificationState.ACTIVE)

            acknowledged = restarted.acknowledge_notification(
                first_notice.notification_id, acknowledged_at=201)
            self.assertIs(acknowledged.state, NotificationState.ACKNOWLEDGED)
            self.assertEqual(restarted.revisions(first_notice.notification_id)[-1], acknowledged)
            self.assertIs(
                restarted.revisions(first.meta.record_id)[0].__class__, first.__class__)

            payload2 = replace(payload, meta=replace(payload.meta, materialized_at=210))
            second = self._event(
                broker, "capability.graduated", payload2, "graduation:A:2")
            restarted.ingest_event(second, payload2)
            notices = restarted.catalog().query(
                QueryRequest(QueryFamily.NOTIFICATION, limit=32)).records
            active = [item for item in notices if item.state is NotificationState.ACTIVE]
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].source_event_id, second.event_id)

            payload3 = replace(payload2, meta=replace(payload2.meta, materialized_at=220))
            third = self._event(
                broker, "capability.graduated", payload3, "graduation:A:3")
            restarted.ingest_event(third, payload3)
            newest = restarted.catalog().query(
                QueryRequest(QueryFamily.NOTIFICATION, limit=32)).records
            active = [item for item in newest if item.state is NotificationState.ACTIVE]
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0].source_event_id, third.event_id)
            self.assertIsNotNone(active[0].supersedes_notification_id)

    def test_missing_explicit_evidence_never_becomes_celebratory(self):
        with TemporaryDirectory() as temporary:
            projection = self._projection(temporary)
            broker = EventStreamBroker(stream_id="mission-control", epoch_id="epoch-a")
            payload = replace(
                SAMPLES[5],
                meta=replace(
                    SAMPLES[5].meta,
                    record_id="release:missing-evidence",
                    materialized_at=200,
                    evidence_refs=(),
                    receipt_refs=(),
                ),
            )
            event = self._event(
                broker, "semantic.release.changed", payload, "release:missing-evidence")
            projection.ingest_event(event, payload)
            page = projection.catalog().query(QueryRequest(QueryFamily.NOTIFICATION, limit=32))
            self.assertEqual(page.records, ())


if __name__ == "__main__":
    unittest.main()
