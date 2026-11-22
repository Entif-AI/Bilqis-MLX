"""Cumulative current-query behavior across accepted generations."""
from dataclasses import replace
import unittest

from bilqis_mlx.mission_control.envelopes import UnavailableEnvelope, UnavailableReason
from bilqis_mlx.mission_control.events import LearningEpisode
from bilqis_mlx.mission_control.model import AuthorityClass, CoverageState, RecordMeta
from bilqis_mlx.mission_control.query_catalog import MissionControlQueryCatalog
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryRequest, QueryState
from bilqis_mlx.mission_control.tests.samples import RUN, SAMPLES


def _meta(record_id, run, *, as_of, coverage=CoverageState.COMPLETE):
    return RecordMeta(
        record_id, run, as_of + 2, as_of, as_of,
        coverage, AuthorityClass.DERIVED,
        evidence_refs=(f"evidence:{record_id}",),
        receipt_refs=(f"receipt:{record_id}",),
    )


class MissionControlCurrentCumulativeTests(unittest.TestCase):
    def test_capability_prefers_newest_generation_when_source_times_are_absent(self):
        run6 = replace(RUN, generation=6, generation_manifest_sha256="6" * 64)
        older = replace(
            SAMPLES[3],
            meta=RecordMeta(
                "capability:run-7:6:B.EXAMPLE", run6, 0, None, None,
                CoverageState.PARTIAL, AuthorityClass.DERIVED),
        )
        newer = replace(
            SAMPLES[3],
            meta=RecordMeta(
                "capability:run-7:7:B.EXAMPLE", RUN, 0, None, None,
                CoverageState.PARTIAL, AuthorityClass.DERIVED),
        )
        page = MissionControlQueryCatalog((newer, older)).query(
            QueryRequest(QueryFamily.CAPABILITY, run_id="run-7"))
        self.assertEqual(page.records, (newer,))

    def test_episode_page_is_newest_first_across_accepted_generations(self):
        run6 = replace(RUN, generation=6, generation_manifest_sha256="6" * 64)
        older = LearningEpisode(
            _meta("episode:6", run6, as_of=106), "episode-6", "A.OLD", "visit-6",
            "COMPLETED", 100, 106)
        newer = LearningEpisode(
            _meta("episode:7", RUN, as_of=118), "episode-7", "A.NEW", "visit-7",
            "COMPLETED", 112, 118)
        page = MissionControlQueryCatalog((older, newer)).query(
            QueryRequest(QueryFamily.EPISODE, run_id="run-7"))
        self.assertEqual(page.records, (newer, older))

    def test_episode_keeps_older_typed_gap_and_reports_partial_coverage(self):
        run6 = replace(RUN, generation=6, generation_manifest_sha256="6" * 64)
        older_gap = UnavailableEnvelope(
            _meta(
                "unavailable:episode:6", run6, as_of=106,
                coverage=CoverageState.UNKNOWN),
            "episode:run-7", UnavailableReason.UNAVAILABLE, None)
        current = LearningEpisode(
            _meta("episode:7", RUN, as_of=118), "episode-7", "A.NEW", "visit-7",
            "COMPLETED", 112, 118)
        page = MissionControlQueryCatalog((older_gap, current)).query(
            QueryRequest(QueryFamily.EPISODE, run_id="run-7"))
        self.assertEqual(page.state, QueryState.PARTIAL)
        self.assertEqual(page.records, (current,))
        self.assertEqual(page.markers, (older_gap,))

    def test_capability_records_survive_typed_unavailable_gap(self):
        degraded = UnavailableEnvelope(
            RecordMeta(
                "unavailable:capability:run-7", RUN, 120, None, None,
                CoverageState.UNKNOWN, AuthorityClass.DERIVED),
            "capability:run-7", UnavailableReason.UNAVAILABLE, None,
        )
        page = MissionControlQueryCatalog((SAMPLES[3], degraded)).query(
            QueryRequest(QueryFamily.CAPABILITY, run_id="run-7"))
        self.assertEqual(page.state, QueryState.PARTIAL)
        self.assertEqual(page.records, (SAMPLES[3],))
        self.assertEqual(page.markers, (degraded,))


if __name__ == "__main__":
    unittest.main()
