"""Literal C07.1a/#509 repeated-adoption closure witness."""
import os
import unittest
from unittest.mock import patch

from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.runtime.atlas_admission import (
    adopt_capability_only_atlas_successor_v2,
    read_accepted_atlas_factory_release,
)
from bilqis_mlx.runtime.atlas_admission_policy_v2 import AtlasDeltaEnvelopeV2
from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
    accepted_binding_for_manifest, accepted_generation,
)
from bilqis_mlx.runtime.bamf_bundle.factory_release.admission import (
    ParsedFactoryReleaseAdmissionBinding,
)
from bilqis_mlx.runtime.tests.admission.atlas.v2.mixed_witness_support import (
    MixedWitnessSupport,
)


@unittest.skipUnless(
    os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
    "full C07.1a repeated-adoption witness is explicitly gated",
)
class C07LeaseClosureV2Tests(MixedWitnessSupport, unittest.TestCase):
    def test_one_lease_admits_three_successors_and_cold_resumes_from_second(self):
        staged1 = self.zero_id_stage()
        h1, plan1, learner1 = self.capability_handoff(staged1)
        snapshot, event_candidate, schema, features = self.common_atlas()
        self.publish_matching_genesis(snapshot, schema, features)
        approval, lease, source_authority = self.issue_mixed_lease(
            h1, event_candidate, snapshot,
            event_capabilities=("D.EVENT_OCCURRENCE", "D.COMMENCEMENT"))
        current1 = self.capability_context(
            h1, plan1, learner1, approval, source_authority)
        combined = self.combined_source_registry()

        with self.z_operator_authority(staged1), patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=combined), patch(
                    "bilqis_mlx.factory.live_answers.live_answer_registry",
                    return_value=self.answer_registry), self.source_replay(
                        snapshot, schema, features):
            result1 = adopt_capability_only_atlas_successor_v2(
                current1, AtlasDeltaEnvelopeV2(h1, None), lease)
        self.assertEqual(result1.accepted_generation, 1)
        pointer1, accepted1 = accepted_generation(self.run / "bamf-state.json")
        binding1 = accepted_binding_for_manifest(
            self.run, pointer1["manifest_sha256"], accepted1,
            expected_acceptance_sha256=pointer1["acceptance_sha256"])
        self.assertIsInstance(binding1, ParsedFactoryReleaseAdmissionBinding)
        self.assertEqual(binding1.lease_sha256, lease.digest())

        cold1 = read_accepted_atlas_factory_release(self.run)
        semantic2, h2, plan2, ledger2, checkpoint2, step2 = self.event_handoff(
            cold1, capability="D.EVENT_OCCURRENCE", mastered={"A.IDENTITY"})
        pointer2, accepted2, binding2 = self.complete_parameter_leg(
            semantic_id=semantic2, h2=h2, plan2=plan2, ledger2=ledger2,
            checkpoint2=checkpoint2, step2=step2, approval=approval, lease=lease,
            cold1=cold1, pointer1=pointer1, accepted1=accepted1, binding1=binding1,
            snapshot=snapshot, schema=schema, features=features, combined=combined,
            expected_generation=2)

        # The third delta starts only from a fresh read of accepted generation 2.
        cold2 = read_accepted_atlas_factory_release(self.run)
        self.assertEqual(cold2.release_sha256, h2.staged_candidate.successor.release_sha256)
        graph2 = candidate_realizations.admitted_candidate_graph(
            h2.staged_candidate, self.parent_graph)
        semantic3, h3, plan3, ledger3, checkpoint3, step3 = self.event_handoff(
            cold2, capability="D.COMMENCEMENT",
            mastered={"A.IDENTITY", "D.EVENT_OCCURRENCE"}, graph=graph2)
        self.assertEqual(
            h3.staged_candidate.successor.transition.added_capabilities,
            ("D.COMMENCEMENT",))
        pointer3, accepted3, binding3 = self.complete_parameter_leg(
            semantic_id=semantic3, h2=h3, plan2=plan3, ledger2=ledger3,
            checkpoint2=checkpoint3, step2=step3, approval=approval, lease=lease,
            cold1=cold2, pointer1=pointer2, accepted1=accepted2, binding1=binding2,
            snapshot=snapshot, schema=schema, features=features, combined=combined,
            expected_generation=3, graph=graph2)

        self.assertEqual(
            (binding1.lease_sha256, binding2.lease_sha256, binding3.lease_sha256),
            (lease.digest(), lease.digest(), lease.digest()))
        self.assertEqual(
            read_accepted_atlas_factory_release(self.run).release_sha256,
            h3.staged_candidate.successor.release_sha256)
        ages = tuple(item.identity for item in accepted3.retained_state.policy.row_ages)
        self.assertEqual(ages.count(semantic2), 1)
        self.assertEqual(ages.count(semantic3), 1)


if __name__ == "__main__":
    unittest.main()
