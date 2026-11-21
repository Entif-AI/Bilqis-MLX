"""Disposable #1300 integration witness through admitted-successor cold resume.

Later-grade retained learning is intentionally not claimed here. The human-run
trainer owns that progression proof.
"""
from __future__ import annotations

from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_admission import (
    read_accepted_atlas_factory_release,
    read_accepted_atlas_lease_v2,
)
from bilqis_mlx.runtime.atlas_flywheel_runtime import AcceptedAtlasFlywheelSupervisor
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_bundle import (
    read_accepted_generation_feature_context,
    read_accepted_vocabulary_registry_export,
)
from bilqis_mlx.semantics.atlas_projection import BANK_SIZE
from bilqis_mlx.source_adapters import event_frames

from ..conformance_1300_support import Conformance1300RuntimeSupport, SUCCESSOR, TARGET
from ..conformance_1300_support.accepted_step import AcceptedStepCapture
from ..conformance_1300_support.cold_resume_assertions import (
    assert_cold_resume_legality,
)
from ..conformance_1300_support.fixtures import CONFORMANCE_1300_REGISTRY
from ..conformance_1300_support.lifecycle import (
    bootstrap_staged_generation_zero,
    enroll_prepared_lease,
)
from ..conformance_1300_support.observability import ProductionRouteCapture
from ..conformance_1300_support.rollback import (
    DestructiveCandidateCapture,
    assert_complete_rollback,
    parent_custody,
)
from ..conformance_1300_support.scenario import (
    advance_until_admitted,
    assert_structural_admission_transition,
    one_visit,
    structural_certification_pass,
)


BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"


class IntegratedConformance1300CausalClosureTests(Conformance1300RuntimeSupport):
    def _bootstrap_and_admit_target(self, fixture, routes, progress):
        before, selected, grade, after = bootstrap_staged_generation_zero(self.run)
        self.assertEqual(selected.status, "TEACHER_SELECTED")
        self.assertEqual(grade.transition_kind, "BOOTSTRAP")
        grade.definition.verify()
        self.assertEqual(grade.generated_grade_id, grade.definition.definition_sha256)
        self.assertEqual(tuple(dict.fromkeys(grade.member_capability_ids)), ("A.IDENTITY",))
        self.assertEqual(
            (before.generation, before.retained_state.optimizer_step),
            (after.generation, after.retained_state.optimizer_step),
        )
        self.assertIsNone(after.baseline_evidence)
        approval = fixture.lease.source_approval
        approval.verify(CONFORMANCE_1300_REGISTRY)
        self.assertTrue(approval.audit_passed)
        self.assertTrue(approval.rights_compatible)
        feature_context = read_accepted_generation_feature_context(
            self.run / "bamf-state.json")
        self.assertEqual(
            feature_context.receipt.source_release_sha256, approval.atlas_release_sha256)
        self.assertEqual(
            feature_context.features.semantic_release, approval.atlas_release_sha256)
        with self.host_registry():
            lease = enroll_prepared_lease(
                self.run, fixture.lease,
                source_authority=AcceptedRuntimeHost(self.run).source_authority())
        self.assertEqual(lease.digest(), fixture.lease.digest())
        supervisor = AcceptedAtlasFlywheelSupervisor(
            self.run, self.parent_graph, reserve_gib=0.0)
        with structural_certification_pass():
            foundation_results, target_release, _ = advance_until_admitted(
                self, progress, TARGET)
        self.assertTrue(foundation_results)
        foundation_progress = tuple(progress)
        self.assertIn("selected A.IDENTITY with ", "\n".join(foundation_progress))
        boundary = next(i for i, message in enumerate(foundation_progress)
                        if message.startswith("grade boundary learner evidence refresh:"))
        transition = foundation_progress.index(
            "grade certification succeeded; activated exact receipt-bound generated successor")
        self.assertLess(boundary, transition)
        self.assertIn(TARGET, target_release.execution_plan.capability_map)
        assert_structural_admission_transition(
            self, after, load_accepted_generation(self.run))
        return supervisor, target_release

    def _learn_target_and_admit_successor(self, supervisor, target_release, routes, progress):
        self._credit_all_predecessor_learning(supervisor)
        target_start = len(progress)
        target_capture = AcceptedStepCapture()
        with target_capture.context():
            for _attempt in range(4):
                result = one_visit(self, progress)
                if result.accepted and "selected " + TARGET + " with " in "\n".join(
                        progress[target_start:]):
                    break
            else:
                self.fail(f"{TARGET} did not retain within 4 visits")
        target_step = target_capture.assert_published_identity(self, self.run)
        target_capture.assert_finite_nonzero(self, step=target_step)
        target_capture.assert_first_baseline_for(self, self.run, TARGET)
        target_learned = load_accepted_generation(self.run)
        target_indices = tuple(sorted(
            row.bank_index * BANK_SIZE + row.row_index
            for row in target_learned.retained_state.policy.row_ages))
        routes.assert_release_present_exclusion(
            self, target_release, "A.IDENTITY", expected_code="FUTURE_GENERATED_GRADE")
        self._credit_all_predecessor_learning(supervisor)
        with structural_certification_pass():
            transition_results, successor_release, _ = advance_until_admitted(
                self, progress, SUCCESSOR)
        self.assertTrue(transition_results)
        self.assertIn(SUCCESSOR, successor_release.execution_plan.capability_map)
        successor = load_accepted_generation(self.run)
        assert_structural_admission_transition(self, target_learned, successor)
        successor_indices = tuple(sorted(
            row.bank_index * BANK_SIZE + row.row_index
            for row in successor.retained_state.policy.row_ages))
        self.assertTrue(set(target_indices).issubset(successor_indices))
        self.assertEqual(len(successor_indices), len(target_indices) + 1)
        self.assertNotEqual(
            successor.semantic_abi["active_set_sha256"],
            target_learned.semantic_abi["active_set_sha256"])
        self.assertEqual(
            successor.semantic_abi["active_set_sha256"],
            successor.extents.active_semantic_digest)
        export = read_accepted_vocabulary_registry_export(self.run)
        self.assertEqual(export.active_indices, successor_indices)
        self.assertEqual(
            tuple(row.semantic_id for row in export.rows),
            (event_frames.atlas_semantic_id(SUCCESSOR),))
        self.assertEqual(
            tuple(row.abi_index for row in export.rows),
            tuple(sorted(set(successor_indices) - set(target_indices))))
        return successor_release

    def _reject_and_cold_resume(self, fixture, supervisor, successor_release, routes, progress):
        self._credit_all_predecessor_learning(supervisor, exclude=(SUCCESSOR,))
        before_rejection = parent_custody(load_accepted_generation(self.run), self.run)
        destructive = DestructiveCandidateCapture()
        with self._operator_context(fixture), destructive.context():
            for _attempt in range(4):
                rejected = one_visit(self, progress)
                if rejected.rejected:
                    break
            else:
                self.fail("destructive successor candidate was not rejected")
        self.assertEqual((rejected.accepted, rejected.rejected), (0, 1))
        assert_complete_rollback(self, self.run, before_rejection, destructive)
        self.assertIn("NEURAL_COMPOSITION", routes.route_kinds)
        routes.assert_exact_training_route_for(self, SUCCESSOR)
        routes.assert_routes_for(self, SUCCESSOR, "NEURAL_COMPOSITION")
        routes.assert_neural_composition_executes_exact_operator(self, SUCCESSOR)
        cold_receipts = assert_cold_resume_legality(self, self.run, SUCCESSOR)
        self.assertEqual(
            read_accepted_atlas_factory_release(self.run).release_sha256,
            successor_release.release_sha256)
        with self.host_registry():
            accepted_lease = read_accepted_atlas_lease_v2(
                self.run,
                source_authority=AcceptedRuntimeHost(self.run).source_authority())
        self.assertIsNotNone(accepted_lease)
        self.assertEqual(accepted_lease.digest(), fixture.lease.digest())
        self.assertEqual(
            cold_receipts["accepted"]["optimizer_step"],
            load_accepted_generation(self.run).retained_state.optimizer_step)

    def test_one_disposable_run_proves_create_learn_reject_expand_and_cold_resume(self):
        fixture = self._production_parameter_fixture()
        progress = []
        routes = ProductionRouteCapture()
        with self._operator_context(fixture), routes.context():
            supervisor, target_release = self._bootstrap_and_admit_target(
                fixture, routes, progress)
            successor_release = self._learn_target_and_admit_successor(
                supervisor, target_release, routes, progress)
            self._reject_and_cold_resume(
                fixture, supervisor, successor_release, routes, progress)
