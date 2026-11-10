"""Concrete owner-issued A02 evidence consumed by the C07 production bridge."""
from dataclasses import fields, replace
from types import SimpleNamespace
import unittest

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.atlas_admission_policy import (
    PostAdmissionTotals, native_post_admission_totals,
    require_native_semantic_binding,
)
from bilqis_mlx.runtime.bamf_bundle import (
    A02VocabularyStagingReceipt, BamfBundleCandidate,
    require_issued_a02_staged_vocabulary_extension,
)
from bilqis_mlx.runtime.bamf_bundle._vocabulary_admission_records import (
    STAGED_EVENT, _issue_a02_staged_vocabulary_extension,
)
from bilqis_mlx.runtime.bamf_bundle.records import canonical, sha
from bilqis_mlx.runtime.model_topology_v2 import bamf_parameter_census
from bilqis_mlx.runtime.tests.admission.atlas.atlas_adoption_executor_support import (
    AtlasAdoptionExecutorFixture,
)
from bilqis_mlx.semantics.atlas.vocabulary_resources import (
    FP32_WEIGHT_AND_ADAMW_BYTES, RESOURCE_SCHEMA,
)


class AtlasProductionAdmissionTests(AtlasAdoptionExecutorFixture, unittest.TestCase):
    def _owner_issued_a02(self, semantic_id):
        _parent, base = self._native_parent_and_candidate()
        plan = {
            "allocations": ({"semantic_id": semantic_id},),
            "active_indices": (0,),
        }
        checkpoint_bytes = (
            bamf_parameter_census(base.topology, base.extents).total
            * FP32_WEIGHT_AND_ADAMW_BYTES)
        resource = {
            "previous_bank_count": 0,
            "next_bank_count": base.extents.semantic_bank_count,
            "added_bank_bytes": checkpoint_bytes,
            "complete_checkpoint_bytes_lower_bound": checkpoint_bytes,
            "disk_reserve_bytes": 0,
            "extra_planning_bytes": 0,
            "required_available_bytes_lower_bound": checkpoint_bytes,
            "schema_version": RESOURCE_SCHEMA,
        }
        receipt = A02VocabularyStagingReceipt(
            run_id=base.run_id,
            generation=base.generation,
            parent_manifest_sha256=base.parent_manifest_sha256,
            parent_feature_receipt_sha256="b" * 64,
            candidate_identity_sha256=candidate_identity_digest(base.retained_state),
            source_allocation_sha256="1" * 64,
            plan_sha256=sha(canonical(plan)),
            prepared_extents_sha256=base.extents.digest,
            active_mask_sha256="3" * 64,
            registry_mirror_sha256="4" * 64,
            resource_estimate_sha256=sha(canonical(resource)),
            active_set_sha256=base.extents.active_semantic_digest,
            feature_sha256=base.extents.factor_map_digest,
            semantic_bank_count=base.extents.semantic_bank_count,
        )
        event = {
            "event": STAGED_EVENT,
            "staging_receipt": receipt.to_record(),
            "plan": plan,
            "resource_estimate": resource,
        }
        values = {item.name: getattr(base, item.name) for item in fields(BamfBundleCandidate)}
        values["outbox"] = (event,)
        candidate = BamfBundleCandidate(**values)
        return _issue_a02_staged_vocabulary_extension(candidate, receipt)

    def test_owner_issued_a02_binds_factory_semantics_and_resource_totals(self):
        semantic_id = "urn:concept:fixture"
        staged = self._owner_issued_a02(semantic_id)
        self.assertIs(require_issued_a02_staged_vocabulary_extension(staged), staged)
        current = SimpleNamespace(semantic_catalog=())
        successor = SimpleNamespace(semantic_catalog=(semantic_id,))
        context = SimpleNamespace(current_release=current, native_staged=staged)
        proposal = SimpleNamespace(
            staged=SimpleNamespace(successor=successor), new_semantic_identities=1)

        self.assertIs(require_native_semantic_binding(context, proposal), staged)
        totals = native_post_admission_totals(staged)
        checkpoint_bytes = (
            bamf_parameter_census(staged.candidate.topology, staged.candidate.extents).total
            * FP32_WEIGHT_AND_ADAMW_BYTES)
        self.assertEqual(totals, PostAdmissionTotals(
            staged.candidate.extents.semantic_bank_count,
            staged.candidate.extents.motif_page_count,
            1, checkpoint_bytes, checkpoint_bytes))


if __name__ == "__main__":
    unittest.main()
