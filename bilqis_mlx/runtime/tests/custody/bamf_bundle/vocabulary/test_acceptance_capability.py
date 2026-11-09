"""A02 staging evidence grants no publication authority."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning._atlas_candidate.state import _issue_parameter_extension_state
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.bamf_bundle import (
    A02StagedVocabularyExtension, A02VocabularyStagingReceipt,
    load_bamf_generation,
    require_issued_a02_staged_vocabulary_extension,
)
from bilqis_mlx.runtime.bamf_bundle._vocabulary_admission_records import (
    _issue_a02_staged_vocabulary_extension,
)
from bilqis_mlx.runtime.bamf_bundle.admission import derive_successor_bundle
from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle
from bilqis_mlx.runtime.bamf_bundle.genesis import BamfRunIdentity
from bilqis_mlx.runtime.bamf_bundle.publication.authority import require_accepted_parent
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    FIXTURE_PARENT_MANIFEST, acceptance, candidate, parent_state,
    publish_genesis, shape_patch,
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

    def test_only_a02_owner_can_issue_live_staged_handoff(self):
        state = parent_state()
        run_identity = BamfRunIdentity(
            "fixture-run", 17, "1" * 64, "bundles/foundation-origin", 0,
            "2" * 64, "3" * 64, "4" * 64, "5" * 64, "6" * 64,
            "7" * 64, "fixture-source", "8" * 64, "fixture-teacher", 0)
        bundle = replace(
            candidate(state, 1, FIXTURE_PARENT_MANIFEST),
            run_identity=run_identity,
            transition={
                "schema": "bilqis.mlx.bamf-generation-transition/v1",
                "kind": "PARAMETER_EXTENSION",
                "invalidate_derived_caches": True,
            },
        )
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
        with self.assertRaises(BilqisError):
            A02StagedVocabularyExtension(bundle, receipt)
        with self.assertRaises(BilqisError):
            _issue_a02_staged_vocabulary_extension(
                replace(bundle, run_identity=None), receipt)

        staged = _issue_a02_staged_vocabulary_extension(bundle, receipt)
        self.assertIs(require_issued_a02_staged_vocabulary_extension(staged), staged)
        self.assertEqual(staged.receipt.digest, receipt.digest)

        with self.assertRaises(BilqisError):
            _issue_a02_staged_vocabulary_extension(
                bundle, replace(receipt, candidate_identity_sha256="f" * 64))
        with self.assertRaises(BilqisError):
            _issue_a02_staged_vocabulary_extension(
                bundle, replace(receipt, feature_sha256="e" * 64))
        altered = replace(
            bundle,
            extents=replace(bundle.extents, active_semantic_digest="8" * 64),
        )
        with self.assertRaises(BilqisError):
            _issue_a02_staged_vocabulary_extension(altered, receipt)

    def test_generic_b13_acceptance_stops_at_c07_vocabulary_boundary(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(
                    os.environ,
                    {"BILQIS_DATA_PLANE": str(root / "plane.sqlite3")}):
                with shape_patch():
                    pointer = publish_genesis(root, run_seed=31)
                    parent = load_bamf_generation(
                        root / "bamf-state.json", publish_missing_outbox=False)
            successor = derive_successor_bundle(
                parent, parent.retained_state,
                parent_manifest_sha256=pointer["manifest_sha256"],
                delivery_events=({"event": "A02_STAGED_SUCCESSOR"},),
            )
            active = "8" * 64
            successor = replace(
                successor,
                extents=replace(parent.extents, active_semantic_digest=active),
                semantic_abi={**parent.semantic_abi, "active_set_sha256": active},
                transition={
                    "schema": "bilqis.mlx.bamf-generation-transition/v1",
                    "kind": "PARAMETER_EXTENSION",
                    "invalidate_derived_caches": True,
                },
            )
            binding = acceptance(successor, parent=parent.retained_state)
            with patch.dict(
                    os.environ,
                    {"BILQIS_DATA_PLANE": str(root / "plane.sqlite3")}), \
                    shape_patch(), self.assertRaises(BilqisError) as failure:
                require_accepted_parent(
                    root, successor, binding, load_bundle=load_bamf_bundle)
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED")


if __name__ == "__main__":
    unittest.main()
