"""Focused CP02/CP03 contract proofs for the read-only Factory cockpit."""
import unittest

from bilqis_mlx.mission_control.contracts.codec import decode_record, encode_record
from bilqis_mlx.mission_control.contracts.factory import (
    FactoryAdmissionAuthority, FactoryBlocker, FactoryCockpitSnapshot,
    FactoryCurrencyState, FactoryDeliveryStatus, FactoryGradeFrontier,
    FactoryLifecycleStatus, FactoryRunLineage, FactorySubjectKind,
    FactoryTopologyEvidence, FactoryTopologyKnowledge,
)
from bilqis_mlx.mission_control.contracts.model import (
    AuthorityClass, CoverageState, MissionControlContractError, RecordMeta,
)
from bilqis_mlx.mission_control.query_catalog import MissionControlQueryCatalog
from bilqis_mlx.mission_control.query_contracts import QueryFamily, QueryRequest


D = {char: char * 64 for char in "123456789abcdef"}


def exact_topology():
    return FactoryTopologyEvidence(
        FactoryTopologyKnowledge.EXACT,
        "bilqis.akasha.factory-topology-view/v1",
        "bilqis.mlx.model-topology/v2",
        D["4"], "bamf-atlas-v2", 12, 16, 8, 768, 3072, 1024, None,
    )


def row(*, blocked=False):
    meta = RecordMeta(
        "factory-release:" + D["1"], None, 10, None, None,
        CoverageState.COMPLETE, AuthorityClass.DERIVED,
        ("akasha-factory-ledger:" + D["2"],), (), (D["3"],),
    )
    blockers = ((FactoryBlocker("issue:#320", "evidence:topology", "waiting"),)
                if blocked else ())
    return FactoryCockpitSnapshot(
        meta, FactorySubjectKind.FACTORY_RELEASE, D["1"], D["1"], None, D["2"],
        FactoryLifecycleStatus.ADMITTED,
        FactoryDeliveryStatus.BLOCKED if blocked else FactoryDeliveryStatus.LAUNCH_QUALIFIED,
        FactoryCurrencyState.CURRENT, FactoryAdmissionAuthority.HUMAN_ONLY,
        (FactoryGradeFrontier("B", ("B.AND",)),),
        ("B.AND",),
        (("B.AND", "A.IDENTITY"),),  # cross-scope prerequisite is lawful Factory evidence
        blockers, (), (), (D["3"],), D["5"], D["6"],
        (FactoryRunLineage(
            "run-7", "lineage-7", 7, D["7"], D["8"], D["9"], exact_topology()),),
    )


class FactoryCockpitContractTests(unittest.TestCase):
    def test_round_trip_preserves_global_read_model_and_exact_topology(self):
        source = row()
        restored = decode_record(encode_record(source))
        self.assertEqual(restored, source)
        self.assertIsNone(restored.meta.run)
        self.assertEqual(restored.lineage[0].topology.model_dimension, 768)

    def test_blocker_requires_blocked_delivery_and_owner_evidence(self):
        blocked = row(blocked=True)
        self.assertEqual(blocked.blockers[0].owner_ref, "issue:#320")
        with self.assertRaises(MissionControlContractError):
            FactoryCockpitSnapshot(
                blocked.meta, blocked.subject_kind, blocked.subject_sha256,
                blocked.factory_release_sha256, blocked.candidate_sha256,
                blocked.semantic_release_sha256, blocked.lifecycle_state,
                FactoryDeliveryStatus.INTEGRATED, blocked.currency_state,
                blocked.admission_authority, blocked.grade_frontier,
                blocked.capability_ids, blocked.dependency_edges, blocked.blockers,
                blocked.promoted_capability_ids, blocked.debt_capability_ids,
                blocked.receipt_refs, blocked.qualification_receipt_sha256,
                blocked.admission_receipt_sha256, blocked.lineage,
            )

    def test_factory_query_does_not_require_fake_run_binding(self):
        source = row()
        catalog = MissionControlQueryCatalog((source,))
        self.assertEqual(
            catalog.query(QueryRequest(QueryFamily.FACTORY)).records, (source,))
        self.assertEqual(
            catalog.query(QueryRequest(
                QueryFamily.RECORD, reference=source.admission_receipt_sha256)).records,
            (source,),
        )


if __name__ == "__main__":
    unittest.main()
