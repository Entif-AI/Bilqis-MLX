"""Portable reconstruction integrity and event publication."""
import json
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane.native_contracts import materialized_at, run_ref
from bilqis_mlx.control_plane.native_source import (
    authenticated_history, materialize_current_native_projection,
    materialize_native_projection, native_query_catalog, native_query_source, refresh_native_events,
)
from bilqis_mlx.mission_control import (
    CandidateDecision, CapabilitySnapshot, LearningEpisode, OperatorView, ResourceSample, TeacherSnapshot,
)
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryMode, QueryRequest
from bilqis_mlx.runtime.bamf_bundle import record_bamf_rejection
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import retention_decision
from ...observed import test_source as observed_support

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.control_plane import ControlPlaneClient, ControlPlaneService, EventFamily
from ...support import start_service


from ..native_source_support import NativeSourceFixture


class NativeBamfProjectionTests(NativeSourceFixture, unittest.TestCase):
    def test_historical_acceptance_tamper_fails_closed(self):
            self.parent()
            source, _pointer = self.publish_successor()
            index = self.root / "tampered.sqlite3"
            projection = MissionControlProjection.rebuild_from_bamf(index, self.run)
            before = projection.catalog().query(QueryRequest(
                QueryFamily.CAPABILITY, run_id=source.run_id))
            history = authenticated_history(self.run)
            parent = history[0]
            acceptance = self.run / "bamf-acceptance" / f"{parent.manifest_sha256}.json"
            raw = acceptance.read_text(encoding="utf-8")
            acceptance.write_text(raw.replace('"generation":0', '"generation":9'), encoding="utf-8")
            with self.assertRaises(BilqisError) as caught:
                MissionControlProjection.rebuild_from_bamf(index, self.run)
            self.assertEqual(
                caught.exception.context.get("reason"),
                "CONTROL_PLANE_NATIVE_HISTORY_ACCEPTANCE_DRIFT",
            )
            self.assertEqual(
                MissionControlProjection(index).catalog().query(QueryRequest(
                    QueryFamily.CAPABILITY, run_id=source.run_id)),
                before,
            )

    def test_cp06_rebuild_combines_authenticated_history_with_current_semantic_authority(self):
            self.parent()
            source, _pointer = self.publish_successor()
            index = self.root / "artifact-only.sqlite3"
            projection = MissionControlProjection.rebuild_from_bamf(index, self.run)
            catalog = projection.catalog()
            current = catalog.query(QueryRequest(
                QueryFamily.CAPABILITY, run_id=source.run_id))
            semantic = catalog.query(QueryRequest(
                QueryFamily.SEMANTIC, run_id=source.run_id))
            self.assertEqual(current.records[0].capability_id, "A.NATIVE")
            self.assertGreater(len(semantic.records), 0)

    def test_subscription_automatically_publishes_new_authenticated_native_events(self):
            self.parent()
            socket = self.root / "native.sock"
            service = ControlPlaneService(
                self.run, socket, event_heartbeat_seconds=0.01,
                event_retention_limit=16, event_queue_limit=16,
            )
            thread = start_service(service)
            try:
                with ControlPlaneClient(socket) as client:
                    subscription = client.subscribe_events()
                    self.publish_successor()
                    observed = []
                    while len(observed) < 5:
                        event = next(subscription)
                        if event.schema_version.endswith("event-envelope/v1"):
                            observed.append(event)
                    families = {event.event_family for event in observed}
                    self.assertTrue({
                        EventFamily.RUN_STATE_CHANGED.value,
                        EventFamily.LESSON_VISIT_COMPLETED.value,
                        EventFamily.CANDIDATE_RETAINED.value,
                        EventFamily.CAPABILITY_CHANGED.value,
                        EventFamily.RESOURCE_HEALTH_SAMPLE.value,
                    } <= families)
                    ids = [event.event_id for event in observed]
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertEqual(refresh_native_events(service), ())
            finally:
                service.shutdown()
                thread.join(2)
