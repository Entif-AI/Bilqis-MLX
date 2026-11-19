"""One disposable #1300 lineage proving the integrated BAMF-v2 causal story."""
from __future__ import annotations

from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_admission import (
    read_accepted_atlas_factory_release,
    read_accepted_atlas_lease_v2,
)
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_bundle import read_accepted_generation_feature_context
from bilqis_mlx.runtime.bamf_operator import read_latest_run_stop_receipt
from bilqis_mlx.source_adapters import event_frames

from .conformance_1300_support import Conformance1300RuntimeSupport, SUCCESSOR, TARGET
from .conformance_1300_support.accepted_step import AcceptedStepCapture
from .conformance_1300_support.cold_resume_assertions import (
    assert_cold_resume_legality,
)
from .conformance_1300_support.correction import hold_successor_only
from .conformance_1300_support.evidence_export import export_causal_evidence
from .conformance_1300_support.fixtures import CONFORMANCE_1300_REGISTRY
from .conformance_1300_support.lifecycle import (
    bootstrap_staged_generation_zero,
    enroll_prepared_lease,
)
from .conformance_1300_support.observability import ProductionRouteCapture
from .conformance_1300_support.rollback import (
    DestructiveCandidateCapture,
    assert_complete_rollback,
    parent_custody,
)
from .conformance_1300_support.scenario import (
    advance_until_admitted,
    advance_until_stop,
    one_visit,
)


BILQIS_LEAF_GATE_POLICY = "DETACHED_ONLY"


class IntegratedConformance1300CausalClosureTests(Conformance1300RuntimeSupport):
    def test_one_disposable_run_proves_create_learn_reject_resume_expand_correct_stop(self):
        fixture = self._production_parameter_fixture()
        progress = []
        routes = ProductionRouteCapture()

        with self._operator_context(fixture), routes.context():
            before, selected, grade, after = bootstrap_staged_generation_zero(self.run)
            self.assertEqual(selected.status, "TEACHER_SELECTED")
            self.assertEqual(grade.transition_kind, "BOOTSTRAP")
            grade.definition.verify()
            self.assertEqual(
                grade.generated_grade_id,
                grade.definition.definition_sha256,
            )
            self.assertEqual(
                tuple(dict.fromkeys(grade.member_capability_ids)),
                ("A.IDENTITY",),
            )
            self.assertEqual(
                (before.generation, before.retained_state.optimizer_step),
                (after.generation, after.retained_state.optimizer_step),
            )
            self.assertIsNone(after.baseline_evidence)
            foundation_abi = dict(after.semantic_abi)
            approval = fixture.lease.source_approval
            approval.verify(CONFORMANCE_1300_REGISTRY)
            self.assertTrue(approval.audit_passed)
            self.assertTrue(approval.rights_compatible)
            feature_context = read_accepted_generation_feature_context(
                self.run / "bamf-state.json"
            )
            self.assertEqual(
                feature_context.receipt.source_release_sha256,
                approval.atlas_release_sha256,
            )
            self.assertEqual(
                feature_context.features.semantic_release,
                approval.atlas_release_sha256,
            )
            with self.host_registry():
                lease = enroll_prepared_lease(
                    self.run,
                    fixture.lease,
                    source_authority=AcceptedRuntimeHost(self.run).source_authority(),
                )
            self.assertEqual(lease.digest(), fixture.lease.digest())

            foundation_results, target_release, _target_parent = advance_until_admitted(
                self, progress, TARGET)
            self.assertTrue(any(result.accepted for result in foundation_results))
            self.assertIn("evidence: measured A.IDENTITY PASS", progress)
            self.assertIn(TARGET, target_release.execution_plan.capability_map)
            self.assertIsNotNone(_target_parent.baseline_evidence)

            target_start = len(progress)
            target_capture = AcceptedStepCapture()
            with target_capture.context():
                target_results, successor_release, _successor_parent = advance_until_admitted(
                    self, progress, SUCCESSOR)
            self.assertTrue(any(result.accepted for result in target_results))
            target_step = target_capture.assert_published_identity(self, self.run)
            target_capture.assert_finite_nonzero(self, step=target_step)
            target_capture.assert_first_baseline_for(self, self.run, TARGET)
            target_progress = progress[target_start:]
            evidence_index = target_progress.index(
                "evidence: measured " + TARGET + " PASS")
            adoption_index = next(
                index for index, message in enumerate(target_progress)
                if "C07 adopted a successor" in message)
            self.assertLess(evidence_index, adoption_index)
            self.assertIn(SUCCESSOR, successor_release.execution_plan.capability_map)
            expanded_abi = dict(load_accepted_generation(self.run).semantic_abi)
            self.assertGreater(len(expanded_abi), len(foundation_abi))
            successor_semantic_id = event_frames.atlas_semantic_id(SUCCESSOR)
            self.assertIn(successor_semantic_id, expanded_abi)
            self.assertNotIn(successor_semantic_id, foundation_abi)
            for semantic_id, address in foundation_abi.items():
                self.assertIn(semantic_id, expanded_abi)
                self.assertEqual(expanded_abi[semantic_id], address)

            before_rejection = parent_custody(
                load_accepted_generation(self.run), self.run)
            destructive = DestructiveCandidateCapture()
            with self._operator_context(
                    fixture), destructive.context():
                for _attempt in range(4):
                    rejected = one_visit(self, progress)
                    routes.assert_release_present_exclusion(
                        self,
                        successor_release,
                        SUCCESSOR,
                        expected_code="FUTURE_GENERATED_GRADE",
                    )
                    if rejected.rejected:
                        break
                else:
                    self.fail("destructive successor candidate was not rejected")
            self.assertEqual((rejected.accepted, rejected.rejected), (0, 1))
            assert_complete_rollback(self, self.run, before_rejection, destructive)

            cold_receipts = assert_cold_resume_legality(self, self.run, SUCCESSOR)

            successor_capture = AcceptedStepCapture()
            successor_start = len(progress)
            with successor_capture.context():
                for _attempt in range(8):
                    learned = one_visit(self, progress)
                    if (learned.accepted
                            and "selected " + SUCCESSOR + " with "
                            in "\n".join(progress[successor_start:])):
                        break
                else:
                    self.fail(f"{SUCCESSOR} did not retain within 8 visits")
            successor_step = successor_capture.assert_published_identity(self, self.run)
            successor_capture.assert_finite_nonzero(self, step=successor_step)
            self.assertIn("NEURAL_COMPOSITION", routes.route_kinds)
            routes.assert_exact_training_route_for(self, SUCCESSOR)
            routes.assert_routes_for(
                self,
                SUCCESSOR,
                "NEURAL_COMPOSITION",
            )
            routes.assert_neural_composition_executes_exact_operator(
                self, SUCCESSOR)
            learned_release = read_accepted_atlas_factory_release(self.run)
            self.assertEqual(
                learned_release.release_sha256,
                successor_release.release_sha256,
            )

            stopped = advance_until_stop(self, progress)
            receipt = read_latest_run_stop_receipt(self.run)
            self.assertIsNotNone(receipt)
            self.assertEqual(receipt["receipt_sha256"], stopped.stop_receipt_sha256)
            self.assertIn(
                receipt["stop_reason"],
                ("PRIORITY_HOLD", "ADMISSION_HOLD",
                 "IMPLEMENTATION_UNCOVERED", "FIXED_POINT"),
            )

            state_before_correction = load_accepted_generation(self.run)
            event_id, dependency, corrected = hold_successor_only(
                self, self.run, target=TARGET, successor=SUCCESSOR)
            state_after_correction = load_accepted_generation(self.run)
            self.assertTrue(event_id)
            self.assertTrue(dependency.key.startswith("salience-fact:"))
            self.assertEqual(corrected.support.status, "REQUALIFICATION_REQUIRED")
            self.assertEqual(
                candidate_identity_digest(state_after_correction.retained_state),
                candidate_identity_digest(state_before_correction.retained_state),
            )
            self.assertEqual(
                state_after_correction.retained_state.optimizer_step,
                state_before_correction.retained_state.optimizer_step,
            )
            self.assertEqual(
                state_after_correction.baseline_evidence,
                state_before_correction.baseline_evidence,
            )
            self.assertEqual(
                state_after_correction.teacher_state,
                state_before_correction.teacher_state,
            )
            self.assertEqual(
                state_after_correction.retained_state.allocations,
                state_before_correction.retained_state.allocations,
            )
            self.assertEqual(
                state_after_correction.retained_state.policy,
                state_before_correction.retained_state.policy,
            )
            self.assertEqual(
                state_after_correction.learning_health_state,
                state_before_correction.learning_health_state,
            )
            self.assertEqual(
                state_after_correction.extents,
                state_before_correction.extents,
            )
            self.assertEqual(
                dict(state_after_correction.semantic_abi),
                dict(state_before_correction.semantic_abi),
            )
            self.assertEqual(
                state_after_correction.generation,
                state_before_correction.generation,
            )
            with self.host_registry():
                accepted_lease = read_accepted_atlas_lease_v2(
                    self.run,
                    source_authority=AcceptedRuntimeHost(self.run).source_authority(),
                )
            self.assertIsNotNone(accepted_lease)
            self.assertEqual(accepted_lease.digest(), fixture.lease.digest())
            exported = export_causal_evidence(
                self.run,
                self,
                target_capture=target_capture,
                successor_capture=successor_capture,
                routes=routes,
                cold_receipts=cold_receipts,
                stop_receipt=receipt,
                correction={
                    "event_id": event_id,
                    "dependency_kind": dependency.kind.value,
                    "dependency_key": dependency.key,
                    "successor_capability_id": SUCCESSOR,
                    "successor_support_status": corrected.support.status.value,
                    "pending_source_task_capability_ids": [
                        task.capability_id
                        for task in corrected.ledger.pending_source_tasks
                    ],
                },
            )
            if exported is not None:
                self.assertTrue(exported.is_file())
