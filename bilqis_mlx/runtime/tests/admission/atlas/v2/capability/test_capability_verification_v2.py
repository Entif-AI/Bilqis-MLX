"""Capability-only Atlas v2 verifier contract tests."""

from bilqis_mlx.runtime.tests.admission.atlas.v2.capability.capability_support import *
from bilqis_mlx.runtime.atlas_admission_policy_v2 import replay_atlas_delta_scope_handoff_v2
from bilqis_mlx.runtime.atlas_capability_facts_v2 import (
    read_capability_only_admission_facts_v2,
)


class CapabilityVerificationV2Tests(CapabilityV2Support):
    def test_real_z_c6_replay_uses_exact_nonempty_sorted_reserve_set(self):
        handoff = self._handoff()
        approval, _lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        expected = tuple(sorted(
            item.candidate_id for item in handoff.candidate_frontier.candidates
            if item.candidate_id != handoff.staged_candidate.candidate_id
        ))

        self.assertTrue(expected)
        self.assertEqual(handoff.proposal.deferred_candidate_ids, expected)
        self.assertEqual(
            replay_atlas_delta_scope_handoff_v2(current, handoff),
            handoff.staged_candidate,
        )

    def test_v2_replay_rejects_removed_added_and_substituted_reserve_ids(self):
        handoff = self._handoff()
        approval, _lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        deferred = handoff.proposal.deferred_candidate_ids
        self.assertTrue(deferred)
        foreign = "candidate:foreign-reserve"
        variants = (
            ("removed", deferred[1:]),
            ("added", deferred + (foreign,)),
            ("substituted", (foreign,) + deferred[1:]),
        )

        for label, changed_ids in variants:
            proposal = self._rehash_proposal(
                handoff.proposal,
                deferred_candidate_ids=changed_ids,
            )
            forged = self._rehash_handoff(handoff, proposal=proposal)
            with self.subTest(label=label), self.assertRaises(BilqisError) as caught:
                replay_atlas_delta_scope_handoff_v2(current, forged)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_ATLAS_V2_PROPOSAL_CONTEXT_DRIFT",
            )

    def test_v2_replay_rejects_selected_candidate_substitution(self):
        handoff = self._handoff()
        approval, _lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        reserve = handoff.proposal.deferred_candidate_ids[0]
        proposal = self._rehash_proposal(
            handoff.proposal,
            selected_candidate_ids=(reserve,),
        )
        forged = self._rehash_handoff(handoff, proposal=proposal)

        with self.assertRaises(BilqisError) as caught:
            replay_atlas_delta_scope_handoff_v2(current, forged)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_DELTA_SCOPE_HANDOFF_DRIFT",
        )

    def test_zero_id_fact_helper_returns_exact_accepted_parent_values(self):
        handoff = self._handoff()
        semantic_release = handoff.receipt.selection_snapshot.semantic_release
        active_digest = "a" * 64
        parent_manifest = "b" * 64
        parent = SimpleNamespace(
            topology=object(),
            compiler_features=object(),
            extents=SimpleNamespace(
                semantic_bank_count=3,
                motif_page_count=4,
                active_semantic_digest=active_digest,
            ),
        )
        feature_context = SimpleNamespace(
            receipt=SimpleNamespace(
                generation_manifest_sha256=parent_manifest,
                active_set_sha256=active_digest,
            ),
            features=SimpleNamespace(semantic_release=semantic_release),
        )
        selection = SimpleNamespace(release_sha256=semantic_release)
        snapshot = SimpleNamespace(active_set_sha256=active_digest)

        with patch(
                "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                return_value=(parent, parent_manifest)), patch(
                "bilqis_mlx.runtime.bamf_bundle."
                "read_accepted_generation_feature_context",
                return_value=feature_context), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.replay_support.feature_source",
                return_value=object()), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.replay_support.artifact_identity",
                return_value=object()), patch(
                "bilqis_mlx.semantics.atlas.snapshot.resolve_atlas_artifact_selection",
                return_value=selection), patch(
                "bilqis_mlx.semantics.atlas.snapshot.load_pinned_atlas_snapshot",
                return_value=snapshot), patch(
                "bilqis_mlx.runtime.bamf_bundle.vocabulary.admission_facts."
                "accepted_active_semantic_ids",
                return_value=("a", "b", "c", "d", "e")), patch(
                "bilqis_mlx.runtime.model_topology_v2.bamf_parameter_census",
                return_value=SimpleNamespace(total=7)):
            facts = read_capability_only_admission_facts_v2(
                Path("/accepted/run"), handoff)

        self.assertEqual(
            facts,
            AtlasDerivedAdmissionFactsV2(3, 4, 5, 84, 84, 0),
        )

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
