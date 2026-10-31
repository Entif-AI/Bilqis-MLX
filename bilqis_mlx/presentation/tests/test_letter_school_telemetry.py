"""Stable public School50 schema and panel contract."""
import io
import tempfile
from pathlib import Path
from bilqis_mlx.presentation.dashboard import build, ingest
import unittest
from bilqis_mlx.presentation.school_telemetry import LETTER_TABLES, SchoolTelemetry
from bilqis_mlx.presentation.spiral_dashboard import Dashboard, TABLES


class SchoolTelemetryTests(unittest.TestCase):
    def test_six_legacy_panel_names_remain_but_new_school_columns_are_useful(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            self.assertEqual(set(board.rows), {name for name, _ in TABLES})
            self.assertEqual([x.name for x in dict(board.tables)["CANDIDATES"]][:3],
                             ["CAPABILITY", "VISIT", "POLICY"])
            self.assertEqual([x.name for x in dict(TABLES)["CANDIDATES"]][:3],
                             ["GRADE", "TRY", "STRATEGY"])
            self.assertTrue(Dashboard(stream=io.StringIO()).rows)

    def test_future_schema_version_must_not_silently_reinterpret_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = build(Path(tmp), stream=io.StringIO())
            with self.assertRaisesRegex(ValueError, "UNSUPPORTED_SCHEMA"):
                ingest(board, {"event": "SCHOOL_VISIT_COMMITTED", "grade": "Z",
                               "telemetry_schema": "bilqis.school50.telemetry/v999",
                               "capability": "Z.UNKNOWN", "optimizer_step": 300000})
            self.assertFalse(board.rows["CANDIDATES"])
