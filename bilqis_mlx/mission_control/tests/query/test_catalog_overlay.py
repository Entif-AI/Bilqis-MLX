"""Overlay construction preserves the complete CP03 query contract."""
from dataclasses import replace
import unittest

from bilqis_mlx.mission_control.contracts.model import MissionControlContractError
from bilqis_mlx.mission_control import MissionControlQueryCatalog
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryMode, QueryRequest
from bilqis_mlx.mission_control.tests.samples import RUN, SAMPLES


class CatalogOverlayTests(unittest.TestCase):
    def test_partitioned_catalog_matches_full_construction(self):
        full = MissionControlQueryCatalog(SAMPLES)
        base = MissionControlQueryCatalog(SAMPLES[::2])
        composed = base.with_records(SAMPLES[1::4]).with_records(SAMPLES[3::4])
        self.assertEqual(composed.records, full.records)
        self.assertEqual(base.records, MissionControlQueryCatalog(SAMPLES[::2]).records)
        for family in QueryFamily:
            for mode in QueryMode:
                options = {"generation": RUN.generation} if mode is QueryMode.HISTORICAL else {}
                if family is QueryFamily.LINKS:
                    options["record_id"] = "capability"
                elif family is QueryFamily.REFERENCE:
                    options["reference"] = "evidence:a"
                request = QueryRequest(family, mode=mode, limit=2, **options)
                with self.subTest(family=family, mode=mode):
                    while True:
                        expected = full.query(request)
                        self.assertEqual(composed.query(request), expected)
                        if not expected.next_cursor:
                            break
                        request = replace(request, cursor=expected.next_cursor)

    def test_duplicate_ids_cannot_cross_overlay_boundary(self):
        base = MissionControlQueryCatalog(SAMPLES[:1])
        with self.assertRaises(MissionControlContractError):
            base.with_records(SAMPLES[:1])
        self.assertEqual(base.records, SAMPLES[:1])
