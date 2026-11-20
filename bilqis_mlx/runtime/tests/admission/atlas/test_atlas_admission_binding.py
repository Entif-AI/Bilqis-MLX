"""C07 admission authority is distinct from C05 retention acceptance."""
from dataclasses import fields, replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate, CompleteStudent
from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
    ATLAS_ADMISSION_SCHEMA_V2,
    ATLAS_ADMISSION_SCHEMA_V3,
    ATLAS_ADMISSION_SCHEMA_V4,
    AtlasAdmissionBinding, _issue_atlas_admission_binding,
)
from bilqis_mlx.runtime.bamf_bundle.genesis import BamfRunIdentity
from bilqis_mlx.runtime.bamf_bundle.publication import _authorize_publication_candidate
from bilqis_mlx.runtime.atlas_admission import (
    persist_accepted_atlas_lease, read_accepted_atlas_lease,
)
import bilqis_mlx.runtime.atlas_admission as atlas_admission
from bilqis_mlx.runtime.jit_adoption import _accepted_lease_run_identity
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _lease, _REGISTRY
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate, parent_state


class AtlasAdmissionBindingTests(unittest.TestCase):
    def _parent_and_candidate(self):
        identity = BamfRunIdentity(
            "fixture-run", 17, "1" * 64, "bundles/foundation-origin", 0,
            "2" * 64, "3" * 64, "4" * 64, "5" * 64, "6" * 64,
            "7" * 64, "fixture-source", "8" * 64, "fixture-teacher", 0)
        base = candidate(parent_state())
        values = {item.name: getattr(base, item.name) for item in fields(BamfBundleCandidate)}
        values["run_identity"] = identity
        parent = CompleteStudent(**values)
        staged = replace(
            base, generation=1, parent_manifest_sha256="a" * 64,
            transition={
                "schema": "bilqis.mlx.bamf-generation-transition/v1",
                "kind": "PARAMETER_EXTENSION",
                "invalidate_derived_caches": True,
            },
            run_identity=identity,
        )
        return parent, staged

    def test_only_owner_issuer_can_mint_live_admission_and_roundtrip_is_evidence_only(self):
        parent, staged = self._parent_and_candidate()
        with self.assertRaises(BilqisError):
            AtlasAdmissionBinding(
                staged.run_id, staged.generation,
                candidate_identity_digest(staged.retained_state),
                candidate_identity_digest(parent.retained_state),
                staged.extents.factor_map_digest, staged.retained_state.optimizer_step,
                "9" * 64, "8" * 64, "7" * 64, "6" * 64, "5" * 64, "4" * 64,
            )

        binding = _issue_atlas_admission_binding(
            staged, parent,
            lease_sha256="9" * 64,
            source_approval_sha256="8" * 64,
            proposal_sha256="7" * 64,
            factory_release_sha256="6" * 64,
            staging_receipt_sha256="5" * 64,
            parent_feature_receipt_sha256="4" * 64,
        )
        self.assertEqual(binding.candidate_identity_sha256,
                         candidate_identity_digest(staged.retained_state))
        self.assertEqual(binding.parent_candidate_identity_sha256,
                         candidate_identity_digest(parent.retained_state))
        self.assertEqual(binding.factory_release_sha256, "6" * 64)
        historical = AtlasAdmissionBinding.from_record(binding.to_record())
        self.assertNotEqual(type(historical), AtlasAdmissionBinding)
        self.assertEqual(historical.digest, binding.digest)

    def test_v2_binding_roundtrip_seals_selection_and_cumulative_obligation_keys(self):
        parent, staged = self._parent_and_candidate()
        keys = (("semantic:event", "2" * 64),)
        binding = _issue_atlas_admission_binding(
            staged, parent,
            lease_sha256="9" * 64,
            source_approval_sha256="8" * 64,
            proposal_sha256="7" * 64,
            factory_release_sha256="6" * 64,
            staging_receipt_sha256="5" * 64,
            parent_feature_receipt_sha256="4" * 64,
            selection_receipt_sha256="3" * 64,
            selected_obligation_keys=keys,
        )
        historical = AtlasAdmissionBinding.from_record(binding.to_record())
        self.assertEqual(binding.schema_version, ATLAS_ADMISSION_SCHEMA_V2)
        self.assertEqual(historical.selection_receipt_sha256, "3" * 64)
        self.assertEqual(historical.selected_obligation_keys, keys)
        self.assertEqual(historical.digest, binding.digest)

    def test_v3_binding_roundtrip_seals_generated_grade_and_predecessor(self):
        parent, staged = self._parent_and_candidate()
        keys = (("semantic:event", "2" * 64),)
        binding = _issue_atlas_admission_binding(
            staged, parent,
            lease_sha256="9" * 64,
            source_approval_sha256="8" * 64,
            proposal_sha256="7" * 64,
            factory_release_sha256="6" * 64,
            staging_receipt_sha256="5" * 64,
            parent_feature_receipt_sha256="4" * 64,
            selection_receipt_sha256="3" * 64,
            selected_obligation_keys=keys,
            predecessor_factory_release_sha256="b" * 64,
            generated_grade_proposal_sha256="c" * 64,
        )
        historical = AtlasAdmissionBinding.from_record(binding.to_record())
        self.assertEqual(binding.schema_version, ATLAS_ADMISSION_SCHEMA_V3)
        self.assertEqual(
            historical.predecessor_factory_release_sha256, "b" * 64)
        self.assertEqual(
            historical.generated_grade_proposal_sha256, "c" * 64)
        self.assertEqual(historical.digest, binding.digest)

    def test_cold_obligation_credit_is_minted_from_v2_b13_binding(self):
        from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_obligation_credit

        parent, staged = self._parent_and_candidate()
        keys = (("semantic:event", "2" * 64),)
        binding = _issue_atlas_admission_binding(
            staged, parent,
            lease_sha256="9" * 64,
            source_approval_sha256="8" * 64,
            proposal_sha256="7" * 64,
            factory_release_sha256="6" * 64,
            staging_receipt_sha256="5" * 64,
            parent_feature_receipt_sha256="4" * 64,
            selection_receipt_sha256="3" * 64,
            selected_obligation_keys=keys,
        )
        parsed = AtlasAdmissionBinding.from_record(binding.to_record())
        pointer = {
            "generation": 1,
            "manifest_sha256": "a" * 64,
            "acceptance_sha256": binding.digest,
        }
        accepted = CompleteStudent(**staged.__dict__)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                return_value=(pointer, accepted)), patch(
                    "bilqis_mlx.runtime.bamf_bundle.feature.acceptance."
                    "accepted_binding_for_manifest",
                    return_value=parsed), patch(
                        "bilqis_mlx.runtime.atlas_admission."
                        "read_accepted_atlas_factory_release",
                        return_value=type("Release", (), {
                            "release_sha256": "6" * 64})()):
            credit = read_accepted_atlas_obligation_credit(Path("/unused"))
        self.assertEqual(credit.factory_release_sha256, "6" * 64)
        self.assertEqual(credit.acceptance_sha256, binding.digest)
        self.assertEqual(credit.obligation_keys, keys)

    def test_cold_obligation_credit_is_minted_from_v4_b13_binding(self):
        from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_obligation_credit
        from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission_championship import (
            _parent_and_candidate as championship_parent_and_candidate,
        )

        parent, staged, _live = championship_parent_and_candidate()
        keys = (("semantic:event", "2" * 64),)
        binding = _issue_atlas_admission_binding(
            staged, parent,
            lease_sha256="9" * 64,
            source_approval_sha256="8" * 64,
            proposal_sha256="7" * 64,
            factory_release_sha256="6" * 64,
            staging_receipt_sha256="5" * 64,
            parent_feature_receipt_sha256="4" * 64,
            selection_receipt_sha256="3" * 64,
            selected_obligation_keys=keys,
        )
        self.assertEqual(binding.schema_version, ATLAS_ADMISSION_SCHEMA_V4)
        parsed = AtlasAdmissionBinding.from_record(binding.to_record())
        pointer = {
            "generation": 1,
            "manifest_sha256": "a" * 64,
            "acceptance_sha256": binding.digest,
        }
        accepted = CompleteStudent(**staged.__dict__)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                return_value=(pointer, accepted)), patch(
                    "bilqis_mlx.runtime.bamf_bundle.feature.acceptance."
                    "accepted_binding_for_manifest",
                    return_value=parsed), patch(
                        "bilqis_mlx.runtime.atlas_admission."
                        "read_accepted_atlas_factory_release",
                        return_value=type("Release", (), {
                            "release_sha256": "6" * 64})()):
            credit = read_accepted_atlas_obligation_credit(Path("/unused"))
        self.assertEqual(credit.factory_release_sha256, "6" * 64)
        self.assertEqual(credit.acceptance_sha256, binding.digest)
        self.assertEqual(credit.obligation_keys, keys)

    def test_b13_publication_accepts_live_c07_binding_without_relabeling_it_as_retention(self):
        parent, staged = self._parent_and_candidate()
        binding = _issue_atlas_admission_binding(
            staged, parent,
            lease_sha256="9" * 64,
            source_approval_sha256="8" * 64,
            proposal_sha256="7" * 64,
            factory_release_sha256="6" * 64,
            staging_receipt_sha256="5" * 64,
            parent_feature_receipt_sha256="4" * 64,
        )
        accepted, prepared, existing = _authorize_publication_candidate(
            Path("/unused"), staged, binding)
        self.assertIs(accepted, binding)
        self.assertIsNone(prepared)
        self.assertIsNone(existing)



if __name__ == "__main__":
    unittest.main()
