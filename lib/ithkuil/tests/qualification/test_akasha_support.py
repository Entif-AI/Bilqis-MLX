"""Regression coverage for CT-056 live qualification comparison semantics."""
import unittest

from lib.ithkuil.tests.qualification.akasha_support import equivalent_projection_receipt


class ProjectionReceiptEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.first = {
            "status": "complete",
            "graph": "bilqis_qual298_source_a",
            "owner": "qual298_a",
            "projection_version": "1.0.0",
            "canonical_sha256": "a" * 64,
            "nodes": 67410,
            "edges": 130173,
        }

    def test_independent_graph_and_owner_do_not_change_projection_equivalence(self):
        other = {
            **self.first,
            "graph": "bilqis_qual298_rebuild_b",
            "owner": "qual298_br",
        }
        self.assertTrue(equivalent_projection_receipt(self.first, other))

    def test_semantic_or_census_drift_breaks_projection_equivalence(self):
        for field, value in (
            ("canonical_sha256", "b" * 64),
            ("nodes", 67411),
            ("edges", 130172),
            ("projection_version", "2.0.0"),
            ("status", "incomplete"),
        ):
            with self.subTest(field=field):
                self.assertFalse(
                    equivalent_projection_receipt(self.first, {**self.first, field: value})
                )


if __name__ == "__main__":
    unittest.main()
