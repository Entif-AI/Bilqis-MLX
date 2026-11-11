"""Negative mixed-lifecycle lease and owner proofs for #955."""
from dataclasses import replace
import os
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.tests.test_atlas_salience import _signed
from bilqis_mlx.runtime.atlas_admission import (
    _accepted_run_lease_identity, issue_atlas_lease_v2,
    persist_accepted_atlas_lease_v2, renew_atlas_lease_v2,
    adopt_capability_only_atlas_successor_v2,
    adopt_parameter_extension_atlas_successor_v2,
    read_accepted_atlas_factory_release,
)
from bilqis_mlx.runtime.atlas_admission_policy_v2 import AtlasDeltaEnvelopeV2
from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import accepted_generation
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _lease as v1_lease
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _REGISTRY
from bilqis_mlx.runtime.tests.admission.atlas.v2.mixed_witness_support import MixedWitnessSupport


@unittest.skipUnless(
    os.environ.get("BILQIS_BAMF_FULL_WITNESS"),
    "full same-v2-lease mixed witness is explicitly gated",
)
class MixedSameLeaseNegativeTests(MixedWitnessSupport, unittest.TestCase):
    def _leg_two(self):
        staged1 = self.zero_id_stage()
        h1, plan1, learner1 = self.capability_handoff(staged1)
        snapshot, event_candidate, schema, features = self.common_atlas()
        self.publish_matching_genesis(snapshot, schema, features)
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
            adopt_capability_only_atlas_successor_v2(
                current1, AtlasDeltaEnvelopeV2(h1, None), lease)
        cold1 = read_accepted_atlas_factory_release(self.run)
        semantic_id, h2, plan2, ledger2, checkpoint2, step2 = self.event_handoff(cold1)
        native2 = self.stage_event_a02(snapshot, semantic_id)
        current2 = self.parameter_context(
            h2, plan2, ledger2, checkpoint2, step2, approval, native2,
            self.accepted_source_authority(), cold1)
        pointer1, _accepted1 = accepted_generation(self.run / "bamf-state.json")
        return (h1, h2, native2, current2, approval, lease, snapshot, schema,
                features, combined, pointer1)

    def _assert_pointer_unchanged(self, expected):
        actual, _accepted = accepted_generation(self.run / "bamf-state.json")
        self.assertEqual(actual, expected)

    def test_v1_and_unavailable_parameter_owner_fail_before_b13_mutation(self):
        (_h1, h2, native2, current2, _approval, lease, snapshot, schema,
         features, combined, pointer1) = self._leg_two()
        delta = AtlasDeltaEnvelopeV2(h2, native2)
        with self.source_replay(snapshot, schema, features), patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=combined), patch(
                    "bilqis_mlx.factory.live_answers.live_answer_registry",
                    return_value=self.answer_registry):
            with self.assertRaises(BilqisError) as v1_failure:
                adopt_parameter_extension_atlas_successor_v2(
                    current2, delta, v1_lease())
            self.assertEqual(
                v1_failure.exception.context["reason"],
                "BAMF_ATLAS_V2_ARGUMENT_INVALID")
            self._assert_pointer_unchanged(pointer1)
            unavailable = replace(
                current2, legacy=replace(current2.legacy, runtime=object()))
            with self.assertRaises(BilqisError) as owner_failure:
                adopt_parameter_extension_atlas_successor_v2(
                    unavailable, delta, lease)
            self.assertEqual(
                owner_failure.exception.context["reason"],
                "BAMF_ATLAS_V2_PARAMETER_OWNER_UNAVAILABLE")
            self._assert_pointer_unchanged(pointer1)

    def test_out_of_scope_and_different_persisted_v2_fail_before_b13_mutation(self):
        (h1, h2, native2, current2, approval, lease, snapshot, schema,
         features, combined, pointer1) = self._leg_two()
        run_identity = _accepted_run_lease_identity(self.run)
        scoped_approval = _signed(replace(
            approval, approval_id="mixed-v2-scope-negative",
            source_family_ids=tuple(h1.family_ids),
            operator_ids=tuple(h1.operator_ids), signature_hex="0" * 128))
        scoped = issue_atlas_lease_v2(
            "mixed-v2-scope-negative", run_identity, scoped_approval,
            lease.resource_ceiling, requested_at="2026-11-10T20:46:00Z",
            human_command_sha256="8" * 64, human_started=True, registry=_REGISTRY)
        renew_atlas_lease_v2(
            self.run, scoped, independently_loaded_run=run_identity,
            registry=_REGISTRY, expected_prior_lease_sha256=lease.digest(),
            human_started=True)
        delta = AtlasDeltaEnvelopeV2(h2, native2)
        scoped_current = replace(
            current2,
            legacy=replace(current2.legacy, source_approval=scoped_approval),
        )
        with self.source_replay(snapshot, schema, features), patch(
                "bilqis_mlx.source_adapters.school.live_source_registry",
                return_value=combined), patch(
                    "bilqis_mlx.factory.live_answers.live_answer_registry",
                    return_value=self.answer_registry):
            result = adopt_parameter_extension_atlas_successor_v2(
                scoped_current, delta, scoped)
        self.assertEqual(result.reason, "OUT_OF_LEASE_SCOPE")
        self._assert_pointer_unchanged(pointer1)

        different = issue_atlas_lease_v2(
            "mixed-v2-different", run_identity, approval, lease.resource_ceiling,
            requested_at="2026-11-10T20:47:00Z",
            human_command_sha256="7" * 64, human_started=True, registry=_REGISTRY)
        renew_atlas_lease_v2(
            self.run, different, independently_loaded_run=run_identity,
            registry=_REGISTRY, expected_prior_lease_sha256=scoped.digest(),
            human_started=True)
        with self.source_replay(snapshot, schema, features):
            with self.assertRaises(BilqisError) as failure:
                adopt_parameter_extension_atlas_successor_v2(
                    current2, delta, lease)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_ATLAS_V2_LEASE_CURRENT_AUTHORITY_DRIFT")
        self._assert_pointer_unchanged(pointer1)
