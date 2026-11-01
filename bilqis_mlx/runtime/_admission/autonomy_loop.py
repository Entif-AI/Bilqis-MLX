"""Restart-safe autonomous curriculum orchestration over factory contracts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..factory.autonomy import (
    AutonomyAction,
    AutonomyActionKind,
    AutonomyPlan,
    CurriculumWorkItem,
    EvidenceLedger,
    EvidenceReceipt,
    TeachingReceipt,
    TeachingWorkItem,
    next_action,
    rebind_evidence_ledger,
    record_evidence,
    record_teaching_intervention,
)
from ..factory.model import FactoryRelease
from .autonomy_state import persist_autonomy_state


SourceCoverageExecutor = Callable[[str, AutonomyPlan], AutonomyPlan]
LearningEvidenceExecutor = Callable[[CurriculumWorkItem], EvidenceReceipt]
TeachingExecutor = Callable[[TeachingWorkItem], TeachingReceipt]


@dataclass(frozen=True)
class AutonomyRunResult:
    action: AutonomyAction
    plan: AutonomyPlan
    ledger: EvidenceLedger
    steps: int

    def __post_init__(self) -> None:
        if (not isinstance(self.action, AutonomyAction) or
                not isinstance(self.plan, AutonomyPlan) or
                not isinstance(self.ledger, EvidenceLedger) or
                type(self.steps) is not int or self.steps < 0):
            raise ValueError("AUTONOMY_RUN_RESULT_INVALID")


def _validate_run_inputs(
        release, plan, ledger, source_coverage_executor,
        learning_evidence_executor, max_steps: int) -> None:
    if not isinstance(release, FactoryRelease):
        raise TypeError("AUTONOMY_RELEASE_REQUIRED")
    if (not isinstance(plan, AutonomyPlan) or
            not isinstance(ledger, EvidenceLedger) or
            not callable(source_coverage_executor) or
            not callable(learning_evidence_executor)):
        raise TypeError("AUTONOMY_EXECUTOR_INPUT_INVALID")
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("AUTONOMY_STEP_BUDGET_INVALID")


def _next_autonomy_action(
        release: FactoryRelease, plan: AutonomyPlan, ledger: EvidenceLedger,
        checkpoint_sha256: str, optimizer_step: int) -> AutonomyAction:
    return next_action(
        release, ledger, plan=plan,
        current_checkpoint_sha256=checkpoint_sha256,
        current_optimizer_step=optimizer_step,
    )


def _apply_source_coverage(
        release: FactoryRelease, plan: AutonomyPlan, ledger: EvidenceLedger,
        action: AutonomyAction, executor: SourceCoverageExecutor):
    updated_plan = executor(action.source_coverage_debt, plan)
    if not isinstance(updated_plan, AutonomyPlan):
        raise TypeError("AUTONOMY_SOURCE_EXECUTOR_RESULT_INVALID")
    if updated_plan.factory_release_sha256 != release.release_sha256:
        raise ValueError("AUTONOMY_SOURCE_EXECUTOR_RELEASE_DRIFT")
    if (updated_plan.digest() == plan.digest() or
            action.source_coverage_debt in updated_plan.coverage_debt or
            len(updated_plan.coverage_debt) >= len(plan.coverage_debt)):
        raise ValueError("AUTONOMY_SOURCE_EXECUTOR_NO_PROGRESS")
    return updated_plan, rebind_evidence_ledger(
        release, ledger, old_plan=plan, new_plan=updated_plan)


def _apply_learning_evidence(
        release: FactoryRelease, plan: AutonomyPlan, ledger: EvidenceLedger,
        action: AutonomyAction, executor: LearningEvidenceExecutor,
        checkpoint_sha256: str, optimizer_step: int) -> EvidenceLedger:
    receipt = executor(action.evidence_work)
    if not isinstance(receipt, EvidenceReceipt):
        raise TypeError("AUTONOMY_EVIDENCE_EXECUTOR_RESULT_INVALID")
    return record_evidence(
        release, ledger, receipt, plan=plan,
        current_checkpoint_sha256=checkpoint_sha256,
        current_optimizer_step=optimizer_step,
    )


def _apply_teaching(
        release: FactoryRelease, plan: AutonomyPlan, ledger: EvidenceLedger,
        action: AutonomyAction, executor: TeachingExecutor | None,
        checkpoint_sha256: str, optimizer_step: int):
    if executor is None:
        raise ValueError("AUTONOMY_TEACHING_EXECUTOR_REQUIRED")
    receipt = executor(action.teaching_work)
    if not isinstance(receipt, TeachingReceipt):
        raise TypeError("AUTONOMY_TEACHING_EXECUTOR_RESULT_INVALID")
    updated = record_teaching_intervention(
        release, ledger, receipt, plan=plan,
        current_checkpoint_sha256=checkpoint_sha256,
        current_optimizer_step=optimizer_step,
    )
    return updated, receipt.checkpoint_sha256, receipt.optimizer_step


def _execute_autonomy_action(
        release: FactoryRelease, plan: AutonomyPlan, ledger: EvidenceLedger,
        action: AutonomyAction, source_coverage_executor: SourceCoverageExecutor,
        learning_evidence_executor: LearningEvidenceExecutor,
        teaching_executor: TeachingExecutor | None,
        checkpoint_sha256: str, optimizer_step: int):
    if action.kind is AutonomyActionKind.SOURCE_COVERAGE:
        plan, ledger = _apply_source_coverage(
            release, plan, ledger, action, source_coverage_executor)
        return plan, ledger, checkpoint_sha256, optimizer_step
    if action.kind is AutonomyActionKind.LEARNING_EVIDENCE:
        ledger = _apply_learning_evidence(
            release, plan, ledger, action, learning_evidence_executor,
            checkpoint_sha256, optimizer_step)
        return plan, ledger, checkpoint_sha256, optimizer_step
    if action.kind is AutonomyActionKind.TEACHING:
        ledger, checkpoint_sha256, optimizer_step = _apply_teaching(
            release, plan, ledger, action, teaching_executor,
            checkpoint_sha256, optimizer_step)
        return plan, ledger, checkpoint_sha256, optimizer_step
    raise ValueError("AUTONOMY_ACTION_UNHANDLED")


def run_until_qualification(
    run_dir: Path,
    release: FactoryRelease,
    *,
    plan: AutonomyPlan,
    ledger: EvidenceLedger,
    source_coverage_executor: SourceCoverageExecutor,
    learning_evidence_executor: LearningEvidenceExecutor,
    current_checkpoint_sha256: str,
    current_optimizer_step: int,
    teaching_executor: TeachingExecutor | None = None,
    max_steps: int = 256,
) -> AutonomyRunResult:
    """Execute bounded neural-inert curriculum work until qualification is due.

    Executors are capability providers.  This loop owns ordering, validation,
    migration, persistence, and fail-closed progress checks; it does not own
    neural updates or qualification/admission decisions.
    """
    _validate_run_inputs(
        release, plan, ledger, source_coverage_executor,
        learning_evidence_executor, max_steps)
    persist_autonomy_state(run_dir, release, plan=plan, ledger=ledger)
    current_plan, current_ledger = plan, ledger
    for step in range(max_steps):
        action = _next_autonomy_action(
            release, current_plan, current_ledger,
            current_checkpoint_sha256, current_optimizer_step)
        if action.kind is AutonomyActionKind.QUALIFICATION:
            return AutonomyRunResult(action, current_plan, current_ledger, step)
        (current_plan, current_ledger,
         current_checkpoint_sha256, current_optimizer_step) = _execute_autonomy_action(
            release, current_plan, current_ledger, action,
            source_coverage_executor, learning_evidence_executor,
            teaching_executor, current_checkpoint_sha256, current_optimizer_step)
        persist_autonomy_state(
            run_dir, release, plan=current_plan, ledger=current_ledger)
    action = _next_autonomy_action(
        release, current_plan, current_ledger,
        current_checkpoint_sha256, current_optimizer_step)
    if action.kind is AutonomyActionKind.QUALIFICATION:
        return AutonomyRunResult(action, current_plan, current_ledger, max_steps)
    raise ValueError("AUTONOMY_STEP_BUDGET_EXHAUSTED")
