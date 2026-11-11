"""Capability-only Atlas v2 verifier contract tests."""

from bilqis_mlx.runtime.tests.admission.atlas.v2.capability_support import *
from bilqis_mlx.runtime.atlas_admission_policy_v2 import _require_exact_atlas_release


class CapabilityVerificationV2Tests(CapabilityV2Support):
    def test_real_z_c6_zero_id_handoff_is_verified_without_a02(self):
        handoff = self._handoff()
        self.assertEqual(handoff.receipt.selection.introduced_semantic_ids, ())
        self.assertEqual(handoff.receipt.selection.introduced_capability_ids, ("Z.C6",))
        self.assertTrue(handoff.proposal.deferred_candidate_ids)
        approval, lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        facts = AtlasDerivedAdmissionFactsV2(1, 1, 1, 0, 0, 0)

        with patch(
                "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"), \
                patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_exact_atlas_release"), \
                patch(
                    "bilqis_mlx.runtime.atlas_capability_facts_v2."
                    "read_capability_only_admission_facts_v2",
                    return_value=facts), \
                patch(
                    "bilqis_mlx.runtime.jit_adoption.verify_current_implementations"), \
                patch(
                    "bilqis_mlx.runtime.jit_adoption._authenticate_native_staged_candidate"
                ) as a02_auth:
            result = advance_atlas_frontier_v2(
                current, AtlasDeltaEnvelopeV2(handoff, None), lease)

        self.assertEqual(result.status.value, "STAGED")
        self.assertEqual(result.reason, "V2_CAPABILITY_ONLY_AUTHORITY_VERIFIED")
        self.assertEqual(result.lease_sha256, lease.digest())
        self.assertEqual(
            result.staged_successor_sha256,
            handoff.staged_candidate.successor.release_sha256,
        )
        a02_auth.assert_not_called()

    def test_zero_id_handoff_rejects_any_a02_staging_object(self):
        handoff = self._handoff()
        approval, lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        helper = object.__new__(AtlasAdoptionExecutorFixture)
        _parent, candidate = AtlasAdoptionExecutorFixture._native_parent_and_candidate(helper)
        native = AtlasAdoptionExecutorFixture._a02_staged(
            helper, candidate, semantic_id="urn:foreign:should-not-exist")

        with patch(
                "bilqis_mlx.runtime.jit_adoption._authenticate_native_staged_candidate"
                ) as a02_auth, self.assertRaises(BilqisError) as caught:
            advance_atlas_frontier_v2(
                current, AtlasDeltaEnvelopeV2(handoff, native), lease)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_DELTA_INVALID",
        )
        a02_auth.assert_not_called()

    def test_capability_only_rejects_signed_approval_for_different_atlas_release(self):
        handoff = self._handoff()
        approval, lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        semantic_release = handoff.receipt.selection_snapshot.semantic_release
        foreign_approval = replace(
            approval,
            atlas_release_sha256="f" * 64,
        )
        foreign_lease = replace(lease, source_approval=foreign_approval)
        accepted_feature_context = SimpleNamespace(
            receipt=SimpleNamespace(source_release_sha256=semantic_release),
            features=SimpleNamespace(semantic_release=semantic_release),
        )
        with patch(
                "bilqis_mlx.runtime.bamf_bundle."
                "read_accepted_generation_feature_context",
                return_value=accepted_feature_context), \
                self.assertRaises(BilqisError) as caught:
            _require_exact_atlas_release(current, handoff, foreign_lease)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_RELEASE_AUTHORITY_DRIFT",
        )

    def test_v2_context_pair_is_all_or_none_and_does_not_relax_legacy_triple(self):
        handoff = self._handoff()
        approval, _lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        AtlasAdmissionContextV2(current.legacy, current.run_dir)
        AtlasAdmissionContextV2(
            current.legacy, current.run_dir, runtime=object(), source_authority=object())
        with self.assertRaises(BilqisError):
            AtlasAdmissionContextV2(
                current.legacy, current.run_dir, runtime=object())
