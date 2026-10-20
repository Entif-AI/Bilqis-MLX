from dataclasses import replace
import hashlib
import unittest

from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.autonomy import (
    AutonomyActionKind,
    EvidenceKind,
    EvidenceReceipt,
    RejectedTeachingAttemptReceipt,
    ProjectionEvidenceSpec,
    compile_autonomy_plan,
    initial_evidence_ledger,
    evidence_complete_capabilities,
    next_action,
    next_work,
    obligations_for_capability,
    record_evidence,
    record_rejected_teaching_attempt,
)
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class AutonomousCurriculumPlannerTests(unittest.TestCase):
    def setUp(self):
        names = ("A.BASE", "A.OTHER", "A.COMPOSITE", "A.F3", "A.F4", "A.F5")
        caps = []
        for name in names:
            prerequisites = (("A.BASE", "A.OTHER") if name == "A.COMPOSITE" else ())
            caps.append(Capability(
                id=name, difficulty="fixture", source_anchor="repo:fixture/autonomy",
                taught_roots=("fixture." + name.lower(),),
                examined_roots=("fixture." + name.lower(),),
                prerequisites=prerequisites, composed_of=prerequisites,
                answer_families=(AnswerFamily("binary", BINARY),),
                lesson_generator="fixture.autonomy-generator/v1",
                independent_oracle="fixture.autonomy-oracle/v1",
            ))
        grade = Grade(
            "A", tuple(caps), assessment_sha256="a" * 64,
            exam_item_counts=tuple((name, 4) for name in names),
            teaching_stages=(("A.BASE", "A.OTHER"),
                             ("A.COMPOSITE", "A.F3", "A.F4", "A.F5")),
        )
        course = Course((grade,), "fixture.autonomy/v1", "b" * 64, "a" * 64)
        descriptor = SourceAdapter(
            "fixture.autonomy-adapter/v1", "fixture.autonomy-generator/v1",
            ("fixture.autonomy-oracle/v1",), "d" * 64,
            teaching_option_ids=("fixture.transfer",),
        )
        registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            descriptor, lambda **_: (), lambda row, **_: True),))
        self.release = compile_factory_release(course, registry)
        self.receipt_index = 0

    def receipt(self, obligation, passed=True, specimen_count=None):
        self.receipt_index += 1
        count = obligation.minimum_specimens if specimen_count is None else specimen_count
        return EvidenceReceipt(
            obligation_id=obligation.obligation_id,
            evidence_id=f"evidence-{self.receipt_index}",
            checkpoint_sha256="e" * 64,
            optimizer_step=self.receipt_index,
            cohort_sha256=_sha(f"cohort-{self.receipt_index}"),
            specimen_count=count,
            passed=passed,
        )

    def teaching_receipt(self, failed, *, intervention_id="teach-1",
                         teaching_option_id=None, checkpoint_sha256="f" * 64,
                         optimizer_step=None, **overrides):
        adapter = self.release.source_adapters[0]
        coverage = next(item for item in self.release.coverage_plans
                        if item.capability_id == failed.obligation_id.split("/", 1)[0])
        values = {
            "obligation_id": failed.obligation_id,
            "intervention_id": intervention_id,
            "teaching_option_id": teaching_option_id or
                "source.direct/" + failed.obligation_id.split("/", 1)[0],
            "parent_checkpoint_sha256": failed.checkpoint_sha256,
            "parent_optimizer_step": failed.optimizer_step,
            "checkpoint_sha256": checkpoint_sha256,
            "optimizer_step": (failed.optimizer_step + 1 if optimizer_step is None
                               else optimizer_step),
            "selected_provider_id": adapter.adapter_id,
            "provider_implementation_sha256": adapter.implementation_sha256,
            "specimen_ids": ("teaching-specimen-" + intervention_id,),
            "specimen_content_sha256": _sha("teaching-content-" + intervention_id),
            "variation_axes": coverage.variation_axes,
            "optimizer_step_delta": 1,
        }
        values.update(overrides)
        from bilqis_mlx.factory.autonomy import TeachingReceipt
        return TeachingReceipt(**values)

    def close_current_capability(self, ledger):
        capability = next_work(self.release, ledger).capability_id
        while True:
            work = next_work(self.release, ledger)
            if work is None or work.capability_id != capability:
                return ledger
            ledger = record_evidence(self.release, ledger, self.receipt(work.obligation))

    def test_generation_axes_constrain_evidence_without_becoming_mastery_claims(self):
        obligations = obligations_for_capability(self.release, "A.BASE")
        self.assertEqual(len(obligations), 1)
        self.assertEqual(obligations[0].kind, EvidenceKind.DIRECT)
        self.assertEqual(obligations[0].generation_axes,
                         ("source-valid", "balanced-gold", "fresh-seed"))

    def test_planner_closes_roots_then_unlocks_composite(self):
        ledger = initial_evidence_ledger(self.release)
        first = next_work(self.release, ledger)
        self.assertEqual(first.capability_id, "A.BASE")
        self.assertEqual(first.obligation.kind, EvidenceKind.DIRECT)
        self.assertEqual(first.teaching_option_ids,
                         ("source.direct/A.BASE", "fixture.transfer"))

        ledger = self.close_current_capability(ledger)
        self.assertEqual(evidence_complete_capabilities(self.release, ledger), ("A.BASE",))
        self.assertEqual(next_work(self.release, ledger).capability_id, "A.OTHER")

        ledger = self.close_current_capability(ledger)
        self.assertEqual(evidence_complete_capabilities(self.release, ledger),
                         ("A.BASE", "A.OTHER"))
        work = next_work(self.release, ledger)
        self.assertEqual(work.capability_id, "A.COMPOSITE")
        kinds = {item.kind for item in obligations_for_capability(
            self.release, "A.COMPOSITE")}
        self.assertEqual(kinds, {EvidenceKind.DIRECT, EvidenceKind.PREREQUISITE,
                                 EvidenceKind.COMPOSITION})

    def test_next_work_is_deterministic_for_unchanged_ledger(self):
        ledger = initial_evidence_ledger(self.release)
        first = next_work(self.release, ledger)
        second = next_work(self.release, ledger)
        self.assertEqual(first, second)

    def test_explicit_current_context_excludes_stale_mastery(self):
        ledger = initial_evidence_ledger(self.release)
        first = next_work(self.release, ledger)
        ledger = record_evidence(self.release, ledger, self.receipt(first.obligation))
        self.assertEqual(
            evidence_complete_capabilities(self.release, ledger), ("A.BASE",))
        self.assertEqual(
            evidence_complete_capabilities(
                self.release, ledger,
                current_checkpoint_sha256="f" * 64,
                current_optimizer_step=999),
            (),
        )
        self.assertEqual(
            next_work(
                self.release, ledger, current_checkpoint_sha256="f" * 64,
                current_optimizer_step=999).capability_id,
            "A.BASE",
        )

    def test_recording_with_explicit_context_rejects_another_checkpoint(self):
        ledger = initial_evidence_ledger(self.release)
        work = next_work(self.release, ledger)
        with self.assertRaisesRegex(ValueError, "EVIDENCE_CURRENT_CHECKPOINT_MISMATCH"):
            record_evidence(
                self.release, ledger, self.receipt(work.obligation),
                current_checkpoint_sha256="f" * 64,
                current_optimizer_step=1)

    def test_explicit_current_context_does_not_reteach_a_stale_failure(self):
        ledger = initial_evidence_ledger(self.release)
        work = next_work(self.release, ledger)
        ledger = record_evidence(
            self.release, ledger, self.receipt(work.obligation, passed=False))
        action = next_action(
            self.release, ledger,
            current_checkpoint_sha256="f" * 64,
            current_optimizer_step=999)
        self.assertEqual(action.kind, AutonomyActionKind.LEARNING_EVIDENCE)
        self.assertEqual(action.evidence_work.obligation, work.obligation)

    def test_composition_evidence_is_required_for_evidence_complete_state(self):
        ledger = initial_evidence_ledger(self.release)
        ledger = self.close_current_capability(ledger)
        ledger = self.close_current_capability(ledger)
        composite = obligations_for_capability(self.release, "A.COMPOSITE")
        missing = next(item for item in composite if item.kind is EvidenceKind.COMPOSITION)
        for obligation in composite:
            if obligation != missing:
                ledger = record_evidence(self.release, ledger, self.receipt(obligation))
        self.assertNotIn("A.COMPOSITE", evidence_complete_capabilities(self.release, ledger))
        self.assertEqual(next_work(self.release, ledger).obligation, missing)
        ledger = record_evidence(self.release, ledger, self.receipt(missing))
        self.assertIn("A.COMPOSITE", evidence_complete_capabilities(self.release, ledger))

    def test_failed_receipt_reopens_before_new_work(self):
        ledger = initial_evidence_ledger(self.release)
        obligation = next_work(self.release, ledger).obligation
        ledger = record_evidence(self.release, ledger, self.receipt(obligation))
        self.assertNotEqual(next_work(self.release, ledger).obligation.obligation_id,
                            obligation.obligation_id)
        ledger = record_evidence(self.release, ledger, self.receipt(obligation, passed=False))
        self.assertEqual(next_work(self.release, ledger).obligation.obligation_id,
                         obligation.obligation_id)
        self.assertNotIn("A.BASE", evidence_complete_capabilities(self.release, ledger))

    def test_passing_receipt_must_meet_obligation_specimen_floor(self):
        ledger = initial_evidence_ledger(self.release)
        obligation = next_work(self.release, ledger).obligation
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_EVIDENCE_SPECIMENS"):
            record_evidence(self.release, ledger,
                            self.receipt(obligation, specimen_count=obligation.minimum_specimens - 1))

    def test_evidence_is_bound_to_exact_factory_release(self):
        ledger = initial_evidence_ledger(self.release)
        changed = replace(self.release, release_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, "AUTONOMY_RELEASE_MISMATCH"):
            next_work(changed, ledger)

    def test_autonomous_loop_finishes_without_grade_specific_dispatch(self):
        ledger = initial_evidence_ledger(self.release)
        seen = []
        for _ in range(40):
            work = next_work(self.release, ledger)
            if work is None:
                break
            seen.append((work.capability_id, work.obligation.kind))
            ledger = record_evidence(self.release, ledger, self.receipt(work.obligation))
        else:
            self.fail("autonomous evidence loop did not converge")

        self.assertLess(seen.index(("A.BASE", EvidenceKind.DIRECT)),
                        seen.index(("A.COMPOSITE", EvidenceKind.DIRECT)))
        self.assertLess(seen.index(("A.OTHER", EvidenceKind.DIRECT)),
                        seen.index(("A.COMPOSITE", EvidenceKind.DIRECT)))
        self.assertEqual(evidence_complete_capabilities(self.release, ledger),
                         tuple(item.capability_id for item in self.release.capabilities))
        self.assertIsNone(next_work(self.release, ledger))

    def test_projection_proof_is_part_of_evidence_completion(self):
        plan = compile_autonomy_plan(
            self.release,
            projection_evidence=(
                ProjectionEvidenceSpec(
                    "A.BASE", "TRANSFER", 2,
                    ("nonce-symbol-renaming",)),
            ),
        )
        ledger = initial_evidence_ledger(self.release, plan=plan)
        direct = next_work(self.release, ledger, plan=plan)
        self.assertEqual(direct.obligation.kind, EvidenceKind.DIRECT)
        ledger = record_evidence(
            self.release, ledger, self.receipt(direct.obligation), plan=plan)
        self.assertNotIn(
            "A.BASE",
            evidence_complete_capabilities(self.release, ledger, plan=plan),
        )
        projection = next_work(self.release, ledger, plan=plan)
        self.assertEqual(projection.capability_id, "A.BASE")
        self.assertEqual(projection.obligation.kind, EvidenceKind.PROJECTION)
        self.assertEqual(projection.obligation.key, "TRANSFER")
        self.assertEqual(
            projection.obligation.proof_axes,
            ("nonce-symbol-renaming",),
        )
        ledger = record_evidence(
            self.release, ledger, self.receipt(projection.obligation), plan=plan)
        self.assertIn(
            "A.BASE",
            evidence_complete_capabilities(self.release, ledger, plan=plan),
        )

    def test_unsupported_projection_routes_as_source_coverage_debt(self):
        plan = compile_autonomy_plan(
            self.release,
            projection_coverage_debt=(
                "A.BASE:TRANSFER:SOURCE_PROJECTION_UNSUPPORTED",
            ),
        )
        ledger = initial_evidence_ledger(self.release, plan=plan)
        action = next_action(self.release, ledger, plan=plan)
        self.assertEqual(action.kind, AutonomyActionKind.SOURCE_COVERAGE)
        self.assertEqual(
            action.source_coverage_debt,
            "A.BASE:TRANSFER:SOURCE_PROJECTION_UNSUPPORTED",
        )
        self.assertIn("A.BASE", plan.blocked_capabilities)

    def test_empty_projection_extension_preserves_legacy_plan_digest(self):
        plan = compile_autonomy_plan(self.release)
        legacy_payload = {
            "factory_release_sha256": self.release.release_sha256,
            "source_composition_audited": False,
            "source_composition_edges": (),
            "coverage_debt": (),
            "blocked_capabilities": (),
            "deferred_composition_candidates": (),
        }
        self.assertEqual(plan.digest(), _sha(
            __import__("json").dumps(
                legacy_payload, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False)))


if __name__ == "__main__":
    unittest.main()

class TypedCompositionAutonomyTests(AutonomousCurriculumPlannerTests):
    def coverage_report(self, *, status="SOURCE_CONTRAST_COVERED", debt=False):
        from bilqis_mlx.curriculum_compiler import compile_ast
        return {
            "schema": "bilqis.mlx.semantic-composition-coverage/v1",
            "ast_sha256": compile_ast(self.release.course).digest(),
            "registry_sha256": "9" * 64,
            "capabilities": tuple(item.capability_id for item in self.release.capabilities),
            "obligations": ({
                "consumer": "A.F3",
                "producer": "A.BASE",
                "operand_slot": 0,
                "operand_type": "Boolean",
                "declared_prerequisite": True,
                "status": status,
                "coverage_debt": debt,
                "witness_ids": ("witness-1",) if not debt else (),
            },),
            "unresolved": (),
            "source_witness_cohort_sha256": "8" * 64,
            "training_authorized": False,
        }

    def test_source_covered_discovered_edge_becomes_composition_obligation(self):
        from bilqis_mlx.factory.autonomy import compile_autonomy_plan
        plan = compile_autonomy_plan(self.release, self.coverage_report())
        obligations = obligations_for_capability(self.release, "A.F3", plan=plan)
        typed = [item for item in obligations if item.kind is EvidenceKind.COMPOSITION]
        self.assertEqual(len(typed), 1)
        self.assertEqual(typed[0].requires_capabilities, ("A.BASE",))
        self.assertIn("typed-composition/A.BASE/slot/0", typed[0].obligation_id)
        self.assertEqual(plan.coverage_debt, ())

    def test_unverified_discovered_edge_stays_source_coverage_debt(self):
        from bilqis_mlx.factory.autonomy import compile_autonomy_plan, next_source_coverage_debt
        report = self.coverage_report(status="AWAITING_SOURCE_WITNESS", debt=True)
        plan = compile_autonomy_plan(self.release, report)
        obligations = obligations_for_capability(self.release, "A.F3", plan=plan)
        self.assertFalse(any(item.kind is EvidenceKind.COMPOSITION for item in obligations))
        self.assertIn("A.F3:A.BASE:0:AWAITING_SOURCE_WITNESS",
                      next_source_coverage_debt(plan))

    def test_undeclared_unverified_candidate_is_deferred_not_blocking(self):
        from bilqis_mlx.factory.autonomy import compile_autonomy_plan, next_source_coverage_debt
        report = self.coverage_report(
            status="CROSS_SOURCE_AST_BRIDGE_UNVERIFIED", debt=True)
        report["obligations"][0]["declared_prerequisite"] = False
        plan = compile_autonomy_plan(self.release, report)
        self.assertEqual(plan.coverage_debt, ())
        self.assertEqual(plan.blocked_capabilities, ())
        self.assertEqual(
            plan.deferred_composition_candidates,
            ("A.F3:A.BASE:0:CROSS_SOURCE_AST_BRIDGE_UNVERIFIED",),
        )
        self.assertIsNone(next_source_coverage_debt(plan))

    def test_evidence_ledger_is_bound_to_exact_autonomy_plan(self):
        from bilqis_mlx.factory.autonomy import compile_autonomy_plan
        plan = compile_autonomy_plan(self.release, self.coverage_report())
        ledger = initial_evidence_ledger(self.release, plan=plan)
        changed = compile_autonomy_plan(
            self.release,
            self.coverage_report(status="SOURCE_CONTRAST_PARTIAL", debt=True),
        )
        with self.assertRaisesRegex(ValueError, "AUTONOMY_PLAN_MISMATCH"):
            next_work(self.release, ledger, plan=changed)

class AutonomyRouterTests(TypedCompositionAutonomyTests):
    def test_router_prioritizes_source_debt_before_learner_work(self):
        from bilqis_mlx.factory.autonomy import (
            AutonomyActionKind, compile_autonomy_plan, next_action,
        )
        plan = compile_autonomy_plan(
            self.release,
            self.coverage_report(status="AWAITING_SOURCE_WITNESS", debt=True),
        )
        ledger = initial_evidence_ledger(self.release, plan=plan)
        action = next_action(self.release, ledger, plan=plan)
        self.assertEqual(action.kind, AutonomyActionKind.SOURCE_COVERAGE)
        self.assertEqual(action.source_coverage_debt,
                         "A.F3:A.BASE:0:AWAITING_SOURCE_WITNESS")
        self.assertIsNone(action.evidence_work)

    def test_router_selects_learner_evidence_when_source_is_clean(self):
        from bilqis_mlx.factory.autonomy import AutonomyActionKind, next_action
        ledger = initial_evidence_ledger(self.release)
        action = next_action(self.release, ledger)
        self.assertEqual(action.kind, AutonomyActionKind.LEARNING_EVIDENCE)
        self.assertEqual(action.evidence_work.capability_id, "A.BASE")
        self.assertIsNone(action.source_coverage_debt)

    def test_router_hands_off_to_qualification_after_evidence_closure(self):
        from bilqis_mlx.factory.autonomy import AutonomyActionKind, next_action
        ledger = initial_evidence_ledger(self.release)
        for _ in range(40):
            action = next_action(self.release, ledger)
            if action.kind is AutonomyActionKind.QUALIFICATION:
                break
            self.assertEqual(action.kind, AutonomyActionKind.LEARNING_EVIDENCE)
            ledger = record_evidence(
                self.release, ledger, self.receipt(action.evidence_work.obligation))
        else:
            self.fail("router never reached qualification")
        self.assertEqual(action.kind, AutonomyActionKind.QUALIFICATION)
        self.assertIsNone(action.evidence_work)
        self.assertIsNone(action.source_coverage_debt)

class AutonomyPlanRebindTests(TypedCompositionAutonomyTests):
    def test_source_debt_resolution_can_preserve_unaffected_evidence(self):
        from bilqis_mlx.factory.autonomy import (
            compile_autonomy_plan, rebind_evidence_ledger,
        )
        blocked = compile_autonomy_plan(
            self.release,
            self.coverage_report(status="AWAITING_SOURCE_WITNESS", debt=True),
        )
        ledger = initial_evidence_ledger(self.release, plan=blocked)
        work = next_work(self.release, ledger, plan=blocked)
        self.assertEqual(work.capability_id, "A.BASE")
        ledger = record_evidence(
            self.release, ledger, self.receipt(work.obligation), plan=blocked)

        covered = compile_autonomy_plan(self.release, self.coverage_report())
        rebound = rebind_evidence_ledger(
            self.release, ledger, old_plan=blocked, new_plan=covered)
        self.assertEqual(rebound.receipts, ledger.receipts)
        self.assertEqual(rebound.autonomy_plan_sha256, covered.digest())
        self.assertEqual(
            next_work(self.release, rebound, plan=covered).capability_id,
            "A.OTHER",
        )

    def test_plan_rebind_rejects_receipts_for_changed_obligation_contract(self):
        from bilqis_mlx.factory.autonomy import (
            AutonomyPlan, compile_autonomy_plan, rebind_evidence_ledger,
        )
        old = compile_autonomy_plan(self.release)
        ledger = initial_evidence_ledger(self.release, plan=old)
        ledger = self.close_current_capability(ledger)
        # Auditing composition changes A.COMPOSITE's composition obligation IDs.
        new = compile_autonomy_plan(self.release, self.coverage_report())
        # Evidence only exists for A.BASE here and remains compatible.
        compatible = rebind_evidence_ledger(
            self.release, ledger, old_plan=old, new_plan=new)
        self.assertEqual(compatible.receipts, ledger.receipts)

        # Now close through the old-plan composite. Explicit composition evidence
        # remains valid; the audited plan may add extra typed-slot obligations
        # without relabeling or discarding the original receipts.
        ledger = self.close_current_capability(ledger)
        ledger = self.close_current_capability(ledger)
        rebound = rebind_evidence_ledger(
            self.release, ledger, old_plan=old, new_plan=new)
        self.assertEqual(rebound.receipts, ledger.receipts)
        typed = tuple(
            obligation for obligation in obligations_for_capability(
                self.release, "A.F3", plan=new)
            if "typed-composition" in obligation.obligation_id)
        self.assertEqual(len(typed), 1)
        self.assertNotIn(
            typed[0].obligation_id,
            {receipt.obligation_id for receipt in rebound.receipts},
        )


class TeachingInterventionTests(AutonomousCurriculumPlannerTests):
    def test_repeated_rejected_challengers_consume_remediation_budget(self):
        ledger = initial_evidence_ledger(self.release)
        work = next_work(self.release, ledger)
        failed = EvidenceReceipt(
            obligation_id=work.obligation.obligation_id,
            evidence_id="rejected-campaign-parent",
            checkpoint_sha256="1" * 64,
            optimizer_step=10,
            cohort_sha256=_sha("rejected-campaign-cohort"),
            specimen_count=work.obligation.minimum_specimens,
            passed=False,
        )
        ledger = record_evidence(self.release, ledger, failed)
        provider = self.release.source_adapters[0]
        for index in range(3):
            ledger = record_rejected_teaching_attempt(
                self.release, ledger,
                RejectedTeachingAttemptReceipt(
                    obligation_id=failed.obligation_id,
                    parent_evidence_id=failed.evidence_id,
                    attempt_id=f"rejected-campaign-{index}",
                    teaching_option_id=work.teaching_option_ids[0],
                    retained_checkpoint_sha256=failed.checkpoint_sha256,
                    retained_optimizer_step=failed.optimizer_step,
                    candidate_optimizer_step=failed.optimizer_step + 4,
                    retention_reason="NO_MEASURABLE_TARGET_GAIN",
                    selected_provider_id=provider.adapter_id,
                    provider_implementation_sha256=provider.implementation_sha256,
                    specimen_content_sha256=f"{index + 3:064x}",
                ))
        action = next_action(self.release, ledger)
        self.assertEqual(action.kind, AutonomyActionKind.LEARNING_EVIDENCE)
        self.assertEqual(action.evidence_work.capability_id, "A.OTHER")
        self.assertEqual(
            action.deferred_obligation_ids, (work.obligation.obligation_id,))

    def test_repeated_failed_remediation_yields_to_legal_breadth(self):
        from bilqis_mlx.factory.autonomy import record_teaching_intervention

        ledger = initial_evidence_ledger(self.release)
        work = next_work(self.release, ledger)
        parent_step = 10
        parent_sha = "1" * 64
        for cycle in range(3):
            failed = EvidenceReceipt(
                obligation_id=work.obligation.obligation_id,
                evidence_id=f"stagnation-fail-{cycle}",
                checkpoint_sha256=parent_sha,
                optimizer_step=parent_step,
                cohort_sha256=_sha(f"stagnation-cohort-{cycle}"),
                specimen_count=work.obligation.minimum_specimens,
                passed=False,
            )
            ledger = record_evidence(self.release, ledger, failed)
            intervention = self.teaching_receipt(
                failed,
                intervention_id=f"stagnation-teach-{cycle}",
                checkpoint_sha256=f"{cycle + 10:064x}",
                optimizer_step=parent_step + 1,
            )
            ledger = record_teaching_intervention(
                self.release, ledger, intervention)
            parent_step = intervention.optimizer_step
            parent_sha = intervention.checkpoint_sha256

        final_failure = EvidenceReceipt(
            obligation_id=work.obligation.obligation_id,
            evidence_id="stagnation-fail-final",
            checkpoint_sha256=parent_sha,
            optimizer_step=parent_step,
            cohort_sha256=_sha("stagnation-cohort-final"),
            specimen_count=work.obligation.minimum_specimens,
            passed=False,
        )
        ledger = record_evidence(self.release, ledger, final_failure)

        action = next_action(self.release, ledger)
        self.assertEqual(action.kind, AutonomyActionKind.LEARNING_EVIDENCE)
        self.assertEqual(action.evidence_work.capability_id, "A.OTHER")
        self.assertEqual(
            action.deferred_obligation_ids, (work.obligation.obligation_id,))

    def test_failed_evidence_requires_teaching_before_remeasurement(self):
        from bilqis_mlx.factory.autonomy import (
            AutonomyActionKind, TeachingReceipt, next_action,
            record_teaching_intervention,
        )
        ledger = initial_evidence_ledger(self.release)
        work = next_work(self.release, ledger)
        failed = self.receipt(work.obligation, passed=False)
        ledger = record_evidence(self.release, ledger, failed)

        action = next_action(self.release, ledger)
        self.assertEqual(action.kind, AutonomyActionKind.TEACHING)
        self.assertEqual(action.teaching_work.failed_evidence, failed)
        self.assertEqual(action.teaching_work.capability_id, "A.BASE")

        intervention = self.teaching_receipt(
            failed, teaching_option_id=action.teaching_work.teaching_option_ids[0])
        ledger = record_teaching_intervention(
            self.release, ledger, intervention)
        action = next_action(self.release, ledger)
        self.assertEqual(action.kind, AutonomyActionKind.LEARNING_EVIDENCE)
        self.assertEqual(action.evidence_work.obligation, work.obligation)

        passed = EvidenceReceipt(
            obligation_id=work.obligation.obligation_id,
            evidence_id="evidence-after-teaching",
            checkpoint_sha256="f" * 64,
            optimizer_step=failed.optimizer_step + 1,
            cohort_sha256="7" * 64,
            specimen_count=work.obligation.minimum_specimens,
            passed=True,
        )
        ledger = record_evidence(self.release, ledger, passed)
        self.assertNotEqual(
            next_action(self.release, ledger).kind,
            AutonomyActionKind.TEACHING,
        )

    def test_teaching_receipt_must_prove_checkpoint_progress(self):
        from bilqis_mlx.factory.autonomy import TeachingReceipt
        with self.assertRaisesRegex(ValueError, "NO_CHECKPOINT_PROGRESS"):
            TeachingReceipt(
                obligation_id="A.BASE/direct",
                intervention_id="teach-stale",
                teaching_option_id="source.direct/A.BASE",
                parent_checkpoint_sha256="e" * 64,
                parent_optimizer_step=9,
                checkpoint_sha256="e" * 64,
                optimizer_step=9,
            )

    def test_unreleased_teaching_option_is_rejected(self):
        from bilqis_mlx.factory.autonomy import (
            TeachingReceipt, next_action, record_teaching_intervention,
        )
        ledger = initial_evidence_ledger(self.release)
        work = next_work(self.release, ledger)
        failed = self.receipt(work.obligation, passed=False)
        ledger = record_evidence(self.release, ledger, failed)
        action = next_action(self.release, ledger)
        receipt = self.teaching_receipt(
            failed, intervention_id="teach-unreleased",
            teaching_option_id="fixture.not-released")
        with self.assertRaisesRegex(ValueError, "TEACHING_OPTION_NOT_RELEASED"):
            record_teaching_intervention(self.release, ledger, receipt)

    def test_new_teaching_receipt_requires_delivered_provenance(self):
        from bilqis_mlx.factory.autonomy import record_teaching_intervention
        ledger = initial_evidence_ledger(self.release)
        work = next_work(self.release, ledger)
        failed = self.receipt(work.obligation, passed=False)
        ledger = record_evidence(self.release, ledger, failed)
        receipt = self.teaching_receipt(
            failed, specimen_ids=(), specimen_content_sha256=None,
            variation_axes=(), optimizer_step_delta=None)
        with self.assertRaisesRegex(ValueError, "TEACHING_PROVENANCE_UNPROVEN"):
            record_teaching_intervention(self.release, ledger, receipt)

    def test_teaching_receipt_rejects_provider_or_axis_mutation(self):
        from bilqis_mlx.factory.autonomy import record_teaching_intervention
        ledger = initial_evidence_ledger(self.release)
        work = next_work(self.release, ledger)
        failed = self.receipt(work.obligation, passed=False)
        ledger = record_evidence(self.release, ledger, failed)
        with self.assertRaisesRegex(ValueError, "TEACHING_PROVIDER_MISMATCH"):
            record_teaching_intervention(
                self.release, ledger,
                self.teaching_receipt(failed, selected_provider_id="unbound"))
        with self.assertRaisesRegex(ValueError, "TEACHING_VARIATION_AXES_MISMATCH"):
            record_teaching_intervention(
                self.release, ledger,
                self.teaching_receipt(failed, variation_axes=("fresh-seed",)))

    def test_teaching_receipt_rejects_incorrect_step_delta(self):
        from bilqis_mlx.factory.autonomy import TeachingReceipt
        failed = self.receipt(next_work(self.release, initial_evidence_ledger(self.release)).obligation,
                              passed=False)
        with self.assertRaisesRegex(ValueError, "STEP_DELTA_INVALID"):
            self.teaching_receipt(failed, optimizer_step_delta=2)
