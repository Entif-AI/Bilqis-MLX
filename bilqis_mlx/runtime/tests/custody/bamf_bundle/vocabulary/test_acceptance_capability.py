"""A02 admission capability must stay paired with its immutable evidence."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    candidate_identity_digest, mint_parameter_extension_binding,
)
from bilqis_mlx.learning._atlas_candidate.state import (
    _issue_parameter_extension_state,
)
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle._vocabulary_admission_records import (
    DECISION_SCHEMA, EVENT, VocabularyAdmissionDecision,
    issue_vocabulary_admission_decision,
)
from bilqis_mlx.runtime.bamf_bundle.publication import _require_acceptance
from bilqis_mlx.runtime.bamf_bundle.records import canonical, sha
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    FIXTURE_PARENT_MANIFEST, candidate, parent_state,
)
from bilqis_mlx.vocabulary_growth import digest as semantic_digest


class A02AcceptanceCapabilityTests(unittest.TestCase):
    def test_parameter_extension_cannot_mutate_existing_optimizer_rows(self):
        state = parent_state()
        name = "identity.bank.0"
        parameters = dict(state.optimizer.parameters)
        changed = mx.array(parameters[name])
        changed[0, 0] = changed[0, 0] + 1
        parameters[name] = changed
        altered = AdamWStateTree(
            parameters, state.optimizer.m, state.optimizer.v,
            state.optimizer.update_counts)
        with self.assertRaises(BilqisError):
            _issue_parameter_extension_state(state, altered, state.policy)

    def test_free_form_decision_issuer_is_rejected(self):
        with self.assertRaises(BilqisError):
            issue_vocabulary_admission_decision(object())

    def _candidate_and_binding(self):
        state = parent_state()
        base = candidate(state, 1, FIXTURE_PARENT_MANIFEST)
        extents = replace(
            base.extents, semantic_bank_count=2,
            active_semantic_digest="8" * 64)
        mirror = {"rows": [{"semantic_id": "urn:concept:8192"}]}
        resource = {"required_available_bytes_lower_bound": 140_000_000_000}
        decision = object.__new__(VocabularyAdmissionDecision)
        for name, value in (
                ("run_id", base.run_id), ("generation", base.generation),
                ("parent_manifest_sha256", FIXTURE_PARENT_MANIFEST),
                ("parent_feature_receipt_sha256", "1" * 64),
                ("source_allocation_sha256", "2" * 64),
                ("prepared_extents_sha256", extents.digest),
                ("active_mask_sha256", "3" * 64),
                ("registry_mirror_sha256", semantic_digest(mirror)),
                ("resource_estimate_sha256", sha(canonical(resource))),
                ("candidate_identity_sha256", candidate_identity_digest(state)),
                ("parent_candidate_identity_sha256", "4" * 64),
                ("feature_sha256", extents.factor_map_digest),
                ("accepted", True), ("schema_version", DECISION_SCHEMA),
                ("_issuance", None)):
            object.__setattr__(decision, name, value)
        event = {
            "event": EVENT,
            "decision": decision.to_record(),
            "decision_sha256": decision.digest,
            "plan": {
                "source_allocation_digest": decision.source_allocation_sha256,
                "bank_count": extents.semantic_bank_count,
                "active_semantic_digest": extents.active_semantic_digest,
            },
            "registry_mirror": mirror,
            "resource_estimate": resource,
        }
        bundle = replace(
            base, extents=extents,
            semantic_abi={
                **base.semantic_abi,
                "active_set_sha256": extents.active_semantic_digest,
                "semantic_bank_count": extents.semantic_bank_count,
                "bank_identities": ["bank:0", "bank:1"],
            },
            transition={
                "schema": "bilqis.mlx.bamf-generation-transition/v1",
                "kind": "PARAMETER_EXTENSION",
                "invalidate_derived_caches": True,
            },
            outbox=(event,),
        )
        with patch(
                "bilqis_mlx.runtime.bamf_bundle._vocabulary_admission_records."
                "live_vocabulary_admission_decision", return_value=True):
            binding = mint_parameter_extension_binding(decision, state)
        return bundle, binding

    def test_rejects_binding_replayed_with_altered_admission_plan(self):
        bundle, binding = self._candidate_and_binding()
        event = dict(bundle.outbox[0])
        event["plan"] = {
            **event["plan"], "source_allocation_digest": "f" * 64}
        altered = replace(bundle, outbox=(event,))
        with self.assertRaises(BilqisError):
            _require_acceptance(altered, binding)


if __name__ == "__main__":
    unittest.main()
