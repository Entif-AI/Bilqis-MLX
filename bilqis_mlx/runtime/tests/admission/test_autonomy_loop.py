from dataclasses import dataclass
from pathlib import Path
import hashlib
import tempfile
import unittest

from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.curriculum_compiler import compile_ast
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.autonomy import (
    AutonomyActionKind, EvidenceReceipt, TeachingReceipt, compile_autonomy_plan,
    initial_evidence_ledger,
)
from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.runtime.autonomy_loop import run_until_qualification
from bilqis_mlx.runtime.autonomy_state import read_autonomy_state


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


class AutonomousRuntimeLoopTests(unittest.TestCase):
    def setUp(self):
        names = ("A.BASE", "A.OTHER", "A.COMPOSITE", "A.F3", "A.F4", "A.F5")
        caps = []
        for name in names:
            prerequisites = (("A.BASE", "A.OTHER") if name == "A.COMPOSITE" else ())
            caps.append(Capability(
                id=name, difficulty="fixture", source_anchor="repo:fixture/autonomy-loop",
                taught_roots=("fixture." + name.lower(),),
                examined_roots=("fixture." + name.lower(),),
                prerequisites=prerequisites, composed_of=prerequisites,
                answer_families=(AnswerFamily("binary", BINARY),),
                lesson_generator="fixture.autonomy-loop/v1",
                independent_oracle="fixture.autonomy-loop-oracle/v1",
            ))
        grade = Grade(
            "A", tuple(caps), assessment_sha256="a" * 64,
            exam_item_counts=tuple((name, 4) for name in names),
            teaching_stages=(("A.BASE", "A.OTHER"),
                             ("A.COMPOSITE", "A.F3", "A.F4", "A.F5")),
        )
        course = Course((grade,), "fixture.autonomy-loop/v1", "b" * 64, "a" * 64)
        descriptor = SourceAdapter(
            "fixture.autonomy-loop-adapter/v1", "fixture.autonomy-loop/v1",
            ("fixture.autonomy-loop-oracle/v1",), "d" * 64)
        registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            descriptor, lambda **_: (), lambda row, **_: True),))
        self.release = compile_factory_release(course, registry)
        self.receipt_index = 0

    def report(self, *, covered):
        status = "SOURCE_CONTRAST_COVERED" if covered else "AWAITING_SOURCE_WITNESS"
        return {
            "schema": "bilqis.mlx.semantic-composition-coverage/v1",
            "ast_sha256": compile_ast(self.release.course).digest(),
            "registry_sha256": "9" * 64,
            "capabilities": tuple(item.capability_id for item in self.release.capabilities),
            "obligations": ({
                "consumer": "A.F3", "producer": "A.BASE", "operand_slot": 0,
                "operand_type": "Boolean", "status": status,
                "declared_prerequisite": True,
                "coverage_debt": not covered,
                "witness_ids": ("witness-1",) if covered else (),
            },),
            "unresolved": (), "source_witness_cohort_sha256": "8" * 64,
            "training_authorized": False,
        }

    def evidence(self, work):
        self.receipt_index += 1
        return EvidenceReceipt(
            obligation_id=work.obligation.obligation_id,
            evidence_id=f"evidence-{self.receipt_index}",
            checkpoint_sha256="e" * 64, optimizer_step=0,
            cohort_sha256=sha(f"cohort-{self.receipt_index}"),
            specimen_count=work.obligation.minimum_specimens, passed=True,
        )

    def test_loop_repairs_source_debt_collects_evidence_and_persists_each_step(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan = compile_autonomy_plan(self.release, self.report(covered=False))
            ledger = initial_evidence_ledger(self.release, plan=plan)
            source_calls = []

            def source_executor(debt, current_plan):
                source_calls.append(debt)
                self.assertEqual(current_plan, plan)
                return compile_autonomy_plan(self.release, self.report(covered=True))

            result = run_until_qualification(
                root, self.release, plan=plan, ledger=ledger,
                source_coverage_executor=source_executor,
                learning_evidence_executor=self.evidence,
                current_checkpoint_sha256="e" * 64,
                current_optimizer_step=0,
                max_steps=64,
            )
            self.assertEqual(result.action.kind, AutonomyActionKind.QUALIFICATION)
            self.assertEqual(source_calls,
                             ["A.F3:A.BASE:0:AWAITING_SOURCE_WITNESS"])
            self.assertGreater(len(result.ledger.receipts), 0)
            restored_plan, restored_ledger = read_autonomy_state(root, self.release)
            self.assertEqual(restored_plan, result.plan)
            self.assertEqual(restored_ledger, result.ledger)

    def test_loop_rejects_executor_that_does_not_make_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = compile_autonomy_plan(self.release, self.report(covered=False))
            ledger = initial_evidence_ledger(self.release, plan=plan)
            with self.assertRaisesRegex(ValueError, "AUTONOMY_SOURCE_EXECUTOR_NO_PROGRESS"):
                run_until_qualification(
                    Path(temp), self.release, plan=plan, ledger=ledger,
                    source_coverage_executor=lambda debt, current: current,
                    learning_evidence_executor=self.evidence,
                    current_checkpoint_sha256="e" * 64,
                    current_optimizer_step=0,
                    max_steps=4,
                )

    def test_loop_has_hard_iteration_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = compile_autonomy_plan(self.release)
            ledger = initial_evidence_ledger(self.release, plan=plan)
            with self.assertRaisesRegex(ValueError, "AUTONOMY_STEP_BUDGET_EXHAUSTED"):
                run_until_qualification(
                    Path(temp), self.release, plan=plan, ledger=ledger,
                    source_coverage_executor=lambda debt, current: current,
                    learning_evidence_executor=self.evidence,
                    current_checkpoint_sha256="e" * 64,
                    current_optimizer_step=0,
                    max_steps=1,
                )

    def test_failed_evidence_triggers_teaching_then_remeasurement(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = compile_autonomy_plan(self.release)
            ledger = initial_evidence_ledger(self.release, plan=plan)
            checkpoint = {"sha256": "e" * 64, "optimizer_step": 0}
            evidence_calls = {}
            teaching_calls = []

            def evidence_executor(work):
                key = work.obligation.obligation_id
                evidence_calls[key] = evidence_calls.get(key, 0) + 1
                passed = not (key == "A.BASE/direct" and evidence_calls[key] == 1)
                self.receipt_index += 1
                return EvidenceReceipt(
                    obligation_id=key,
                    evidence_id=f"runtime-evidence-{self.receipt_index}",
                    checkpoint_sha256=checkpoint["sha256"],
                    optimizer_step=checkpoint["optimizer_step"],
                    cohort_sha256=sha(f"runtime-cohort-{self.receipt_index}"),
                    specimen_count=work.obligation.minimum_specimens,
                    passed=passed,
                )

            def teaching_executor(work):
                teaching_calls.append(work.obligation.obligation_id)
                parent = dict(checkpoint)
                checkpoint["sha256"] = "f" * 64
                checkpoint["optimizer_step"] += 1
                definition = {
                    item.capability_id: item for item in self.release.capabilities
                }[work.capability_id]
                provider = {
                    item.adapter_id: item
                    for item in self.release.source_adapters
                }[definition.source_adapter_id]
                coverage = {
                    item.capability_id: item
                    for item in self.release.coverage_plans
                }[work.capability_id]
                rows = ({"id": "runtime-teaching-row-1",
                         "capability": work.capability_id,
                         "gold": "1"},)
                return TeachingReceipt(
                    obligation_id=work.obligation.obligation_id,
                    intervention_id="runtime-teach-1",
                    teaching_option_id=work.teaching_option_ids[0],
                    parent_checkpoint_sha256=parent["sha256"],
                    parent_optimizer_step=parent["optimizer_step"],
                    checkpoint_sha256=checkpoint["sha256"],
                    optimizer_step=checkpoint["optimizer_step"],
                    selected_provider_id=provider.adapter_id,
                    provider_implementation_sha256=provider.implementation_sha256,
                    specimen_ids=("runtime-teaching-row-1",),
                    specimen_content_sha256=content_digest(rows),
                    variation_axes=coverage.variation_axes,
                    optimizer_step_delta=1,
                )

            result = run_until_qualification(
                Path(temp), self.release, plan=plan, ledger=ledger,
                source_coverage_executor=lambda debt, current: current,
                learning_evidence_executor=evidence_executor,
                teaching_executor=teaching_executor,
                current_checkpoint_sha256=checkpoint["sha256"],
                current_optimizer_step=checkpoint["optimizer_step"],
                max_steps=64,
            )
            self.assertEqual(result.action.kind, AutonomyActionKind.QUALIFICATION)
            self.assertEqual(teaching_calls, ["A.BASE/direct"])
            self.assertEqual(evidence_calls["A.BASE/direct"], 2)
            self.assertEqual(len(result.ledger.interventions), 1)


if __name__ == "__main__":
    unittest.main()
