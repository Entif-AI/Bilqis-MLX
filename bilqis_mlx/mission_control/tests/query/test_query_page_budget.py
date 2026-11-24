"""Regression for wire-sized episode pages containing availability markers."""
from dataclasses import replace
import json
import unittest

from bilqis_mlx.mission_control.contracts.envelopes import (
    UnavailableEnvelope, UnavailableReason,
)
from bilqis_mlx.mission_control.contracts.events import (
    CandidateDecision, CandidateOutcome,
)
from bilqis_mlx.mission_control.contracts.model import (
    AuthorityClass, CoverageState, RecordMeta,
)
from bilqis_mlx.mission_control.query_catalog import MissionControlQueryCatalog
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryRequest
from bilqis_mlx.mission_control.tests.samples import RUN


class QueryPageBudgetTests(unittest.TestCase):
    def test_episode_page_reserves_space_for_provenance_markers(self):
        def meta(record_id, coverage):
            return RecordMeta(
                record_id, RUN, 100, 100, 100, coverage, AuthorityClass.DERIVED,
                evidence_refs=("evidence:" + "a" * 700,),
            )

        rows = tuple(
            CandidateDecision(
                meta(f"decision:{i:02}", CoverageState.COMPLETE),
                f"candidate:{i:02}", "A.LINK", CandidateOutcome.REJECTED, "TEST",
            )
            for i in range(32)
        )
        markers = tuple(
            UnavailableEnvelope(
                meta(f"marker:{i}", CoverageState.UNKNOWN),
                "episode", UnavailableReason.UNKNOWN, None,
            )
            for i in range(15)
        )
        catalog = MissionControlQueryCatalog((*rows, *markers))
        request = QueryRequest(QueryFamily.EPISODE, run_id=RUN.run_id, limit=32)
        page = catalog.query(request)
        self.assertGreater(len(page.records), 0)
        self.assertLess(len(page.records), 32)
        found = []
        while True:
            found.extend(row.meta.record_id for row in page.records)
            self.assertEqual(set(page.markers), set(markers))
            wire = json.dumps(catalog.encode_page(page), separators=(",", ":"))
            self.assertLess(len(wire.encode("utf-8")), 64 * 1024)
            if not page.next_cursor:
                break
            page = catalog.query(replace(request, cursor=page.next_cursor))
        self.assertEqual(len(found), 32)
        self.assertEqual(set(found), {row.meta.record_id for row in rows})
