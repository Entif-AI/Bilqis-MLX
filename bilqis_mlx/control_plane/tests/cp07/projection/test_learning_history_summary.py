"""The bounded observer projection conserves authenticated episode evidence."""
from dataclasses import replace
import unittest

from bilqis_mlx.control_plane.native_source import authenticated_history, native_query_source
from bilqis_mlx.control_plane.native_contracts import run_ref
from bilqis_mlx.control_plane.projection.learning_history import LearningHistoryProjection
from bilqis_mlx.mission_control import (
    CandidateDecision, CandidateOutcome, CoverageState, LearningEpisode,
    LearningHistorySummary, PartialEnvelope, QueryFamily, QueryMode, QueryRequest,
    decode_record, encode_record,
)
from bilqis_mlx.mission_control.tests.samples import meta
from ..native_source_support import NativeSourceFixture


class LearningHistorySummaryTests(NativeSourceFixture, unittest.TestCase):
    def test_current_summary_preserves_detail_and_is_not_historical(self):
        self.parent()
        self.publish_successor()
        catalog = native_query_source(self.run)()
        request = QueryRequest(QueryFamily.RECORD,
                               schema_version=LearningHistorySummary.SCHEMA)
        summary, = catalog.query(request).records
        detailed = catalog.query(QueryRequest(QueryFamily.EPISODE, limit=32))
        episodes = [row for row in detailed.records if isinstance(row, LearningEpisode)]
        decisions = [row for row in detailed.records if isinstance(row, CandidateDecision)]
        self.assertEqual(summary.visit_count, len(episodes))
        self.assertEqual(summary.decision_count, len(decisions))
        self.assertEqual(summary.accepted_count, 1)
        self.assertEqual(decode_record(encode_record(summary)), summary)
        historical = replace(request, mode=QueryMode.HISTORICAL,
                             generation=summary.meta.run.generation)
        self.assertEqual(catalog.query(historical).records, ())

    def test_bounded_pulse_and_exact_counts_reuse_unchanged_evidence(self):
        self.parent()
        tip = authenticated_history(self.run)[-1]
        run = run_ref(tip)
        decision = CandidateDecision(meta("decision", run=run), "candidate",
                                     "A.NATIVE", CandidateOutcome.REJECTED, "NO_GAIN")
        rows = tuple(replace(decision, meta=meta(f"decision-{i:03}", run=run))
                     for i in range(40))
        projection = LearningHistoryProjection()
        summary = projection(tip, rows)
        self.assertEqual((summary.decision_count, summary.rejected_count), (40, 40))
        self.assertEqual(tuple(row.meta.record_id for row in summary.recent_decisions),
                         tuple(f"decision-{i:03}" for i in range(39, 31, -1)))
        self.assertIs(projection(tip, tuple(reversed(rows))), summary)
        marker = PartialEnvelope(meta("partial", run=run, coverage=CoverageState.PARTIAL),
                                 rows[0].meta.record_id, ("source_time",))
        partial = projection(tip, (*rows, marker))
        self.assertEqual(partial.meta.coverage, CoverageState.PARTIAL)
        self.assertEqual(partial.rejected_count, 40)
        self.assertNotEqual(partial.source_rows_sha256, summary.source_rows_sha256)
        self.assertEqual(decode_record(encode_record(partial)), partial)
