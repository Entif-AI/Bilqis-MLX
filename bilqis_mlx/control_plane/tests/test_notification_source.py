"""Issue #307 durable C10/Akasha notification-source acceptance."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.control_plane.notifications import (
    notification_from_native_event, notification_from_semantic_release_change,
    sync_akasha_notifications,
)
from bilqis_mlx.control_plane.native_contracts import AuthenticatedGeneration
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
            run_scoped = projection.catalog().query(QueryRequest(
                QueryFamily.NOTIFICATION, run_id="live-run", limit=32)).records
            self.assertEqual(run_scoped, records)
            self.assertEqual(
                {record.kind.value for record in records},
                {"GRADUATION", "GRAPH_MATERIALIZATION", "BLOCKER", "DRIFT", "GATE_TRANSITION", "FAILURE"},
            )
            graduation = next(record for record in records if record.kind.value == "GRADUATION")
            self.assertEqual(graduation.evidence_ref, "b" * 64)

    @staticmethod
    def _generation(semantic_release, *, manifest="a", acceptance="b", generation=1):
        return AuthenticatedGeneration(
            manifest_sha256=manifest * 64,
            acceptance_sha256=acceptance * 64,
            manifest={
                "run_id": "run:fixture", "generation": generation,
                "provenance": {"release_digest": semantic_release * 64},
                "topology": {"digest": "d" * 64},
            },
            acceptance={
                "candidate_identity_sha256": "e" * 64,
                "factory_release_sha256": "f" * 64,
            },
            run_identity={"run_identity_sha256": "1" * 64},
            correction_frontier={}, teacher_state={}, outbox=(),
        )

    def test_accepted_lineage_projects_semantic_release_change(self):
        parent = self._generation("2", manifest="a", acceptance="b", generation=1)
        current = self._generation("3", manifest="4", acceptance="5", generation=2)
        notice = notification_from_semantic_release_change(
            current, parent, projected_at=777)
        self.assertIsNotNone(notice)
        self.assertEqual(notice.kind.value, "SEMANTIC_RELEASE")
        self.assertEqual(notice.subject_ref, "semantic-release:" + "3" * 64)
        self.assertEqual(notice.created_at, 777)
        unchanged = self._generation("2", manifest="6", acceptance="7", generation=2)
        self.assertIsNone(notification_from_semantic_release_change(
            unchanged, parent, projected_at=778))

    def test_accepted_append_grade_event_projects_real_promotion_notice(self):
        generation = AuthenticatedGeneration(
            manifest_sha256="a" * 64,
            acceptance_sha256="b" * 64,
            manifest={
                "run_id": "run:fixture", "generation": 1,
                "provenance": {"release_digest": "c" * 64},
                "topology": {"digest": "d" * 64},
            },
            acceptance={
                "candidate_identity_sha256": "e" * 64,
                "factory_release_sha256": "f" * 64,
            },
            run_identity={"run_identity_sha256": "1" * 64},
            correction_frontier={}, teacher_state={}, outbox=(),
        )
        event = {
            "event": "SCHOOL_EXECUTION_PROFILE_ADOPTED",
            "event_id": "promotion-event-1",
            "transition_kind": "APPEND_GRADE",
            "grade": "B",
            "factory_release_sha256": "f" * 64,
        }
        notification = notification_from_native_event(
            generation, event, projected_at=888)
        self.assertIsNotNone(notification)
        self.assertEqual(notification.kind.value, "PROMOTION")
        self.assertEqual(notification.subject_ref, "grade:B")
        self.assertEqual(notification.evidence_ref, "factory-release:" + "f" * 64)
        self.assertEqual(notification.created_at, 888)


if __name__ == "__main__":
    unittest.main()
