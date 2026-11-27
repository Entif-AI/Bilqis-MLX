"""Notification composition follows the source frontier, not query frequency."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane.notifications.query_source import composed_query_source
from bilqis_mlx.mission_control import (
    MissionControlQueryCatalog, QueryFamily, QueryMode, QueryRequest,
)
from bilqis_mlx.mission_control.contracts.notifications import (
    Notification, NotificationState,
)
from bilqis_mlx.mission_control.projection import MissionControlProjection
from bilqis_mlx.mission_control.tests.samples import SAMPLES


MODULE = "bilqis_mlx.control_plane.notifications.query_source"


class NotificationQuerySourceTests(unittest.TestCase):
    def test_frontier_reuse_preserves_acknowledgments_and_query_identity(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            projection = MissionControlProjection.create_empty(root / "notices.sqlite3")
            notice = next(item for item in SAMPLES if type(item) is Notification)
            projection.ingest_notification(notice)
            accepted = MissionControlQueryCatalog((SAMPLES[0],))
            history = ("accepted",)
            seen = []

            def snapshot(request):
                seen.append(request)
                return accepted, history

            material = object()
            native = SimpleNamespace(_native_snapshot=snapshot, _native_material=material)
            request = QueryRequest(QueryFamily.RUN, mode=QueryMode.HISTORICAL,
                                   run_id="run", generation=7)
            with (
                patch(f"{MODULE}.native_query_source", return_value=native),
                patch(f"{MODULE}.sync_akasha_notifications") as akasha,
                patch(f"{MODULE}.sync_native_transition_notifications") as transitions,
            ):
                source = composed_query_source(root, projection)
                first = source(request)
                self.assertIs(source(request), first)
                self.assertEqual(seen, [request, request])
                self.assertIs(source._native_material, material)
                self.assertTrue(source._bilqis_query_aware)
                akasha.assert_called_once_with(root, projection)
                transitions.assert_called_once_with(root, projection, history=history)

                # An observation-only refresh must not reimport accepted evidence.
                accepted = MissionControlQueryCatalog((SAMPLES[1],))
                second = source(request)
                self.assertIn(SAMPLES[1], second.records)
                self.assertNotIn(SAMPLES[0], second.records)
                self.assertEqual(akasha.call_count, 1)
                self.assertEqual(transitions.call_count, 1)

                projection.acknowledge_notification(
                    notice.notification_id, acknowledged_at=notice.created_at + 10)
                acknowledged = source(request).query(QueryRequest(QueryFamily.NOTIFICATION))
                self.assertEqual(acknowledged.records[0].state, NotificationState.ACKNOWLEDGED)
                self.assertEqual(transitions.call_count, 1)

                (root / "akasha-outbox.sqlite3-wal").write_bytes(b"new event")
                source(request)
                self.assertEqual(akasha.call_count, 2)
                self.assertEqual(transitions.call_count, 1)
                history = (*history, "advanced")
                accepted = MissionControlQueryCatalog((SAMPLES[0], SAMPLES[1]))
                advanced = source(request)
                self.assertEqual(transitions.call_count, 2)
                transitions.assert_called_with(root, projection, history=history)
                self.assertIn(SAMPLES[0], advanced.records)
                self.assertEqual(advanced.query(QueryRequest(
                    QueryFamily.NOTIFICATION)).records[0].state, NotificationState.ACKNOWLEDGED)

    def test_unavailable_native_source_is_not_replaced_by_notification_data(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            projection = MissionControlProjection.create_empty(root / "notices.sqlite3")
            unavailable = MissionControlQueryCatalog.unavailable()
            native = SimpleNamespace(
                _native_snapshot=lambda _query: (unavailable, ()), _native_material=None)
            with (
                patch(f"{MODULE}.native_query_source", return_value=native),
                patch(f"{MODULE}.sync_akasha_notifications") as akasha,
                patch(f"{MODULE}.sync_native_transition_notifications") as transitions,
            ):
                self.assertIs(composed_query_source(root, projection)(), unavailable)
                akasha.assert_not_called()
                transitions.assert_not_called()
