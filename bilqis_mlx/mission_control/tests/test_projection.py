"""CP06 disposable projection, revision, frontier, and rebuild behavior."""
from dataclasses import replace
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.control_plane.event_stream import EventFamily, EventStreamBroker
from bilqis_mlx.mission_control.observability import GenerationManifest
from bilqis_mlx.mission_control.projection import (
    MissionControlProjection, ProjectionFrontierState,
)
from bilqis_mlx.mission_control.query_catalog import MissionControlQueryCatalog
from bilqis_mlx.mission_control.query_contracts import (
    QueryFamily, QueryMode, QueryRequest,
)
from bilqis_mlx.mission_control.tests.samples import SAMPLES


class MissionControlProjectionTests(unittest.TestCase):
    def test_empty_build_queries_and_delete_rebuild_are_equivalent(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "mission-control.sqlite3"
            records = SAMPLES[:16]
            frontier = ("mission-control", "epoch-a", 2, "a" * 64)
            expected = MissionControlQueryCatalog(records)
            projection = MissionControlProjection.rebuild(
                path, records, frontiers=(frontier,))
            requests = (
                QueryRequest(QueryFamily.RUN, run_id="run-7", limit=32),
                QueryRequest(QueryFamily.CAPABILITY, record_id="capability"),
                QueryRequest(QueryFamily.EPISODE, record_id="episode"),
                QueryRequest(QueryFamily.GENERATION, generation=7),
                QueryRequest(QueryFamily.REFERENCE, reference="evidence:a", limit=32),
            )
            first = tuple(
                expected.encode_page(projection.catalog().query(request))
                for request in requests
            )
            literal = tuple(
                expected.encode_page(expected.query(request))
                for request in requests
            )
            self.assertEqual(first, literal)
            self.assertEqual(
                projection.frontier_status(*frontier).state,
                ProjectionFrontierState.CURRENT,
            )

            path.unlink()
            rebuilt = MissionControlProjection.rebuild(
                path, records, frontiers=(frontier,))
            second = tuple(
                expected.encode_page(rebuilt.catalog().query(request))
                for request in requests
            )
            self.assertEqual(second, first)
            self.assertEqual(
                rebuilt.frontier_status(*frontier).state,
                ProjectionFrontierState.CURRENT,
            )

    def test_duplicate_event_and_receipt_ingestion_is_idempotent(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "projection.sqlite3"
            projection = MissionControlProjection.create_empty(path)
            payload = SAMPLES[6]
            broker = EventStreamBroker(
                stream_id="mission-control", epoch_id="epoch-a")
            event = broker.publish_record(EventFamily.CANDIDATE_ASSESSED, payload)
            self.assertIsNotNone(event)
            receipt = SAMPLES[8]
            projection.ingest_records((event,))
            before_payload = projection.frontier_status(
                event.position.stream_id, event.position.epoch_id,
                event.position.ordinal + 1, event.position.cursor_sha256,
            )
            self.assertEqual(before_payload.state, ProjectionFrontierState.EMPTY)
            projection.ingest_event(event, payload)
            first = projection.ingest_records((receipt,))
            projection.ingest_event(event, payload)
            second = projection.ingest_records((receipt,))
            self.assertEqual(second, first)
            self.assertEqual(first.active_records, 3)
            self.assertEqual(first.revisions, 3)
            self.assertEqual(first.events, 1)
            status = projection.frontier_status(
                event.position.stream_id, event.position.epoch_id,
                event.position.ordinal + 1, event.position.cursor_sha256,
            )
            self.assertEqual(status.state, ProjectionFrontierState.CURRENT)
            conflicting = replace(
                event,
                meta=replace(
                    event.meta,
                    materialized_at=event.meta.materialized_at + 1,
                ),
            )
            with self.assertRaises(BilqisError) as collision:
                projection.ingest_records((conflicting,))
            self.assertEqual(
                collision.exception.context["reason"],
                "PROJECTION_EVENT_IDENTITY_CONFLICT",
            )

    def test_event_frontier_lag_clears_only_after_verified_payload_ingestion(self):
        with TemporaryDirectory() as temporary:
            projection = MissionControlProjection.create_empty(
                Path(temporary) / "projection.sqlite3")
            broker = EventStreamBroker(
                stream_id="mission-control", epoch_id="epoch-a")
            first_payload, second_payload = SAMPLES[5], SAMPLES[6]
            first = broker.publish_record(
                EventFamily.LESSON_VISIT_COMPLETED, first_payload)
            second = broker.publish_record(
                EventFamily.CANDIDATE_ASSESSED, second_payload)
            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            frontier = broker.frontier()
            with self.assertRaises(BilqisError) as skipped:
                projection.ingest_event(second, second_payload)
            self.assertEqual(
                skipped.exception.context["reason"],
                "PROJECTION_FRONTIER_GAP_REBUILD_REQUIRED",
            )
            self.assertEqual(
                projection.frontier_status(
                    frontier.stream_id, frontier.epoch_id,
                    frontier.next_ordinal, frontier.latest_cursor_sha256,
                ).state,
                ProjectionFrontierState.EMPTY,
            )
            projection.ingest_event(first, first_payload)
            lagging = projection.frontier_status(
                frontier.stream_id, frontier.epoch_id,
                frontier.next_ordinal, frontier.latest_cursor_sha256,
            )
            self.assertEqual(lagging.state, ProjectionFrontierState.STALE)
            projection.ingest_event(second, second_payload)
            caught_up = projection.frontier_status(
                frontier.stream_id, frontier.epoch_id,
                frontier.next_ordinal, frontier.latest_cursor_sha256,
            )
            self.assertEqual(caught_up.state, ProjectionFrontierState.CURRENT)

    def test_large_event_payload_stays_external_by_ref_and_digest(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            projection = MissionControlProjection.create_empty(
                root / "projection.sqlite3")
            blob = (b"CP06-EXTERNAL-PAYLOAD-" * 65536)
            digest = hashlib.sha256(blob).hexdigest()
            broker = EventStreamBroker(
                stream_id="mission-control", epoch_id="epoch-a")
            event = broker.publish_reference(
                EventFamily.WARNING_FAILURE,
                meta=SAMPLES[5].meta,
                payload_schema_version=SAMPLES[5].schema_version,
                payload_record_id="external-large-payload",
                payload_sha256=digest,
                payload_ref="artifact:external-large-payload",
            )
            self.assertIsNotNone(event)
            projection.ingest_records((event,))
            stored = projection.revisions(event.meta.record_id)[0]
            self.assertEqual(stored.payload_sha256, digest)
            self.assertEqual(
                stored.payload_ref, "artifact:external-large-payload")
            self.assertNotIn(blob[:4096], projection.path.read_bytes())
            status = projection.frontier_status(
                event.position.stream_id, event.position.epoch_id,
                event.position.ordinal + 1, event.position.cursor_sha256,
            )
            self.assertEqual(status.state, ProjectionFrontierState.EMPTY)

    def test_changed_generation_and_receipt_create_revisioned_state(self):
        with TemporaryDirectory() as temporary:
            projection = MissionControlProjection.create_empty(
                Path(temporary) / "projection.sqlite3")
            old = SAMPLES[14]
            self.assertIs(type(old), GenerationManifest)
            new_run = replace(
                old.meta.run,
                generation=8,
                generation_manifest_sha256="5" * 64,
            )
            new = replace(
                old,
                meta=replace(
                    old.meta,
                    record_id="generation:8",
                    run=new_run,
                    materialized_at=121,
                    observed_at=119,
                    as_of=119,
                    receipt_refs=("receipt:generation:8",),
                ),
                checkpoint_sha256="6" * 64,
                student_sha256="7" * 64,
                optimizer_state_sha256="8" * 64,
                parent_manifest_sha256=old.meta.run.generation_manifest_sha256,
            )
            projection.ingest_records((old, new))
            catalog = projection.catalog()
            old_page = catalog.query(QueryRequest(
                QueryFamily.GENERATION, mode=QueryMode.HISTORICAL,
                generation=7,
            ))
            new_page = catalog.query(QueryRequest(
                QueryFamily.GENERATION, mode=QueryMode.HISTORICAL,
                generation=8,
            ))
            self.assertEqual(
                [item.meta.record_id for item in old_page.records], ["generation"])
            self.assertEqual(
                [item.meta.record_id for item in new_page.records], ["generation:8"])

            receipt = SAMPLES[17]
            pending = replace(
                receipt,
                meta=replace(
                    receipt.meta,
                    materialized_at=119,
                    observed_at=118,
                    as_of=118,
                    receipt_refs=(),
                ),
                state=type(receipt.state).PENDING,
                acknowledged_at=119,
                postcondition_ref=None,
            )
            projection.ingest_records((pending, receipt))
            revisions = projection.revisions(receipt.meta.record_id)
            self.assertEqual(
                [item.state.value for item in revisions], ["PENDING", "COMPLETED"])
            self.assertEqual(projection.stats().revisions, 4)

    def test_frontier_lag_and_divergence_are_explicit(self):
        with TemporaryDirectory() as temporary:
            projection = MissionControlProjection.create_empty(
                Path(temporary) / "projection.sqlite3")
            empty = projection.frontier_status(
                "mission-control", "epoch-a", 2, "a" * 64)
            self.assertEqual(empty.state, ProjectionFrontierState.EMPTY)
            projection.record_frontier(
                "mission-control", "epoch-a", 2, "a" * 64)
            current = projection.frontier_status(
                "mission-control", "epoch-a", 2, "a" * 64)
            stale = projection.frontier_status(
                "mission-control", "epoch-a", 3, "b" * 64)
            diverged = projection.frontier_status(
                "mission-control", "epoch-a", 2, "c" * 64)
            restarted = projection.frontier_status(
                "mission-control", "epoch-b", 1, "d" * 64)
            self.assertEqual(current.state, ProjectionFrontierState.CURRENT)
            self.assertEqual(stale.state, ProjectionFrontierState.STALE)
            self.assertEqual(diverged.state, ProjectionFrontierState.DIVERGED)
            self.assertEqual(restarted.state, ProjectionFrontierState.STALE)
            with self.assertRaises(BilqisError) as epoch_change:
                projection.record_frontier(
                    "mission-control", "epoch-b", 1, "d" * 64)
            self.assertEqual(
                epoch_change.exception.context["reason"],
                "PROJECTION_FRONTIER_EPOCH_MISMATCH_REBUILD_REQUIRED",
            )

    def test_incompatible_or_corrupt_index_fails_closed_with_rebuild_guidance(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "projection.sqlite3"
            MissionControlProjection.create_empty(path)
            with sqlite3.connect(path) as db:
                db.execute(
                    "UPDATE projection_meta SET value = '999' WHERE key = 'schema_version'")
                db.commit()
            with self.assertRaises(BilqisError) as incompatible:
                MissionControlProjection(path)
            self.assertEqual(
                incompatible.exception.context["reason"],
                "PROJECTION_SCHEMA_INCOMPATIBLE_REBUILD_REQUIRED",
            )
            recovered = MissionControlProjection.rebuild(path, SAMPLES[:2])
            self.assertEqual(recovered.stats().active_records, 2)

            path.write_bytes(b"not-a-sqlite-database")
            with self.assertRaises(BilqisError) as corrupt:
                MissionControlProjection(path)
            self.assertEqual(
                corrupt.exception.context["reason"],
                "PROJECTION_CORRUPT_REBUILD_REQUIRED",
            )

    def test_missing_index_and_row_tamper_fail_closed(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "projection.sqlite3"
            with self.assertRaises(BilqisError) as missing:
                MissionControlProjection(path)
            self.assertEqual(
                missing.exception.context["reason"],
                "PROJECTION_MISSING_REBUILD_REQUIRED",
            )
            projection = MissionControlProjection.rebuild(path, SAMPLES[:2])
            with sqlite3.connect(path) as db:
                db.execute(
                    """UPDATE record_revisions SET payload_json =
                    replace(payload_json, 'READY', 'BROKEN')
                    WHERE record_id = 'run-context'"""
                )
                db.commit()
            with self.assertRaises(BilqisError) as tampered:
                projection.catalog()
            self.assertEqual(
                tampered.exception.context["reason"],
                "PROJECTION_ROW_DIGEST_MISMATCH_REBUILD_REQUIRED",
            )

    def test_symlink_projection_path_is_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.sqlite3"
            MissionControlProjection.create_empty(target)
            link = root / "projection.sqlite3"
            link.symlink_to(target)
            with self.assertRaises(BilqisError) as unsafe:
                MissionControlProjection(link)
            self.assertEqual(
                unsafe.exception.context["reason"], "PROJECTION_PATH_UNSAFE")


if __name__ == "__main__":
    unittest.main()
