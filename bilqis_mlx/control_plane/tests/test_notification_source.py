"""Issue #307 durable C10/Akasha notification-source acceptance."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.control_plane.notifications import sync_akasha_notifications
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryRequest
from bilqis_mlx.runtime.akasha_outbox import (
    AkashaEvent, AkashaEventKind, append_outbox,
)


class NotificationSourceTests(unittest.TestCase):
    def _event(self, kind, payload, *, subject="subject:fixture", time=100):
        return AkashaEvent.from_payload(
            kind=kind,
            subject_id=subject,
            source_receipt_sha256="9" * 64,
            payload=payload,
            source_time=time,
            effective_time=time + 1,
            observed_at=time + 2,
            recorded_at=time + 3,
        )

    def test_c10_graduation_materialization_blocker_drift_and_failure_project(self):
        with TemporaryDirectory() as temporary:
            run = Path(temporary)
            outbox = run / "akasha-outbox.sqlite3"
            projection = MissionControlProjection.create_empty(run / "notifications.sqlite3")
            events = (
                self._event(AkashaEventKind.CAPABILITY_GRADUATION, {
                    "capability_id": "B.EXAMPLE",
                    "generation_sha256": "a" * 64,
                    "assessment_receipt_sha256": "b" * 64,
                }, subject="capability:B.EXAMPLE"),
                self._event(AkashaEventKind.MATERIALIZATION, {
                    "graph": "fixture-graph", "owner": "fixture-owner",
                    "canonical_rdf_sha256": "1" * 64,
                    "materialization_receipt_sha256": "2" * 64,
                    "projection_version": "1.0.0", "coverage_status": "complete",
                    "semantic_coverage_sha256": "3" * 64,
                    "importer_implementation_sha256": "4" * 64,
                    "smoke_suite_sha256": "5" * 64,
                }, subject="graph:fixture", time=110),
                self._event(AkashaEventKind.REQUALIFICATION, {
                    "capability_id": "B.EXAMPLE",
                    "retained_generation_sha256": "c" * 64,
                    "status": "REQUALIFICATION_REQUIRED",
                }, subject="capability:B.EXAMPLE", time=120),
                self._event(AkashaEventKind.REVALIDATION, {
                    "artifact_id": "artifact:1", "old_digest": "d" * 64,
                    "new_digest": "e" * 64, "eligible": False,
                }, subject="artifact:1", time=130),
                self._event(AkashaEventKind.REVALIDATION, {
                    "artifact_id": "artifact:2", "old_digest": "f" * 64,
                    "new_digest": "0" * 64, "eligible": True,
                }, subject="artifact:2", time=135),
                self._event(AkashaEventKind.PROCESS_FAULT, {
                    "fault_id": "fault:1", "original_source_event_id": "event:1",
                    "correction_event_id": "correction:1", "remediation_id": "remediation:1",
                    "derived_path": ["artifact:1"],
                }, subject="fault:1", time=140),
            )
            for event in events:
                self.assertTrue(append_outbox(outbox, event))

            self.assertEqual(sync_akasha_notifications(run, projection), len(events))
            self.assertEqual(sync_akasha_notifications(run, projection), len(events))
            records = projection.catalog().query(
                QueryRequest(QueryFamily.NOTIFICATION, limit=32)).records
            self.assertEqual(len(records), len(events))
            self.assertEqual(
                {record.kind.value for record in records},
                {"GRADUATION", "GRAPH_MATERIALIZATION", "BLOCKER", "DRIFT", "GATE_TRANSITION", "FAILURE"},
            )
            graduation = next(record for record in records if record.kind.value == "GRADUATION")
            self.assertEqual(graduation.evidence_ref, "b" * 64)

    def test_c10_event_without_an_explicit_time_does_not_invent_creation_time(self):
        with TemporaryDirectory() as temporary:
            run = Path(temporary)
            projection = MissionControlProjection.create_empty(run / "notifications.sqlite3")
            # Accepted owner-generated factory-release events may intentionally
            # lack source-owned clocks. They cannot become a timestamped notice.
            self.assertEqual(sync_akasha_notifications(run, projection), 0)
            self.assertEqual(projection.notifications(), ())


if __name__ == "__main__":
    unittest.main()
