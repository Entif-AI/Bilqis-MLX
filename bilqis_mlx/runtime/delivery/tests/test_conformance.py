import unittest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.delivery import ProofState
from bilqis_mlx.runtime.delivery.conformance import (
    ConformanceProjection, ConformanceRow, required_claim_ids,
)


def rows():
    return tuple(ConformanceRow(
        claim_id, "docs/tasks/bamf-0.2/ISSUE_BOOK.md",
        "docs/architecture/BAMF_0_2.md", f"tests/{claim_id}.py", ProofState.SPECIFIED)
        for claim_id in required_claim_ids())


class ConformanceProjectionTests(unittest.TestCase):
    def test_projection_requires_all_24_requirements_and_20_failures_in_order(self):
        value = ConformanceProjection(rows(), "IN_PROGRESS", "NOT_CLAIMED")
        self.assertEqual(len(value.rows), 44)
        self.assertEqual(value.rows[0].claim_id, "BAMF-REQ-001")
        self.assertEqual(value.rows[-1].claim_id, "F20")
        self.assertEqual(value.digest(), ConformanceProjection(
            rows(), "IN_PROGRESS", "NOT_CLAIMED").digest())

    def test_projection_refuses_missing_row_and_keeps_mastery_separate(self):
        with self.assertRaises(BilqisError) as caught:
            ConformanceProjection(rows()[:-1], "READY_FOR_OWNER_MERGE", "DEMONSTRATED")
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)


if __name__ == "__main__":
    unittest.main()
