"""C07.1b concrete executor uses the native prepared-successor transaction."""
from dataclasses import asdict, fields, replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.jit_curriculum import propose_curriculum_delta
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime import release_adoption
from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate, CompleteStudent
from bilqis_mlx.runtime.bamf_bundle.genesis import BamfRunIdentity
from bilqis_mlx.runtime.jit_adoption import (
    _PreparedSuccessorRuntime, _accepted_lease_run_identity,
    _authenticate_native_staged_candidate,
    _execute_prepared_successor_adoption,
)
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import _lease, _REGISTRY
from bilqis_mlx.runtime.tests.admission.prepared_successor_fixtures import (
    PreparedSuccessorFixture,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import candidate, parent_state


class AtlasAdoptionExecutorTests(PreparedSuccessorFixture, unittest.TestCase):
    def _native_parent_and_candidate(self):
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

    def test_native_candidate_preflight_requires_exact_b13_parent_and_a02_anchors(self):
        parent, staged = self._native_parent_and_candidate()
        parent_feature = SimpleNamespace(
            generation_manifest_sha256="a" * 64, digest="b" * 64)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                return_value=(parent, "a" * 64)), patch(
                "bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt",
                return_value=parent_feature):
            self.assertIs(
                _authenticate_native_staged_candidate(
                    self.root, staged,
                    expected_candidate_identity_sha256=candidate_identity_digest(
                        staged.retained_state),
                    expected_parent_feature_receipt_sha256=parent_feature.digest,
                ),
                staged,
            )

            with self.assertRaises(BilqisError) as failure:
                _authenticate_native_staged_candidate(
                    self.root, staged,
                    expected_candidate_identity_sha256="c" * 64,
                    expected_parent_feature_receipt_sha256=parent_feature.digest,
                )
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_ATLAS_NATIVE_STAGING_DRIFT",
            )

    def test_native_candidate_preflight_rejects_parent_drift_before_mutation(self):
        parent, staged = self._native_parent_and_candidate()
        parent_feature = SimpleNamespace(
            generation_manifest_sha256="a" * 64, digest="b" * 64)
        drifted = replace(staged, parent_manifest_sha256="d" * 64)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                return_value=(parent, "a" * 64)), patch(
                "bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt",
                return_value=parent_feature):
            with self.assertRaises(BilqisError) as failure:
                _authenticate_native_staged_candidate(
                    self.root, drifted,
                    expected_candidate_identity_sha256=candidate_identity_digest(
                        drifted.retained_state),
                    expected_parent_feature_receipt_sha256=parent_feature.digest,
                )
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_ATLAS_ACCEPTED_PARENT_DRIFT",
            )

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

    def test_executor_rechecks_saved_checkpoint_before_native_commit(self):
        plan, ledger, proposal = self._proposal(self.staged)
        fixture = self.fixture.fixture
        stale = replace(self.checkpoint, optimizer_step=1)
        self.receipt["school"]["current_student"] = {
            **self.receipt["school"]["current_student"], "optimizer_step": 1}
        with self.admitted_boundary(), patch.object(
                release_adoption, "_adopt_prepared_successor",
                side_effect=AssertionError("stale executor entered commit")):
            with self.assertRaises(BilqisError) as failure:
                _execute_prepared_successor_adoption(
                    self._runtime(), frontier=self.frontier, current=self.current,
                    ledger=ledger, plan=plan, checkpoint=self.checkpoint,
                    proposal=proposal, staged=(self.staged,),
                    source_registry=fixture.registry,
                    answer_registry=fixture.answers)
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_ATLAS_RUNTIME_CONTEXT_CHANGED")
        self.assertNotEqual(stale, self.checkpoint)

    def test_native_same_grade_growth_commits_once_without_optimizer_update(self):
        import numpy as np
        from bilqis_mlx import state_dag

        native = self.prepare_native_same_grade_growth()
        self.staged = native.staged
        _, release_file, admission = (
            release_adoption._runtime_admission._executable_factory_admission(
                self.root, self.current, self.checkpoint,
                release_adoption._runtime_state._fingerprint(self.graph),
                self.graph))
        self.receipt.update(
            factory_release_sha256=self.current.release_sha256,
            factory_release_file=release_file,
            factory_release_schema=self.current.schema,
            factory_admission_v2=asdict(admission),
        )
        plan, ledger, proposal = self._proposal(self.staged)
        fixture = self.fixture.fixture
        old_weights = {
            name: np.array(value) for name, value in self.parameters.items()}
        with patch.object(
                release_adoption._compatibility_executable_projection,
                "legacy_course_for_profile",
                return_value=SimpleNamespace(version="fixture")), patch(
                "bilqis_mlx.factory.candidate_realizations.admitted_candidate_graph",
                return_value=native.graph), patch(
                "bilqis_mlx.learning.student_ops._predictions",
                side_effect=lambda _mx, _parameters, rows, *_:
                    {row["id"]: row["gold"] for row in rows}), patch.object(
                native.optim.AdamW, "update",
                side_effect=AssertionError("neural optimizer update")):
            result = _execute_prepared_successor_adoption(
                self._runtime(native.mx), frontier=self.frontier,
                current=self.current, ledger=ledger, plan=plan,
                checkpoint=self.checkpoint, proposal=proposal,
                staged=(self.staged,), source_registry=fixture.registry,
                answer_registry=fixture.answers)

        self.assertEqual(
            result.receipt["factory_release_sha256"],
            self.staged.successor.release_sha256)
        self.assertEqual(state_dag.read_current(self.root), result.receipt)
        self.assertEqual(int(result.optimizer.state["step"].item()), 7)
        self.assertEqual(int(self.optimizer.state["step"].item()), 7)
        for name, old in old_weights.items():
            active = (result.parameters[name][:native.old_count]
                      if name == "embedding.weight" else result.parameters[name])
            np.testing.assert_array_equal(np.asarray(active), old)
            np.testing.assert_array_equal(np.asarray(self.parameters[name]), old)

    def test_native_b13_adoption_publishes_exact_staged_candidate_without_legacy_materialization(self):
        from bilqis_mlx.runtime.bamf_bundle.atlas_admission import AtlasAdmissionBinding

        parent, candidate = self._native_parent_and_candidate()
        lease = replace(_lease(), run_identity=_accepted_lease_run_identity(
            parent.run_identity))
        staging_receipt = SimpleNamespace(
            candidate_identity_sha256=candidate_identity_digest(candidate.retained_state),
            parent_feature_receipt_sha256="b" * 64,
            digest="5" * 64,
        )
        native_staged = SimpleNamespace(candidate=candidate, receipt=staging_receipt)
        parent_feature = SimpleNamespace(
            generation_manifest_sha256="a" * 64, digest="b" * 64)
        plan, ledger, proposal = self._proposal(self.staged)
        fixture = self.fixture.fixture
        pointer = {"schema": "bilqis.mlx.bamf-state/v2", "generation": 1}
        ordering = []
        persisted_file = (
            "factory-releases/" + self.staged.successor.release_sha256 + ".json")
        with self.admitted_boundary(), patch(
                "bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority",
                return_value=(parent, "a" * 64)), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                return_value=({"generation": parent.generation}, parent)), patch(
                "bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt",
                return_value=parent_feature), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease",
                return_value=lease), patch(
                "bilqis_mlx.runtime.admission._persist_executable_factory_release",
                side_effect=lambda _run_dir, _release: ordering.append("factory") or persisted_file) as persist, patch(
                "bilqis_mlx.runtime.bamf_bundle.publish_atlas_admission_generation",
                side_effect=lambda *args, **kwargs: ordering.append("b13") or pointer) as publish, patch.object(
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
        persist.assert_called_once_with(self.root, self.staged.successor)
        self.assertEqual(ordering, ["factory", "b13"])
        self.assertEqual(result.native_pointer, pointer)
        self.assertIs(result.optimizer, self.optimizer)

    def test_native_b13_retry_reuses_exact_already_published_admission(self):
        from bilqis_mlx.runtime.bamf_bundle.atlas_admission import (
            AtlasAdmissionBinding, _issue_atlas_admission_binding,
        )
        from bilqis_mlx.runtime.bamf_bundle.records import CompleteStudent
        from bilqis_mlx.semantics.domains import contract_digest

        parent, candidate = self._native_parent_and_candidate()
        accepted = CompleteStudent(**candidate.__dict__)
        lease = replace(_lease(), run_identity=_accepted_lease_run_identity(
            parent.run_identity))
        staging_receipt = SimpleNamespace(
            candidate_identity_sha256=candidate_identity_digest(candidate.retained_state),
            parent_feature_receipt_sha256="b" * 64,
            digest="5" * 64,
        )
        native_staged = SimpleNamespace(candidate=candidate, receipt=staging_receipt)
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
        fixture = self.fixture.fixture
        with self.admitted_boundary(), patch(
                "bilqis_mlx.runtime.atlas_admission.read_accepted_atlas_lease",
                return_value=lease), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_generation",
                return_value=(pointer, accepted)), patch(
                "bilqis_mlx.runtime.bamf_bundle.feature.acceptance.accepted_binding_for_manifest",
                return_value=historical), patch(
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
            (self.staged.successor.release_sha256 + ".json")
        ).is_file())


if __name__ == "__main__":
    unittest.main()
