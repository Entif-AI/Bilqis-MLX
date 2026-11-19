"""CT-054 projection rebuild, migration, stale-read and rollback proof."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.akasha_domains import AkashaDomain, DOMAIN_CONTRACTS
from bilqis_mlx.runtime.akasha_projection_lifecycle import (
    ProjectionSelectionKind,
    begin_projection_rebuild,
    complete_projection_rebuild,
    list_projection_versions,
    read_active_projection,
    read_projection_version,
    rollback_projection_version,
    select_projection_version,
    selection_history,
)


DOMAIN = AkashaDomain.RECEIPT_PROVENANCE
REBUILD_SOURCE = DOMAIN_CONTRACTS[DOMAIN].rebuild_sources[0]
SOURCE_V1 = ({"receipt_sha256": "a" * 64, "event_id": "event:1"},)
SOURCE_V2 = SOURCE_V1 + ({"receipt_sha256": "b" * 64, "event_id": "event:2"},)
EVIDENCE_1 = "1" * 64
EVIDENCE_2 = "2" * 64
EVIDENCE_3 = "3" * 64


def _build(path: Path, version: int, source, expected, payload):
    intent = begin_projection_rebuild(
        path, DOMAIN, projection_version=version,
        rebuild_source=REBUILD_SOURCE, source_records=source,
        expected_active_sha256=expected)
    return intent, complete_projection_rebuild(
        path, intent, source_records=source, payload=payload)


def _select_initial(path: Path):
    intent, version = _build(
        path, 1, SOURCE_V1, None, {"events": ["event:1"], "layout": 1})
    receipt = select_projection_version(
        path, version, expected_active_sha256=None,
        kind=ProjectionSelectionKind.INITIAL, evidence_sha256=EVIDENCE_1)
    return intent, version, receipt


class AkashaProjectionLifecycleTests(unittest.TestCase):
    def test_fresh_rebuild_is_source_bound_and_stale_read_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lifecycle.sqlite3"
            intent, version, receipt = _select_initial(path)
            self.assertEqual(intent.projection_schema, DOMAIN_CONTRACTS[DOMAIN].projection_schema)
            self.assertEqual(intent.rebuild_source, REBUILD_SOURCE)
            self.assertEqual(receipt.selected_version_sha256, version.version_sha256)
            self.assertEqual(
                read_active_projection(
                    path, DOMAIN, source_records=SOURCE_V1,
                    expected_projection_version=1),
                version)
            with self.assertRaises(BilqisError) as caught:
                read_active_projection(path, DOMAIN, source_records=SOURCE_V2)
            self.assertEqual(caught.exception.context["reason"], "AKASHA_PROJECTION_STALE")

    def test_schema_version_migration_creates_new_version_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lifecycle.sqlite3"
            _, first, initial = _select_initial(path)
            _, second = _build(
                path, 2, SOURCE_V2, first.version_sha256,
                {"events": ["event:1", "event:2"], "layout": 2})
            migration = select_projection_version(
                path, second, expected_active_sha256=first.version_sha256,
                kind=ProjectionSelectionKind.MIGRATION, evidence_sha256=EVIDENCE_2)
            self.assertEqual(
                read_active_projection(
                    path, DOMAIN, source_records=SOURCE_V2,
                    expected_projection_version=2),
                second)
            self.assertEqual(list_projection_versions(path, DOMAIN), (first, second))
            self.assertEqual(read_projection_version(path, first.version_sha256), first)
            self.assertEqual(selection_history(path, DOMAIN), (initial, migration))

    def test_migration_and_rebuild_enforce_version_transition_semantics(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lifecycle.sqlite3"
            _, first, _ = _select_initial(path)
            _, same_version = _build(
                path, 1, SOURCE_V2, first.version_sha256,
                {"events": ["event:1", "event:2"], "layout": 1})
            with self.assertRaises(BilqisError) as caught:
                select_projection_version(
                    path, same_version, expected_active_sha256=first.version_sha256,
                    kind=ProjectionSelectionKind.MIGRATION, evidence_sha256=EVIDENCE_2)
            self.assertEqual(
                caught.exception.context["reason"],
                "AKASHA_PROJECTION_MIGRATION_VERSION_INVALID")
            select_projection_version(
                path, same_version, expected_active_sha256=first.version_sha256,
                kind=ProjectionSelectionKind.REBUILD, evidence_sha256=EVIDENCE_2)
            self.assertEqual(
                read_active_projection(
                    path, DOMAIN, source_records=SOURCE_V2,
                    expected_projection_version=1),
                same_version)

    def test_interrupted_rebuild_never_becomes_current(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lifecycle.sqlite3"
            _, first, _ = _select_initial(path)
            begin_projection_rebuild(
                path, DOMAIN, projection_version=2,
                rebuild_source=REBUILD_SOURCE, source_records=SOURCE_V2,
                expected_active_sha256=first.version_sha256)
            self.assertEqual(
                read_active_projection(path, DOMAIN, source_records=SOURCE_V1), first)
            self.assertEqual(list_projection_versions(path, DOMAIN), (first,))

    def test_completion_rejects_source_frontier_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lifecycle.sqlite3"
            intent = begin_projection_rebuild(
                path, DOMAIN, projection_version=1,
                rebuild_source=REBUILD_SOURCE, source_records=SOURCE_V1,
                expected_active_sha256=None)
            with self.assertRaises(BilqisError) as caught:
                complete_projection_rebuild(
                    path, intent, source_records=SOURCE_V2,
                    payload={"events": ["event:1", "event:2"]})
            self.assertEqual(
                caught.exception.context["reason"],
                "AKASHA_PROJECTION_SOURCE_FRONTIER_DRIFT")

    def test_rollback_selects_prior_valid_version_and_preserves_newer_version(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lifecycle.sqlite3"
            _, first, initial = _select_initial(path)
            _, second = _build(
                path, 2, SOURCE_V2, first.version_sha256,
                {"events": ["event:1", "event:2"], "layout": 2})
            migration = select_projection_version(
                path, second, expected_active_sha256=first.version_sha256,
                kind=ProjectionSelectionKind.MIGRATION, evidence_sha256=EVIDENCE_2)
            rollback = rollback_projection_version(
                path, DOMAIN, first.version_sha256,
                expected_active_sha256=second.version_sha256,
                evidence_sha256=EVIDENCE_3)
            self.assertEqual(rollback.kind, ProjectionSelectionKind.ROLLBACK)
            self.assertEqual(
                read_active_projection(path, DOMAIN, source_records=SOURCE_V1), first)
            self.assertEqual(list_projection_versions(path, DOMAIN), (first, second))
            self.assertEqual(
                selection_history(path, DOMAIN), (initial, migration, rollback))

    def test_rollback_rejects_completed_version_that_was_never_current(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lifecycle.sqlite3"
            _, first, _ = _select_initial(path)
            _, never_selected = _build(
                path, 2, SOURCE_V2, first.version_sha256,
                {"events": ["event:1", "event:2"], "layout": 2})
            with self.assertRaises(BilqisError) as caught:
                rollback_projection_version(
                    path, DOMAIN, never_selected.version_sha256,
                    expected_active_sha256=first.version_sha256,
                    evidence_sha256=EVIDENCE_3)
            self.assertEqual(
                caught.exception.context["reason"],
                "AKASHA_PROJECTION_ROLLBACK_TARGET_UNPROVEN")

    def test_stored_corruption_is_operator_visible_and_never_silently_repaired(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lifecycle.sqlite3"
            _, first, _ = _select_initial(path)
            with sqlite3.connect(path) as connection:
                connection.execute("DROP TRIGGER akasha_projection_versions_no_update")
                connection.execute(
                    "UPDATE akasha_projection_versions SET canonical_json=? "
                    "WHERE version_sha256=?",
                    ("{}", first.version_sha256))
            with self.assertRaises(BilqisError) as caught:
                read_projection_version(path, first.version_sha256)
            self.assertEqual(
                caught.exception.context["reason"],
                "AKASHA_PROJECTION_STORED_CORRUPT")
            with sqlite3.connect(path) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT canonical_json FROM akasha_projection_versions "
                        "WHERE version_sha256=?", (first.version_sha256,)).fetchone()[0],
                    "{}")


if __name__ == "__main__":
    unittest.main()
