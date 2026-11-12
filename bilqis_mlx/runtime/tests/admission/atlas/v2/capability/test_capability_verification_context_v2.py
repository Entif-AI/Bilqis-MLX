"""Capability-only Atlas v2 context, rights, and implementation-drift tests."""

from bilqis_mlx.runtime.tests.admission.atlas.v2.capability.capability_support import *
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime


class CapabilityVerificationContextV2Tests(CapabilityV2Support):
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
