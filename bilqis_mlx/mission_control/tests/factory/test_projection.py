"""Canonical #299 Factory ledger projection into the Mission Control cockpit."""
import unittest

from bilqis_mlx.mission_control.contracts.factory import (
    FactoryAdmissionAuthority, FactoryBlocker, FactoryCurrencyState,
    FactoryDeliveryStatus, FactoryTopologyKnowledge,
)
from bilqis_mlx.mission_control.factory_projection import (
    FactoryCockpitOverlay, project_factory_cockpit,
)
from bilqis_mlx.runtime.akasha_factory_ledger import rebuild_factory_ledger
from bilqis_mlx.runtime.tests.projection.akasha.test_factory_ledger import _fixture


class FactoryCockpitProjectionTests(unittest.TestCase):
    def test_authorized_ledger_projects_full_release_candidate_and_topology_truth(self):
        releases, candidates, lifecycle, checkpoints = _fixture()
        projection = rebuild_factory_ledger(releases, candidates, lifecycle, checkpoints)
        first, second = releases
        blocker = FactoryBlocker(
            "issue:#320", "evidence:topology-review", "Historical topology review required")
        records = project_factory_cockpit(
            projection,
            materialized_at=200,
            current_factory_release_sha256=second.factory_release_sha256,
            overlays=(FactoryCockpitOverlay(
                first.factory_release_sha256,
                FactoryDeliveryStatus.BLOCKED,
                (blocker,),
                qualification_receipt_sha256="9" * 64,
                admission_receipt_sha256="a" * 64,
            ),),
        )

        releases_by_sha = {
            item.factory_release_sha256: item for item in records
            if item.candidate_sha256 is None
        }
        first_row = releases_by_sha[first.factory_release_sha256]
        second_row = releases_by_sha[second.factory_release_sha256]
        candidate_row = next(item for item in records if item.candidate_sha256 is not None)

        self.assertEqual(first_row.admission_authority, FactoryAdmissionAuthority.HUMAN_ONLY)
        self.assertEqual(first_row.delivery_status, FactoryDeliveryStatus.BLOCKED)
        self.assertEqual(first_row.blockers, (blocker,))
        self.assertEqual(first_row.currency_state, FactoryCurrencyState.STALE)
        self.assertIn(("B.C0", "A.C0"), first_row.dependency_edges)
        self.assertEqual(tuple(item.grade_id for item in first_row.grade_frontier), ("A", "B"))
        self.assertEqual(first_row.lineage[0].topology.knowledge, FactoryTopologyKnowledge.EXACT)
        self.assertEqual(first_row.lineage[0].topology.model_dimension, 768)
        self.assertEqual(second_row.currency_state, FactoryCurrencyState.CURRENT)
        self.assertEqual(
            second_row.lineage[0].topology.knowledge,
            FactoryTopologyKnowledge.HISTORICAL_COMPATIBILITY_REQUIRED,
        )
        self.assertIsNotNone(second_row.lineage[0].topology.compatibility_ref)
        self.assertEqual(candidate_row.factory_release_sha256, first.factory_release_sha256)
        self.assertIn(first.artifact_receipt_sha256, first_row.receipt_refs)


if __name__ == "__main__":
    unittest.main()
