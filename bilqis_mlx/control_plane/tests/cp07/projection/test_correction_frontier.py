"""Distinguish a known accepted frontier from an unmeasured impact queue."""
from dataclasses import replace
import unittest

from bilqis_mlx.control_plane.native_source import authenticated_history, native_query_source
from bilqis_mlx.control_plane.projection.correction_frontier import accepted_correction_frontier
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.mission_control import (
    CorrectionFrontierSnapshot, CoverageState, QueryFamily, QueryMode, QueryRequest,
    decode_record, encode_record,
)
from ..native_source_support import NativeSourceFixture


class CorrectionFrontierTests(NativeSourceFixture, unittest.TestCase):
    def test_authenticated_empty_frontier_is_not_a_correction_event(self):
        self.parent()
        self.publish_successor()
        catalog = native_query_source(self.run)()
        request = QueryRequest(QueryFamily.RECORD, schema_version=CorrectionFrontierSnapshot.SCHEMA)
        current, = catalog.query(request).records
        self.assertEqual(current.meta.run.generation, 1)
        self.assertEqual(current.frontier_entry_count, 0)
        self.assertEqual(current.correction_generation, 0)
        self.assertEqual(current.meta.coverage, CoverageState.PARTIAL)
        self.assertEqual(decode_record(encode_record(current)), current)
        self.assertEqual(catalog.query(QueryRequest(QueryFamily.CORRECTION)).records, ())
        historical, = catalog.query(replace(
            request, mode=QueryMode.HISTORICAL, generation=0)).records
        self.assertEqual(historical.meta.run.generation, 0)

    def test_count_uses_sidecar_entries_and_never_invents_missing_frontier(self):
        self.parent()
        tip = authenticated_history(self.run)[-1]
        source = {**tip.correction_frontier, "frontier": [{"artifact_id": "a"}, {"artifact_id": "b"}]}
        observed, = accepted_correction_frontier(replace(tip, correction_frontier=source))
        self.assertEqual(observed.frontier_entry_count, 2)
        self.assertEqual(observed.meta.coverage, CoverageState.PARTIAL)
        self.assertEqual(accepted_correction_frontier(replace(tip, correction_frontier={})), ())
        with self.assertRaises(BilqisError):
            accepted_correction_frontier(replace(tip, correction_frontier={**source, "frontier": None}))
