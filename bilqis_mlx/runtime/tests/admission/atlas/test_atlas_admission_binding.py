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
    AtlasAdmissionBinding, _issue_atlas_admission_binding,
)
from bilqis_mlx.runtime.bamf_bundle.genesis import BamfRunIdentity
from bilqis_mlx.runtime.bamf_bundle.publication import _authorize_publication_candidate
from bilqis_mlx.runtime.atlas_admission import (
    persist_accepted_atlas_lease, read_accepted_atlas_lease,
)
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

    def test_lease_identity_is_a_projection_of_accepted_b13_birth_identity(self):
        parent, _staged = self._parent_and_candidate()
        projected = _accepted_lease_run_identity(parent.run_identity)
        self.assertEqual(projected.lineage_id, parent.run_identity.run_id)
        self.assertEqual(
            projected.initial_generation_digest,
            parent.run_identity.initial_candidate_identity_sha256)
        self.assertEqual(projected.topology_digest,
                         parent.run_identity.initial_topology_digest)
        self.assertEqual(projected.origin_checkpoint.sha256,
                         parent.run_identity.origin_checkpoint_sha256)
        self.assertEqual(projected.origin_checkpoint.filename,
                         parent.run_identity.origin_checkpoint_filename)
        self.assertEqual(projected.origin_checkpoint.optimizer_step,
                         parent.run_identity.origin_optimizer_step)

    def test_production_lease_persistence_replays_b13_identity_instead_of_trusting_lease(self):
        parent, _staged = self._parent_and_candidate()
        lease = replace(_lease(), run_identity=_accepted_lease_run_identity(
            parent.run_identity))
        with tempfile.TemporaryDirectory() as temporary, patch(
                "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                return_value=(parent, "a" * 64)):
            root = Path(temporary)
            persist_accepted_atlas_lease(root, lease, registry=_REGISTRY)
            self.assertEqual(read_accepted_atlas_lease(
                root, registry=_REGISTRY), lease)
            with self.assertRaises(BilqisError):
                persist_accepted_atlas_lease(
                    root, replace(lease, run_identity=replace(
                        lease.run_identity, lineage_id="wrong-run")),
                    registry=_REGISTRY)


if __name__ == "__main__":
    unittest.main()
