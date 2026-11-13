"""Literal #955 mixed-lifecycle same-v2-lease witness."""
import os
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.atlas_admission import (
    adopt_capability_only_atlas_successor_v2,
    adopt_parameter_extension_atlas_successor_v2,
    read_accepted_atlas_factory_release,
)
from bilqis_mlx.runtime.atlas_admission_policy_v2 import AtlasDeltaEnvelopeV2
from bilqis_mlx.runtime.bamf_bundle.atlas_admission import ParsedAtlasAdmissionBinding
from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import (
    accepted_binding_for_manifest, accepted_generation,
)
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
from bilqis_mlx.runtime.bamf_bundle.factory_release.admission import (
    ParsedFactoryReleaseAdmissionBinding,
)
from bilqis_mlx.runtime.tests.admission.atlas.v2.mixed_witness_support import MixedWitnessSupport


@unittest.skipUnless(
    os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
    "full same-v2-lease mixed witness is explicitly gated",
)
class MixedSameLeaseV2Tests(MixedWitnessSupport, unittest.TestCase):
    def test_fixture_worlds_share_one_semantic_release_and_real_genesis(self):
        staged = self.zero_id_stage()
        handoff, _plan, _learner = self.capability_handoff(staged)
        snapshot, event_candidate, schema, features = self.common_atlas()
        self.assertEqual(handoff.receipt.selection_snapshot.semantic_release,
                         snapshot.release_sha256)
        self.assertEqual(event_candidate.census.semantic_release, snapshot.release_sha256)
        pointer = self.publish_matching_genesis(snapshot, schema, features)
        self.assertEqual(pointer["generation"], 0)
        self.assertEqual(staged.successor.semantic_catalog, self.current.semantic_catalog)

    def test_real_capability_only_n_plus_1_uses_persisted_v2_lease(self):
        staged = self.zero_id_stage()
        handoff, plan, learner = self.capability_handoff(staged)
        snapshot, event_candidate, schema, features = self.common_atlas()
        self.publish_matching_genesis(snapshot, schema, features)
        approval, lease, source_authority = self.issue_mixed_lease(
            handoff, event_candidate, snapshot)
        current = self.capability_context(
            handoff, plan, learner, approval, source_authority)
        combined = self.combined_source_registry()
        with self.z_operator_authority(staged), patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=combined), patch(
                    "bilqis_mlx.factory.live_answers.live_answer_registry",
                    return_value=self.answer_registry), self.source_replay(
                        snapshot, schema, features):
            result = adopt_capability_only_atlas_successor_v2(
                current, AtlasDeltaEnvelopeV2(handoff, None), lease)
        self.assertEqual(result.accepted_generation, 1)
        cold = read_accepted_atlas_factory_release(self.run)
        self.assertEqual(cold.release_sha256, staged.successor.release_sha256)
        pointer, accepted = accepted_generation(self.run / "bamf-state.json")
        binding = accepted_binding_for_manifest(
            self.run, pointer["manifest_sha256"], accepted,
            expected_acceptance_sha256=pointer["acceptance_sha256"])
        self.assertIsInstance(binding, ParsedFactoryReleaseAdmissionBinding)
        self.assertEqual(binding.lease_sha256, lease.digest())

    def test_same_v2_lease_spans_capability_cold_resume_and_real_a02(self):
        staged1 = self.zero_id_stage()
        h1, plan1, learner1 = self.capability_handoff(staged1)
        snapshot, event_candidate, schema, features = self.common_atlas()
        self.publish_matching_genesis(snapshot, schema, features)
        parent0, _parent0_manifest = load_bamf_generation_authority(
            self.run / "bamf-state.json")
        neural0 = self.neural_fingerprint(parent0)
        no_v1 = (
            patch("bilqis_mlx.runtime.atlas_admission.issue_atlas_lease",
                  side_effect=AssertionError("v1 lease issue forbidden")),
            patch("bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease",
                  side_effect=AssertionError("v1 accepted lease read forbidden")),
            patch("bilqis_mlx.runtime.atlas_admission._read_atlas_lease",
                  side_effect=AssertionError("v1 lease read forbidden")),
            patch("bilqis_mlx.runtime.atlas_admission._persist_atlas_lease_locked",
                  side_effect=AssertionError("v1 lease write forbidden")),
            patch("bilqis_mlx.runtime.atlas_lease_storage._read_atlas_lease",
                  side_effect=AssertionError("v1 lease storage read forbidden")),
            patch("bilqis_mlx.runtime.atlas_lease_storage._persist_atlas_lease_locked",
                  side_effect=AssertionError("v1 lease storage write forbidden")),
        )
        for guard in no_v1:
            guard.start()
            self.addCleanup(guard.stop)
        approval, lease, source_authority0 = self.issue_mixed_lease(
            h1, event_candidate, snapshot)
        current1 = self.capability_context(
            h1, plan1, learner1, approval, source_authority0)
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
        self.assertEqual(self.neural_fingerprint(accepted1), neural0)
        self.assertEqual(accepted1.semantic_abi, parent0.semantic_abi)
        self.assertEqual(accepted1.compiler_features, parent0.compiler_features)
        n1_fingerprint = self.run_fingerprint()
        with self.z_operator_authority(staged1), self.source_replay(
                snapshot, schema, features), patch(
                "bilqis_mlx.runtime.atlas_adoption_v2.advance_atlas_frontier_v2",
                side_effect=AssertionError("exact retry reached verifier")), patch(
                    "bilqis_mlx.runtime.atlas_capability_adoption_v2."
                    "publish_capability_only_factory_successor",
                    side_effect=AssertionError("exact retry reached publisher")):
            retry1 = adopt_capability_only_atlas_successor_v2(
                current1, AtlasDeltaEnvelopeV2(h1, None), lease)
        self.assertEqual(retry1.accepted_manifest_sha256, pointer1["manifest_sha256"])
        self.assertEqual(self.run_fingerprint(), n1_fingerprint)

        cold1 = read_accepted_atlas_factory_release(self.run)
        semantic_id, h2, plan2, ledger2, checkpoint2, step2 = self.event_handoff(cold1)
        self.assertEqual(h2.receipt.predecessor_release.release_sha256,
                         cold1.release_sha256)
        self.assertEqual(h2.receipt.selection_snapshot.semantic_release,
                         lease.source_approval.atlas_release_sha256)
        self.complete_parameter_leg(
            semantic_id=semantic_id, h2=h2, plan2=plan2, ledger2=ledger2,
            checkpoint2=checkpoint2, step2=step2, approval=approval, lease=lease,
            cold1=cold1, pointer1=pointer1, accepted1=accepted1, binding1=binding1,
            snapshot=snapshot, schema=schema, features=features, combined=combined)
