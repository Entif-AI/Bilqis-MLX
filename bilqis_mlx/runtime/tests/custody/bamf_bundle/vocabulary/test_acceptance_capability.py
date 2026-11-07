"""A02 staging evidence grants no publication authority."""
from dataclasses import replace
import unittest

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning._atlas_candidate.state import _issue_parameter_extension_state
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle._vocabulary_admission_records import (
    A02StagedVocabularyExtension, A02VocabularyStagingReceipt,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    FIXTURE_PARENT_MANIFEST, candidate, parent_state,
)


class A02StagingCapabilityTests(unittest.TestCase):
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

    def test_staging_receipt_is_bound_to_the_exact_candidate(self):
        state = parent_state()
        bundle = candidate(state, 1, FIXTURE_PARENT_MANIFEST)
        receipt = A02VocabularyStagingReceipt(
            run_id=bundle.run_id, generation=bundle.generation,
            parent_manifest_sha256=FIXTURE_PARENT_MANIFEST,
            parent_feature_receipt_sha256="1" * 64,
            candidate_identity_sha256=candidate_identity_digest(state),
            source_allocation_sha256="2" * 64, plan_sha256="3" * 64,
            prepared_extents_sha256=bundle.extents.digest,
            active_mask_sha256="4" * 64, registry_mirror_sha256="5" * 64,
            resource_estimate_sha256="6" * 64,
            active_set_sha256=bundle.extents.active_semantic_digest,
            feature_sha256=bundle.extents.factor_map_digest,
            semantic_bank_count=bundle.extents.semantic_bank_count,
        )
        staged = A02StagedVocabularyExtension(bundle, receipt)
        self.assertEqual(staged.receipt.digest, receipt.digest)
        altered = replace(
            bundle,
            extents=replace(bundle.extents, active_semantic_digest="8" * 64),
        )
        with self.assertRaises(BilqisError):
            A02StagedVocabularyExtension(altered, receipt)


if __name__ == "__main__":
    unittest.main()
