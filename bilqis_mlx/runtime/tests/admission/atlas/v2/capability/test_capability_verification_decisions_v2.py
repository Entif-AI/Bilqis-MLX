"""Capability-only Atlas v2 decision and release-authority tests."""

from bilqis_mlx.runtime.tests.admission.atlas.v2.capability.capability_support import *
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.runtime.atlas_admission_policy_v2 import _require_exact_atlas_release
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate,
    _closure,
)


class CapabilityVerificationDecisionV2Tests(CapabilityV2Support):
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
