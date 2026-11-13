"""Literal CP03 queries cover every required Mission Control read family."""
from dataclasses import replace
import unittest

from bilqis_mlx.mission_control.codec import canonical_json, encode_record
from bilqis_mlx.mission_control.query_contracts import (
    QueryFamily, QueryRequest, QueryState,
)
from bilqis_mlx.mission_control.query_catalog import MissionControlQueryCatalog
from bilqis_mlx.mission_control.tests.samples import SAMPLES
from bilqis_mlx.presentation.atlas_metrics import bamf_status


_FAMILIES = (
    QueryFamily.RUN,
    QueryFamily.SCHOOL,
    QueryFamily.CAPABILITY,
    QueryFamily.EPISODE,
    QueryFamily.GENERATION,
    QueryFamily.SEMANTIC,
    QueryFamily.FRAME,
    QueryFamily.NEURAL,
    QueryFamily.MEMORY,
    QueryFamily.TEACHER,
    QueryFamily.SALIENCE,
    QueryFamily.CORRECTION,
    QueryFamily.RESOURCE,
)


class MissionControlQueryFamilyTests(unittest.TestCase):
    def setUp(self):
        self.domain_records = SAMPLES[:16]
        self.index = MissionControlQueryCatalog(self.domain_records)

    def test_literal_fixture_queries_cover_every_required_family(self):
        for family in _FAMILIES:
            with self.subTest(family=family.value):
                page = self.index.query(QueryRequest(family))
                self.assertEqual(page.state, QueryState.PRESENT)
                self.assertGreaterEqual(page.total_matches, 1)
                self.assertTrue(page.records)

    def test_current_operator_view_is_the_same_cp02_truth_used_by_status(self):
        page = self.index.query(QueryRequest(QueryFamily.RUN))
        operator = next(
            item for item in page.records
            if item.schema_version.endswith("operator-view/v1"))
        self.assertEqual(bamf_status(encode_record(operator)), operator)

    def test_querying_records_is_byte_stable_and_non_mutating(self):
        before = tuple(canonical_json(item) for item in self.domain_records)
        for family in _FAMILIES:
            self.index.query(QueryRequest(family))
        after = tuple(canonical_json(item) for item in self.domain_records)
        self.assertEqual(after, before)

    def test_capability_episode_evidence_and_generation_receipt_links_resolve(self):
        capability = self.index.query(QueryRequest(
            QueryFamily.LINKS, record_id="capability"))
        episode = next(link for link in capability.links if link.relation == "EPISODE")
        self.assertEqual(episode.target_record_id, "episode")

        episode_links = self.index.query(QueryRequest(
            QueryFamily.LINKS, record_id=episode.target_record_id))
        self.assertIn(
            "evidence:a",
            {link.target_ref for link in episode_links.links
             if link.relation == "EVIDENCE"},
        )

        generation = self.index.query(QueryRequest(
            QueryFamily.LINKS, record_id="generation"))
        checkpoint = next(
            link for link in generation.links if link.relation == "CHECKPOINT")
        self.assertTrue(checkpoint.target_ref.startswith("checkpoint:"))
        self.assertIn(
            "receipt:a",
            {link.target_ref for link in generation.links
             if link.relation == "RECEIPT"},
        )

    def test_reference_lookup_returns_exact_stable_link_sources(self):
        page = self.index.query(QueryRequest(
            QueryFamily.REFERENCE, reference="evidence:a", limit=32))
        self.assertEqual(page.state, QueryState.PRESENT)
        self.assertGreater(page.total_matches, 1)
        self.assertTrue(all(link.target_ref == "evidence:a" for link in page.links))

    def test_index_rejects_duplicate_record_identity(self):
        with self.assertRaises(ValueError):
            MissionControlQueryCatalog((*self.domain_records, replace(
                self.domain_records[0], meta=self.domain_records[0].meta)))


if __name__ == "__main__":
    unittest.main()
