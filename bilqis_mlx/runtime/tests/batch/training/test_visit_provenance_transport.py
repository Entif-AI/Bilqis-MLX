"""C02 transports exact C03 visit records without minting upstream authority."""
from __future__ import annotations

import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_training_contracts import (
    BamfDeliveryProvenance, BamfTrainingRow, _issue_training_batch,
)
from bilqis_mlx.runtime.atlas_visit_provenance import BamfVisitProvenance
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import (
    c03_visit_record, visit_provenance,
)


class VisitProvenanceTransportTests(unittest.TestCase):
    @staticmethod
    def _batch(visit):
        provenance = BamfDeliveryProvenance(
            "row-1", "a" * 64, "source-1", visit.capability_id, None,
            (("policy", "focused"),), 3, 1, None, 42, visit,
            "family-1", "episode-1",
        )
        return _issue_training_batch(
            "b" * 64, "generation-1", "c" * 64, visit.capability_id,
            (BamfTrainingRow(None, None, None, provenance),),
        )

    def test_exact_c03_record_round_trips(self):
        record = c03_visit_record("C.NUMBER", run_seed=71, generation=3)
        value = BamfVisitProvenance.from_c03_record(record)
        self.assertEqual(value.to_c03_record(), record)
        self.assertEqual(value.run_seed, 71)
        self.assertEqual(value.generation, 3)
        self.assertEqual(value.capability_id, "C.NUMBER")

    def test_caller_cannot_construct_transport_or_change_record_without_digest(self):
        with self.assertRaises(BilqisError):
            BamfVisitProvenance()
        forged = c03_visit_record("A.IDENTITY")
        forged["run_seed"] += 1
        with self.assertRaises(BilqisError):
            BamfVisitProvenance.from_c03_record(forged)

    def test_run_seed_is_not_optimizer_or_episode_alias(self):
        first = visit_provenance("B.IDBOOLOPS", run_seed=17)
        second = visit_provenance("B.IDBOOLOPS", run_seed=18)
        self.assertNotEqual(first.visit_id, second.visit_id)
        self.assertEqual(first.run_seed, 17)
        self.assertFalse(hasattr(first, "optimizer_step_seed"))
        self.assertFalse(hasattr(first, "episode_id"))

        first_batch = self._batch(first)
        second_batch = self._batch(second)
        provenance = first_batch.rows[0].provenance
        self.assertEqual(provenance.optimizer_step_seed, 42)
        self.assertEqual(provenance.episode_id, "episode-1")
        self.assertNotEqual(first_batch.authority_digest, second_batch.authority_digest)


if __name__ == "__main__":
    unittest.main()
