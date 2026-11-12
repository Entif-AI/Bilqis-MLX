"""Restart-safe autonomous curriculum orchestration over factory contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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
from ..factory.atlas_frontier import (
    AtlasCoverageEpoch,
    AtlasLearnerEvidence,
    next_atlas_delta,
)
from ..factory.atlas_delta_scope import AtlasDeltaScopeHandoff
from ..factory.atlas_frontier_progress import FrontierStatus
from .atlas_admission_policy import AdmissionResult, AdmissionStatus
from .atlas_lease_contracts import _invalid
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


class AdmissionFlywheelStatus(str, Enum):
    FIXED_POINT = "FIXED_POINT"
    WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
    HELD = "HELD"
    IMPLEMENTATION_UNCOVERED = "IMPLEMENTATION_UNCOVERED"
    LEASE_REQUIRED = "LEASE_REQUIRED"


@dataclass(frozen=True)
class AdmissionFlywheelState:
    """One custody-reloaded planner input; it grants no admission authority."""

    epoch: AtlasCoverageEpoch
    learner_evidence: AtlasLearnerEvidence
    plan: AutonomyPlan

    def __post_init__(self) -> None:
        if (type(self.epoch) is not AtlasCoverageEpoch
                or type(self.learner_evidence) is not AtlasLearnerEvidence
                or type(self.plan) is not AutonomyPlan
                or self.plan.factory_release_sha256
                   != self.epoch.current_release.release_sha256
                or self.learner_evidence.ledger.factory_release_sha256
                   != self.epoch.current_release.release_sha256
                or self.learner_evidence.ledger.autonomy_plan_sha256
                   != self.plan.digest()):
            _invalid("BAMF_ATLAS_FLYWHEEL_STATE_INVALID")
        self.epoch.verify()


@dataclass(frozen=True)
class AdmissionFlywheelResult:
    status: AdmissionFlywheelStatus
    reason: str
    advances: int
    final_state: AdmissionFlywheelState

    def __post_init__(self) -> None:
        if (not isinstance(self.status, AdmissionFlywheelStatus)
                or not isinstance(self.reason, str) or not self.reason
                or type(self.advances) is not int or self.advances < 0
                or type(self.final_state) is not AdmissionFlywheelState):
            _invalid("BAMF_ATLAS_FLYWHEEL_RESULT_INVALID")


AdmissionFlywheelStateLoader = Callable[[], AdmissionFlywheelState]
AdmissionFlywheelExecutor = Callable[[AtlasDeltaScopeHandoff], AdmissionResult]


def _flywheel_state_identity(state: AdmissionFlywheelState) -> tuple:
    epoch = state.epoch
    return (
        epoch.snapshot.snapshot_sha256,
        epoch.closure.closure_sha256,
        epoch.candidate_frontier.release_sha256,
        epoch.current_release.release_sha256,
        tuple(item.staged_sha256 for item in epoch.staged_candidates),
        None if epoch.prior is None else epoch.prior.progress_sha256,
        epoch.accepted_credit,
        state.learner_evidence.ledger,
        state.learner_evidence.checkpoint_sha256,
        state.learner_evidence.optimizer_step,
        state.plan.digest(),
    )


def _terminal_flywheel_result(
        status: FrontierStatus, state: AdmissionFlywheelState,
        advances: int) -> AdmissionFlywheelResult | None:
    mapped = {
        FrontierStatus.FIXED_POINT: AdmissionFlywheelStatus.FIXED_POINT,
        FrontierStatus.COMPLETE_ATLAS_COVERAGE: AdmissionFlywheelStatus.FIXED_POINT,
        FrontierStatus.WAITING_FOR_EVIDENCE: AdmissionFlywheelStatus.WAITING_FOR_EVIDENCE,
        FrontierStatus.SOURCE_HELD: AdmissionFlywheelStatus.HELD,
        FrontierStatus.IMPLEMENTATION_UNCOVERED:
            AdmissionFlywheelStatus.IMPLEMENTATION_UNCOVERED,
        FrontierStatus.LEASE_REQUIRED: AdmissionFlywheelStatus.LEASE_REQUIRED,
    }.get(status)
    return (None if mapped is None else
            AdmissionFlywheelResult(mapped, status.value, advances, state))


def run_admission_flywheel(
    load_state: AdmissionFlywheelStateLoader,
    admission_executor: AdmissionFlywheelExecutor,
    *,
    max_advances: int = 16,
) -> AdmissionFlywheelResult:
    """Replan only after an observed state transition; never poll or train.

    The A09 planner remains proposal-only. ``admission_executor`` is the existing
    C07 admission owner and must independently enforce lease/source/custody
    authority. The loader must rebuild its state from current accepted artifacts.
    This loop has no source-rights, grade-promotion, or MLX-training capability.
    """
    if (not callable(load_state) or not callable(admission_executor)):
        _invalid("BAMF_ATLAS_FLYWHEEL_EXECUTOR_INVALID")
    if type(max_advances) is not int or max_advances < 1:
        _invalid("BAMF_ATLAS_FLYWHEEL_ADVANCE_BUDGET_INVALID")

    state = load_state()
    if type(state) is not AdmissionFlywheelState:
        _invalid("BAMF_ATLAS_FLYWHEEL_STATE_INVALID")
    advances = 0
    while True:
        planned = next_atlas_delta(
            state.epoch, state.learner_evidence, state.plan)
        if isinstance(planned, FrontierStatus):
            terminal = _terminal_flywheel_result(planned, state, advances)
            if terminal is not None:
                return terminal
            if planned is not FrontierStatus.REPLAN_REQUIRED:
                _invalid("BAMF_ATLAS_FLYWHEEL_PLANNER_STATUS_INVALID")
            if advances >= max_advances:
                return AdmissionFlywheelResult(
                    AdmissionFlywheelStatus.HELD,
                    "ADVANCE_BUDGET_EXHAUSTED", advances, state)
            refreshed = load_state()
            if type(refreshed) is not AdmissionFlywheelState:
                _invalid("BAMF_ATLAS_FLYWHEEL_STATE_INVALID")
            if _flywheel_state_identity(refreshed) == _flywheel_state_identity(state):
                return AdmissionFlywheelResult(
                    AdmissionFlywheelStatus.HELD,
                    "REPLAN_WITHOUT_STATE_ADVANCE", advances, state)
            state = refreshed
            advances += 1
        elif isinstance(planned, AtlasDeltaScopeHandoff):
            planned.verify()
            if advances >= max_advances:
                return AdmissionFlywheelResult(
                    AdmissionFlywheelStatus.HELD,
                    "ADVANCE_BUDGET_EXHAUSTED", advances, state)
            result = admission_executor(planned)
            if not isinstance(result, AdmissionResult):
                _invalid("BAMF_ATLAS_FLYWHEEL_ADMISSION_RESULT_INVALID")
            expected_retained_release = (
                planned.staged_candidate.successor.release_sha256
                if result.status is AdmissionStatus.ADOPTED
                else state.epoch.current_release.release_sha256)
            if (result.proposal_sha256 != planned.proposal.proposal_sha256
                    or result.retained_release_sha256
                       != expected_retained_release
                    or result.staged_successor_sha256
                       != planned.staged_candidate.successor.release_sha256):
                return AdmissionFlywheelResult(
                    AdmissionFlywheelStatus.HELD,
                    "ADMISSION_RESULT_BINDING_DRIFT", advances, state)
            if result.status is AdmissionStatus.STAGED:
                status = (AdmissionFlywheelStatus.LEASE_REQUIRED
                          if ("LEASE_REQUIRED" in result.reason
                              or result.reason == "OUT_OF_LEASE_SCOPE")
                          else AdmissionFlywheelStatus.HELD)
                return AdmissionFlywheelResult(status, result.reason, advances, state)
            refreshed = load_state()
            if type(refreshed) is not AdmissionFlywheelState:
                _invalid("BAMF_ATLAS_FLYWHEEL_STATE_INVALID")
            if (refreshed.epoch.current_release.release_sha256
                    != result.staged_successor_sha256):
                return AdmissionFlywheelResult(
                    AdmissionFlywheelStatus.HELD,
                    "ADOPTED_STATE_BINDING_DRIFT", advances, state)
            if _flywheel_state_identity(refreshed) == _flywheel_state_identity(state):
                return AdmissionFlywheelResult(
                    AdmissionFlywheelStatus.HELD,
                    "ADOPTED_WITHOUT_STATE_ADVANCE", advances, state)
            state = refreshed
            advances += 1
        else:
            _invalid("BAMF_ATLAS_FLYWHEEL_PLANNER_RESULT_INVALID")


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
