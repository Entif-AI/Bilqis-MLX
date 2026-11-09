"""C12 accepted import behavior across B12 custody and B13 publication."""
from dataclasses import replace
import json
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import begin_candidate, candidate_step, resolve_candidate
from bilqis_mlx.learning._retention.tests.execution_fixtures import execution_provenance
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.cognitive_package import publish_screened_delta_import
from bilqis_mlx.runtime.cognitive_package.tests.adoption_harness import (
    AdoptionHarness, KEY_OWNER, SCOPE_OWNER, _receipt,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import HP, NAME, shape_patch
from bilqis_mlx.semantics.context_eligibility import SourceFrontier


class PackageImportAdoptionTests(AdoptionHarness):
    def test_eligible_import_resets_receiver_state_and_publishes_lineage(self):
        screened, receipt = self.screened()
        published = self.adopt(screened, receipt)
        with shape_patch():
            loaded = load_bamf_generation(self.run / "bamf-state.json")

        self.assertEqual(loaded.generation, self.initial.generation + 1)
        self.assertEqual(
            loaded.retained_state.optimizer_step,
            self.state.optimizer_step,
        )
        self.assertEqual(loaded.retained_state.policy.mode, self.state.policy.mode)
        self.assertEqual(loaded.retained_state.policy.accepted_fast_since_full, 0)
        self.assertEqual(
            loaded.retained_state.policy.row_ages,
            screened.transaction.candidate.policy.row_ages,
        )
        self.assertAlmostEqual(
            float(np.asarray(loaded.retained_state.optimizer.parameters[NAME])[0, 0]),
            float(np.asarray(self.state.optimizer.parameters[NAME])[0, 0]) + .5,
        )
        self.assertEqual(np.asarray(loaded.retained_state.optimizer.m[NAME])[0, 0], 0.)
        self.assertEqual(np.asarray(loaded.retained_state.optimizer.v[NAME])[0, 0], 0.)
        np.testing.assert_array_equal(
            np.asarray(loaded.retained_state.optimizer.update_counts[NAME]), [0, 0])
        self.assertEqual(loaded.transition["kind"], "PACKAGE_IMPORT")
        self.assertEqual(loaded.transition["package_sha256"], screened.candidate.package.digest)
        self.assertEqual(loaded.transition["source_clearance_sha256"], receipt.clearance_sha256)
        self.assertEqual(loaded.outbox[0]["origin"], "PACKAGE_IMPORT")
        self.assertEqual(loaded.outbox[0]["receiver_manifest_sha256"], self.pointer["manifest_sha256"])
        self.assertEqual(published["parent_manifest_sha256"], self.pointer["manifest_sha256"])

    def test_next_native_step_binds_to_imported_generation_and_reset_lineage(self):
        screened, receipt = self.screened()
        published = self.adopt(screened, receipt)
        with shape_patch():
            loaded = load_bamf_generation(self.run / "bamf-state.json")

        self.assertEqual(loaded.generation, self.initial.generation + 1)
        self.assertEqual(loaded.transition["kind"], "PACKAGE_IMPORT")
        self.assertEqual(loaded.transition["package_sha256"], screened.candidate.package.digest)
        self.assertEqual(
            loaded.transition["reset_policy_sha256"], screened.transaction.reset_policy_sha256)
        self.assertEqual(
            loaded.retained_state.custody.manifest_sha256, published["manifest_sha256"])

        transaction = begin_candidate(loaded.retained_state)
        execution = execution_provenance(
            transaction.parent, rows=(0,), candidate_step=1,
            extents=loaded.extents)
        with shape_patch():
            transaction = candidate_step(
                transaction,
                {NAME: mx.array([[1., 1.], [0., 0.]], dtype=mx.float32)},
                execution, HP, spec=loaded.topology, extents=loaded.extents,
                loss_bearing=True, max_norm=1.)
        retained = resolve_candidate(transaction, accepted=True)

        np.testing.assert_array_equal(
            np.asarray(retained.optimizer.update_counts[NAME]), [1, 0])
        self.assertEqual(retained.optimizer_step, loaded.retained_state.optimizer_step + 1)
        self.assertEqual(execution.parent_manifest_sha256, published["manifest_sha256"])

    def test_reject_or_eligible_label_alone_cannot_publish(self):
        rejected, receipt = self.screened(accepted=False)
        self.assertFalse(rejected.decision.accepted)
        with self.assertRaises(BilqisError):
            self.adopt(rejected, receipt)
        eligible, receipt = self.screened()
        for forged in (True, eligible.decision):
            with self.subTest(forged=type(forged).__name__), self.assertRaises(BilqisError):
                self.adopt(forged, receipt)
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], self.pointer["manifest_sha256"])

    def test_current_a12_clearance_is_required(self):
        screened, receipt = self.screened()
        forged = replace(receipt, signature_hex="0" * 128)
        with self.assertRaises(BilqisError):
            self.adopt(screened, forged)
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], self.pointer["manifest_sha256"])

    def test_host_bound_authority_rejects_scope_key_and_stale_frontier_before_publish(self):
        screened, receipt = self.screened()
        artifacts = receipt.export_artifact_digests
        cases = (
            ("scope", _receipt(
                self.selection, self.frontier, artifacts, owner=SCOPE_OWNER), self.frontier),
            ("key", _receipt(
                self.selection, self.frontier, artifacts, owner=KEY_OWNER), self.frontier),
            ("frontier", receipt, SourceFrontier(3, 4, ())),
        )
        for name, candidate_receipt, frontier in cases:
            with self.subTest(name=name), patch(
                "bilqis_mlx.runtime.cognitive_package.adoption.accept_and_publish",
                side_effect=AssertionError("downstream mutation reached"),
            ):
                with self.assertRaises(BilqisError):
                    publish_screened_delta_import(
                        screened, self.run, export_clearance=candidate_receipt,
                        atlas_selection=self.selection, source_frontier=frontier,
                        source_context=self.source_context())
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], self.pointer["manifest_sha256"])
