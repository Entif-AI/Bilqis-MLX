"""C07 native publication consumes only owner-issued A02/B13 authority."""
import json
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import CandidateCustodyIdentity
from bilqis_mlx.runtime import release_adoption
from bilqis_mlx.runtime.jit_adoption import (
    _accepted_lease_run_identity, _execute_prepared_successor_adoption,
)
from bilqis_mlx.runtime.tests.admission.atlas.atlas_adoption_executor_support import (
    AtlasAdoptionExecutorFixture,
)
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _lease


class AtlasAdoptionPublicationTests(AtlasAdoptionExecutorFixture, unittest.TestCase):
    def test_first_native_publish_rechecks_a02_resource_headroom_before_persistence(self):
        parent, candidate = self._native_parent_and_candidate()
        lease = replace(_lease(), run_identity=_accepted_lease_run_identity(
            parent.run_identity))
        native_staged = self._a02_staged(
            candidate, required_available_bytes=2)
        parent_feature = SimpleNamespace(
            generation_manifest_sha256="a" * 64, digest="b" * 64)
        plan, ledger, proposal = self._proposal(self.staged)
        fixture = self.fixture.fixture
        release_path = (
            self.root / "factory-releases" /
            (self.staged.successor.release_sha256 + ".json"))

        with self.admitted_boundary(), patch(
                "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                return_value=(parent, "a" * 64)), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                return_value=({"generation": parent.generation}, parent)), patch(
                "bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt",
                return_value=parent_feature), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease",
                return_value=lease), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
                return_value=self.current), patch(
                "bilqis_mlx.runtime.bamf_bundle.vocabulary.admission.shutil.disk_usage",
                return_value=SimpleNamespace(free=1)), patch(
                "bilqis_mlx.runtime.bamf_bundle.publish_atlas_admission_generation") as publish:
            with self.assertRaises(BilqisError) as failure:
                _execute_prepared_successor_adoption(
                    self._runtime(), frontier=self.frontier, current=self.current,
                    ledger=ledger, plan=plan, checkpoint=self.checkpoint,
                    proposal=proposal, staged=(self.staged,),
                    source_registry=fixture.registry, answer_registry=fixture.answers,
                    native_staged=native_staged, atlas_lease=lease,
                    source_authority=object())

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_VOCABULARY_ADMISSION_DISK_BUDGET_EXCEEDED")
        self.assertFalse(release_path.exists())
        publish.assert_not_called()

    def test_native_b13_adoption_publishes_exact_staged_candidate_without_legacy_materialization(self):
        from bilqis_mlx.runtime.bamf_bundle.atlas_admission import AtlasAdmissionBinding

        parent, candidate = self._native_parent_and_candidate()
        lease = replace(_lease(), run_identity=_accepted_lease_run_identity(
            parent.run_identity))
        native_staged = self._a02_staged(candidate)
        candidate = native_staged.candidate
        parent_feature = SimpleNamespace(
            generation_manifest_sha256="a" * 64, digest="b" * 64)
        plan, ledger, proposal = self._proposal(self.staged)
        fixture = self.fixture.fixture
        pointer = {"schema": "bilqis.mlx.bamf-state/v2", "generation": 1}
        release_path = (
            self.root / "factory-releases" /
            (self.staged.successor.release_sha256 + ".json"))

        def publish_after_factory(*args, **kwargs):
            self.assertTrue(release_path.is_file())
            self.assertEqual(
                json.loads(release_path.read_text())["factory_release_sha256"],
                self.staged.successor.release_sha256)
            return pointer

        with self.admitted_boundary(), patch(
                "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                return_value=(parent, "a" * 64)), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                return_value=({"generation": parent.generation}, parent)), patch(
                "bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt",
                return_value=parent_feature), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease",
                return_value=lease), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
                side_effect=(self.current, self.staged.successor)), patch.object(
                release_adoption._runtime_admission,
                "_require_executable_factory_admission",
                side_effect=AssertionError("legacy receipt authority")), patch(
                "bilqis_mlx.runtime.bamf_bundle.publish_atlas_admission_generation",
                side_effect=publish_after_factory) as publish, patch.object(
                release_adoption, "_adopt_prepared_successor",
                side_effect=AssertionError("legacy materialization")):
            result = _execute_prepared_successor_adoption(
                self._runtime(), frontier=self.frontier, current=self.current,
                ledger=ledger, plan=plan, checkpoint=self.checkpoint,
                proposal=proposal, staged=(self.staged,),
                source_registry=fixture.registry, answer_registry=fixture.answers,
                native_staged=native_staged, atlas_lease=lease,
                source_authority=object())

        published_candidate = publish.call_args.args[1]
        binding = publish.call_args.kwargs["admission"]
        self.assertIs(published_candidate, candidate)
        self.assertIsInstance(binding, AtlasAdmissionBinding)
        self.assertEqual(binding.lease_sha256, lease.digest())
        self.assertEqual(binding.factory_release_sha256,
                         self.staged.successor.release_sha256)
        self.assertTrue(release_path.is_file())
        self.assertEqual(result.native_pointer, pointer)
        self.assertIs(result.optimizer, self.optimizer)

    def test_native_b13_retry_reuses_exact_already_published_admission(self):
        from bilqis_mlx.runtime import checkpoint_outbox
        from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
            AtlasAdmissionBinding, _issue_atlas_admission_binding,
        )
        from bilqis_mlx.runtime.bamf_bundle.records import CompleteStudent
        from bilqis_mlx.semantics.domains import contract_digest

        parent, candidate = self._native_parent_and_candidate()
        lease = replace(_lease(), run_identity=_accepted_lease_run_identity(
            parent.run_identity))
        native_staged = self._a02_staged(candidate)
        candidate = native_staged.candidate
        staging_receipt = native_staged.receipt
        plan, ledger, proposal = self._proposal(self.staged)
        binding = _issue_atlas_admission_binding(
            candidate, parent, lease_sha256=lease.digest(),
            source_approval_sha256=contract_digest(lease.source_approval),
            proposal_sha256=proposal.proposal_sha256,
            factory_release_sha256=self.staged.successor.release_sha256,
            staging_receipt_sha256=staging_receipt.digest,
            parent_feature_receipt_sha256=staging_receipt.parent_feature_receipt_sha256,
        )
        historical = AtlasAdmissionBinding.from_record(binding.to_record())
        pointer = {
            "schema": "bilqis.mlx.bamf-state/v2",
            "run_id": candidate.run_id,
            "generation": candidate.generation,
            "parent_manifest_sha256": candidate.parent_manifest_sha256,
            "manifest_sha256": "c" * 64,
            "acceptance_sha256": binding.digest,
        }
        accepted_state = replace(
            candidate.retained_state,
            custody=CandidateCustodyIdentity(
                candidate.run_id, candidate.generation,
                pointer["manifest_sha256"], candidate.topology.digest,
                candidate.extents.digest))
        accepted_outbox = tuple(checkpoint_outbox.with_delivery_outbox(
            {"run_id": candidate.run_id, "generation": candidate.generation},
            candidate.outbox)["delivery_outbox"])
        accepted = CompleteStudent(**{
            **candidate.__dict__, "retained_state": accepted_state,
            "outbox": accepted_outbox})
        fixture = self.fixture.fixture
        with self.admitted_boundary(), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease",
                return_value=lease), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_factory_release",
                return_value=self.staged.successor), patch.object(
                release_adoption._runtime_admission,
                "_require_executable_factory_admission",
                side_effect=AssertionError("legacy receipt authority")), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                return_value=(pointer, accepted)), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_binding_for_manifest",
                return_value=historical), patch(
                "bilqis_mlx.runtime.bamf_bundle.vocabulary.admission.shutil.disk_usage",
                side_effect=AssertionError("exact retry rechecked live A02 headroom")), patch(
                "bilqis_mlx.runtime.bamf_bundle.publish_atlas_admission_generation") as publish:
            result = _execute_prepared_successor_adoption(
                self._runtime(), frontier=self.frontier, current=self.current,
                ledger=ledger, plan=plan, checkpoint=self.checkpoint,
                proposal=proposal, staged=(self.staged,),
                source_registry=fixture.registry, answer_registry=fixture.answers,
                native_staged=native_staged, atlas_lease=lease,
                source_authority=object())

        self.assertEqual(result.native_pointer, pointer)
        publish.assert_not_called()
        self.assertTrue((
            self.root / "factory-releases" /
            (self.staged.successor.release_sha256 + ".json")).is_file())


if __name__ == "__main__":
    unittest.main()
