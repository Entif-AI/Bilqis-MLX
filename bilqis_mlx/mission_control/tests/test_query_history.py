"""CP03 historical identity, pagination, and degraded projection semantics."""
from dataclasses import replace
import unittest

from bilqis_mlx.mission_control.envelopes import (
    PartialEnvelope, StaleEnvelope, UnavailableEnvelope, UnavailableReason,
)
from bilqis_mlx.mission_control.model import AuthorityClass, CoverageState, RecordMeta
from bilqis_mlx.mission_control.query_contracts import (
    DEFAULT_PAGE_SIZE, QueryFamily, QueryMode, QueryRequest, QueryState,
)
from bilqis_mlx.mission_control.query_catalog import MissionControlQueryCatalog
from bilqis_mlx.mission_control.snapshots import CapabilitySnapshot, OperatorView
from bilqis_mlx.mission_control.tests.samples import RUN, SAMPLES, value


def _meta(record_id, run, *, as_of):
    return RecordMeta(
        record_id, run, as_of + 2, as_of, as_of,
        CoverageState.COMPLETE, AuthorityClass.DERIVED,
        evidence_refs=(f"evidence:{record_id}",),
        receipt_refs=(f"receipt:{record_id}",),
    )


class MissionControlQueryHistoryTests(unittest.TestCase):
    def test_current_selects_newest_generation_but_historical_is_exact(self):
        run6 = replace(
            RUN, generation=6, generation_manifest_sha256="6" * 64)
        old = OperatorView(
            _meta("operator:6", run6, as_of=106),
            "READY", "ASSESS_OLD", None, ())
        current = OperatorView(
            _meta("operator:7", RUN, as_of=118),
            "READY", "ASSESS_MAIN", None, ())
        index = MissionControlQueryCatalog((old, current))

        current_page = index.query(QueryRequest(QueryFamily.RUN, run_id="run-7"))
        self.assertEqual(
            [item.meta.record_id for item in current_page.records], ["operator:7"])

        historical = index.query(QueryRequest(
            QueryFamily.RUN, mode=QueryMode.HISTORICAL,
            run_id="run-7", generation=6))
        self.assertEqual(
            [item.meta.record_id for item in historical.records], ["operator:6"])

        missing = index.query(QueryRequest(
            QueryFamily.RUN, mode=QueryMode.HISTORICAL,
            run_id="run-7", generation=999))
        self.assertEqual(missing.state, QueryState.MISSING)
        self.assertEqual(missing.records, ())
        self.assertEqual(old.meta.evidence_refs, ("evidence:operator:6",))
        self.assertEqual(current.meta.evidence_refs, ("evidence:operator:7",))

    def test_historical_frontier_query_is_exact(self):
        index = MissionControlQueryCatalog((SAMPLES[4],))
        page = index.query(QueryRequest(
            QueryFamily.SCHOOL, mode=QueryMode.HISTORICAL,
            frontier_id="frontier-7"))
        self.assertEqual(page.state, QueryState.PRESENT)
        self.assertEqual(
            [item.meta.record_id for item in page.records], ["frontier"])
        missing = index.query(QueryRequest(
            QueryFamily.SCHOOL, mode=QueryMode.HISTORICAL,
            frontier_id="frontier-missing"))
        self.assertEqual(missing.state, QueryState.MISSING)

    def test_historical_request_cannot_omit_explicit_identity_or_use_latest(self):
        with self.assertRaises(ValueError):
            QueryRequest(QueryFamily.RUN, mode=QueryMode.HISTORICAL)
        with self.assertRaises(ValueError):
            QueryRequest(
                QueryFamily.RUN, mode=QueryMode.HISTORICAL,
                record_id="latest")

    def test_query_request_wire_round_trip_preserves_exact_identity(self):
        request = QueryRequest(
            QueryFamily.CAPABILITY,
            mode=QueryMode.HISTORICAL,
            run_id="run-7",
            generation=7,
            schema_version="bilqis.bamf.mission-control.capability-snapshot/v1",
            limit=3,
        )
        self.assertEqual(
            QueryRequest.from_mapping(request.to_record()), request)

    def test_pagination_reports_truncation_and_cursor_is_query_bound(self):
        capabilities = tuple(
            CapabilitySnapshot(
                _meta(f"capability:{index}", RUN, as_of=118),
                f"B.CAP{index}", "B", "LEARNING", value(index), value(10), value(0),
            )
            for index in range(DEFAULT_PAGE_SIZE + 3)
        )
        index = MissionControlQueryCatalog(capabilities)
        first_request = QueryRequest(QueryFamily.CAPABILITY)
        first = index.query(first_request)
        self.assertTrue(first.truncated)
        self.assertEqual(len(first.records), DEFAULT_PAGE_SIZE)
        self.assertEqual(first.total_matches, DEFAULT_PAGE_SIZE + 3)
        self.assertEqual(first.coverage, CoverageState.PARTIAL)

        second = index.query(replace(
            first_request, cursor=first.next_cursor))
        self.assertFalse(second.truncated)
        self.assertEqual(len(second.records), 3)
        self.assertEqual(second.coverage, CoverageState.COMPLETE)
        with self.assertRaises(ValueError):
            index.query(QueryRequest(
                QueryFamily.CAPABILITY,
                schema_version="bilqis.bamf.mission-control.capability-snapshot/v9",
                cursor=first.next_cursor,
            ))

    def test_partial_stale_denied_unknown_and_unavailable_do_not_collapse(self):
        school = SAMPLES[2]
        partial_meta = replace(
            school.meta, record_id="partial:school", coverage=CoverageState.PARTIAL)
        partial = PartialEnvelope(
            partial_meta, school.meta.record_id, ("mastered_count",))
        partial_page = MissionControlQueryCatalog((school, partial)).query(
            QueryRequest(QueryFamily.SCHOOL))
        self.assertEqual(partial_page.state, QueryState.PARTIAL)
        self.assertEqual(partial_page.markers, (partial,))

        stale_record = replace(
            SAMPLES[1], meta=replace(
                SAMPLES[1].meta, record_id="operator:stale", as_of=100))
        stale = StaleEnvelope(
            replace(
                stale_record.meta, record_id="stale:operator",
                coverage=CoverageState.PARTIAL),
            stale_record.meta.record_id, 100, 118,
        )
        stale_page = MissionControlQueryCatalog((stale_record, stale)).query(
            QueryRequest(
                QueryFamily.RUN, mode=QueryMode.HISTORICAL, as_of=118))
        self.assertEqual(stale_page.state, QueryState.STALE)
        self.assertEqual(stale_page.markers, (stale,))

        for reason, expected in (
            (UnavailableReason.DENIED, QueryState.DENIED),
            (UnavailableReason.UNKNOWN, QueryState.UNKNOWN),
            (UnavailableReason.UNAVAILABLE, QueryState.UNAVAILABLE),
        ):
            marker = UnavailableEnvelope(
                RecordMeta(
                    f"unavailable:{reason.value}", None, 120, None, None,
                    CoverageState.UNKNOWN, AuthorityClass.DERIVED,
                ),
                "capability", reason, None,
            )
            page = MissionControlQueryCatalog((marker,)).query(
                QueryRequest(QueryFamily.CAPABILITY))
            self.assertEqual(page.state, expected)

        self.assertEqual(
            MissionControlQueryCatalog(()).query(
                QueryRequest(QueryFamily.CAPABILITY)).state,
            QueryState.EMPTY,
        )
        self.assertEqual(
            MissionControlQueryCatalog.unavailable().query(
                QueryRequest(QueryFamily.CAPABILITY)).state,
            QueryState.UNAVAILABLE,
        )


if __name__ == "__main__":
    unittest.main()
