"""Capability-only Atlas v2 verifier contract tests."""

from bilqis_mlx.runtime.tests.admission.atlas.v2.capability_support import *
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime
from bilqis_mlx.runtime.atlas_admission_policy_v2 import (
    _require_exact_atlas_release,
    replay_atlas_delta_scope_handoff_v2,
)
from bilqis_mlx.runtime.atlas_capability_facts_v2 import (
    read_capability_only_admission_facts_v2,
)
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import (
    rehash,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate,
    _closure,
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

    def test_grade_label_permutation_and_symmetric_debt_preserve_v2_admission_decision(self):
        def run_case(label, debt):
            snapshot = rehash(
                self.snapshot,
                grade_labels=(label,),
                retained_mastery_debt=(debt,),
                retained_debt_source_sha256="d" * 64,
            )
            closure = _closure(
                snapshot,
                tuple(
                    _candidate(snapshot, identity)
                    for identity in snapshot.source_eligible_concept_ids
                ),
            )
            with patch.object(self, "snapshot", snapshot), patch.object(
                self, "closure", closure
            ):
                handoff = self._handoff()
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
                        "bilqis_mlx.runtime.jit_adoption.verify_current_implementations"):
                result = advance_atlas_frontier_v2(
                    current, AtlasDeltaEnvelopeV2(handoff, None), lease)
            return snapshot, handoff, lease, result

        left = run_case("A", "Z.C0")
        right = run_case("B", "Z.C1")
        left_snapshot, left_handoff, left_lease, left_result = left
        right_snapshot, right_handoff, right_lease, right_result = right

        self.assertEqual(left_snapshot.grade_labels, ("A",))
        self.assertEqual(right_snapshot.grade_labels, ("B",))
        self.assertEqual(left_snapshot.retained_mastery_debt, ("Z.C0",))
        self.assertEqual(right_snapshot.retained_mastery_debt, ("Z.C1",))
        self.assertNotEqual(
            left_snapshot.snapshot_sha256,
            right_snapshot.snapshot_sha256,
        )
        self.assertEqual(
            left_handoff.receipt.selection.selected_semantic_id,
            right_handoff.receipt.selection.selected_semantic_id,
        )
        self.assertEqual(left_handoff.proposal, right_handoff.proposal)
        self.assertEqual(
            left_handoff.staged_candidate,
            right_handoff.staged_candidate,
        )
        self.assertEqual(left_lease.digest(), right_lease.digest())
        self.assertEqual(left_result, right_result)
        self.assertIs(left_result.status, AdmissionStatus.STAGED)
        self.assertEqual(
            left_result.reason,
            "V2_CAPABILITY_ONLY_AUTHORITY_VERIFIED",
        )
        self.assertEqual(left_result.lease_sha256, left_lease.digest())
        self.assertEqual(left_result.actual_neural_updates, 0)

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
        foreign_approval = _signed(replace(
            approval,
            atlas_release_sha256="f" * 64,
            signature_hex="0" * 128,
        ))
        foreign_approval.verify_signature(current.legacy.registry)
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
        with self.assertRaises(BilqisError):
            AtlasAdmissionContextV2(
                current.legacy, current.run_dir, source_authority=object())

    def test_legacy_partial_production_triple_still_rejects_before_v2_wrapping(self):
        handoff = self._handoff()
        approval, _lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)

        with self.assertRaises(BilqisError) as caught:
            replace(
                current.legacy,
                runtime=object(),
                native_staged=None,
                source_authority=object(),
            )

        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_ADMISSION_CONTEXT_INVALID",
        )

    def test_v2_production_pair_rejects_any_legacy_production_triple(self):
        handoff = self._handoff()
        approval, _lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        helper = object.__new__(AtlasAdoptionExecutorFixture)
        _parent, candidate = AtlasAdoptionExecutorFixture._native_parent_and_candidate(helper)
        native = AtlasAdoptionExecutorFixture._a02_staged(
            helper, candidate, semantic_id="urn:fixture:v2-context")
        legacy_runtime = _PreparedSuccessorRuntime(
            None, current.run_dir, {}, None, None, {}, object(), object(), 0.)
        legacy = replace(
            current.legacy,
            runtime=legacy_runtime,
            native_staged=native,
            source_authority=object(),
        )

        with self.assertRaises(BilqisError) as caught:
            AtlasAdmissionContextV2(
                legacy,
                current.run_dir,
                runtime=object(),
                source_authority=object(),
            )

        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_CONTEXT_INVALID",
        )

    def test_v2_production_pair_requires_legacy_implementation_registries(self):
        handoff = self._handoff()
        approval, _lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        legacy_without_registries = replace(
            current.legacy,
            source_registry=None,
            answer_registry=None,
        )

        with self.assertRaises(BilqisError) as caught:
            AtlasAdmissionContextV2(
                legacy_without_registries,
                current.run_dir,
                runtime=object(),
                source_authority=object(),
            )

        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_V2_CONTEXT_INVALID",
        )

    def test_capability_only_rights_hold_is_preserved_before_success(self):
        handoff = self._handoff()
        approval, lease = self._lease_authority(handoff)
        held_approval = _signed(replace(
            approval,
            rights_compatible=False,
            signature_hex="0" * 128,
        ))
        held_lease = replace(lease, source_approval=held_approval)
        current = replace(
            self._context(handoff, held_approval),
            legacy=replace(
                self._context(handoff, held_approval).legacy,
                source_approval=held_approval,
            ),
        )
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
                    return_value=facts):
            result = advance_atlas_frontier_v2(
                current, AtlasDeltaEnvelopeV2(handoff, None), held_lease)

        self.assertEqual(result.reason, "SOURCE_OR_RIGHTS_HELD")

    def test_capability_only_source_and_answer_implementation_drift_fail_closed(self):
        handoff = self._handoff()
        approval, lease = self._lease_authority(handoff)
        current = self._context(handoff, approval)
        facts = AtlasDerivedAdmissionFactsV2(1, 1, 1, 0, 0, 0)
        expected = (
            ("JIT_ADOPTION_SOURCE_IMPLEMENTATION_DRIFT", "BAMF_ATLAS_SOURCE_IMPLEMENTATION_DRIFT"),
            ("JIT_ADOPTION_ANSWER_IMPLEMENTATION_DRIFT", "BAMF_ATLAS_ANSWER_IMPLEMENTATION_DRIFT"),
        )

        for raw, reason in expected:
            with self.subTest(raw=raw), patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._accepted_run_bindings"), patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_current_v2_lease"), patch(
                    "bilqis_mlx.runtime.atlas_admission_policy_v2._require_exact_atlas_release"), patch(
                    "bilqis_mlx.runtime.atlas_capability_facts_v2."
                    "read_capability_only_admission_facts_v2",
                    return_value=facts), patch(
                    "bilqis_mlx.runtime.jit_adoption.verify_current_implementations",
                    side_effect=ValueError(raw)), self.assertRaises(BilqisError) as caught:
                advance_atlas_frontier_v2(
                    current, AtlasDeltaEnvelopeV2(handoff, None), lease)
            self.assertEqual(caught.exception.context["reason"], reason)
