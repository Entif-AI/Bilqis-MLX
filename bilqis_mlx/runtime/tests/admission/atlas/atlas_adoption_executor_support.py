"""Shared C07 executor fixtures for typed A02/B13 adoption tests."""
from dataclasses import fields, replace

from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.jit_curriculum import propose_curriculum_delta
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.bamf_bundle import (
    A02VocabularyStagingReceipt, BamfBundleCandidate, CompleteStudent,
)
from bilqis_mlx.runtime.bamf_bundle._vocabulary_admission_records import (
    STAGED_EVENT, _issue_a02_staged_vocabulary_extension,
)
from bilqis_mlx.runtime.bamf_bundle.records import canonical, sha
from bilqis_mlx.runtime.bamf_bundle.genesis import BamfRunIdentity
from bilqis_mlx.runtime.jit_adoption import _PreparedSuccessorRuntime
from bilqis_mlx.runtime.tests.admission.prepared_successor_fixtures import (
    PreparedSuccessorFixture,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate, parent_state
from bilqis_mlx.semantics.atlas.vocabulary_resources import RESOURCE_SCHEMA


class AtlasAdoptionExecutorFixture(PreparedSuccessorFixture):
    def _native_parent_and_candidate(self):
        identity = BamfRunIdentity(
            "fixture-run", 17, "1" * 64, "bundles/foundation-origin", 0,
            "2" * 64, "3" * 64, "4" * 64, "5" * 64, "6" * 64,
            "7" * 64, "fixture-source", "8" * 64, "fixture-teacher", 0)
        base = candidate(parent_state())
        values = {
            item.name: getattr(base, item.name) for item in fields(BamfBundleCandidate)
        }
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

    def _a02_staged(
            self, candidate, *, parent_feature="b" * 64,
            required_available_bytes=1):
        resource = {
            "previous_bank_count": max(candidate.extents.semantic_bank_count - 1, 0),
            "next_bank_count": candidate.extents.semantic_bank_count,
            "added_bank_bytes": 0,
            "complete_checkpoint_bytes_lower_bound": required_available_bytes,
            "disk_reserve_bytes": 0,
            "extra_planning_bytes": 0,
            "required_available_bytes_lower_bound": required_available_bytes,
            "schema_version": RESOURCE_SCHEMA,
        }
        receipt = A02VocabularyStagingReceipt(
            run_id=candidate.run_id,
            generation=candidate.generation,
            parent_manifest_sha256=candidate.parent_manifest_sha256,
            parent_feature_receipt_sha256=parent_feature,
            candidate_identity_sha256=candidate_identity_digest(
                candidate.retained_state),
            source_allocation_sha256="1" * 64,
            plan_sha256="2" * 64,
            prepared_extents_sha256=candidate.extents.digest,
            active_mask_sha256="3" * 64,
            registry_mirror_sha256="4" * 64,
            resource_estimate_sha256=sha(canonical(resource)),
            active_set_sha256=candidate.extents.active_semantic_digest,
            feature_sha256=candidate.extents.factor_map_digest,
            semantic_bank_count=candidate.extents.semantic_bank_count,
        )
        candidate = replace(candidate, outbox=({
            "event": STAGED_EVENT,
            "staging_receipt": receipt.to_record(),
            "resource_estimate": resource,
        },))
        return _issue_a02_staged_vocabulary_extension(candidate, receipt)

    def _proposal(self, staged):
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        proposal = propose_curriculum_delta(
            self.frontier, self.current, ledger, plan,
            self.checkpoint.sha256, self.checkpoint.optimizer_step,
            candidate_bindings=(staged.binding,))
        return plan, ledger, proposal

    def _runtime(self, mx=None):
        return _PreparedSuccessorRuntime(
            mx, self.root, self.receipt, None, None, self.graph,
            self.parameters, self.optimizer, 0.)
