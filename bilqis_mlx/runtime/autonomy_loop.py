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
    next_action,
    rebind_evidence_ledger,
    record_evidence,
)
from ..factory.model import FactoryRelease
from .autonomy_state import persist_autonomy_state


SourceCoverageExecutor = Callable[[str, AutonomyPlan], AutonomyPlan]
LearningEvidenceExecutor = Callable[[CurriculumWorkItem], EvidenceReceipt]


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


def run_until_qualification(
    run_dir: Path,
    release: FactoryRelease,
    *,
    plan: AutonomyPlan,
    ledger: EvidenceLedger,
    source_coverage_executor: SourceCoverageExecutor,
    learning_evidence_executor: LearningEvidenceExecutor,
    max_steps: int = 256,
) -> AutonomyRunResult:
    """Execute bounded neural-inert curriculum work until qualification is due.

    Executors are capability providers.  This loop owns ordering, validation,
    migration, persistence, and fail-closed progress checks; it does not own
    neural updates or qualification/admission decisions.
    """
    if not isinstance(release, FactoryRelease):
        raise TypeError("AUTONOMY_RELEASE_REQUIRED")
    if (not isinstance(plan, AutonomyPlan) or not isinstance(ledger, EvidenceLedger) or
            not callable(source_coverage_executor) or
            not callable(learning_evidence_executor)):
        raise TypeError("AUTONOMY_EXECUTOR_INPUT_INVALID")
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("AUTONOMY_STEP_BUDGET_INVALID")

    persist_autonomy_state(run_dir, release, plan=plan, ledger=ledger)
    current_plan, current_ledger = plan, ledger
    for step in range(max_steps):
        action = next_action(release, current_ledger, plan=current_plan)
        if action.kind is AutonomyActionKind.QUALIFICATION:
            return AutonomyRunResult(action, current_plan, current_ledger, step)

        if action.kind is AutonomyActionKind.SOURCE_COVERAGE:
            updated_plan = source_coverage_executor(
                action.source_coverage_debt, current_plan)
            if not isinstance(updated_plan, AutonomyPlan):
                raise TypeError("AUTONOMY_SOURCE_EXECUTOR_RESULT_INVALID")
            if updated_plan.factory_release_sha256 != release.release_sha256:
                raise ValueError("AUTONOMY_SOURCE_EXECUTOR_RELEASE_DRIFT")
            if (updated_plan.digest() == current_plan.digest() or
                    action.source_coverage_debt in updated_plan.coverage_debt or
                    len(updated_plan.coverage_debt) >= len(current_plan.coverage_debt)):
                raise ValueError("AUTONOMY_SOURCE_EXECUTOR_NO_PROGRESS")
            current_ledger = rebind_evidence_ledger(
                release, current_ledger,
                old_plan=current_plan, new_plan=updated_plan)
            current_plan = updated_plan
        elif action.kind is AutonomyActionKind.LEARNING_EVIDENCE:
            receipt = learning_evidence_executor(action.evidence_work)
            if not isinstance(receipt, EvidenceReceipt):
                raise TypeError("AUTONOMY_EVIDENCE_EXECUTOR_RESULT_INVALID")
            current_ledger = record_evidence(
                release, current_ledger, receipt, plan=current_plan)
        else:
            raise ValueError("AUTONOMY_ACTION_UNHANDLED")

        persist_autonomy_state(
            run_dir, release, plan=current_plan, ledger=current_ledger)

    action = next_action(release, current_ledger, plan=current_plan)
    if action.kind is AutonomyActionKind.QUALIFICATION:
        return AutonomyRunResult(action, current_plan, current_ledger, max_steps)
    raise ValueError("AUTONOMY_STEP_BUDGET_EXHAUSTED")
