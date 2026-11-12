"""Event-driven C07 admission flywheel over existing A09/C07 authorities."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from ..factory.atlas_frontier import (
    AtlasCoverageEpoch,
    AtlasLearnerEvidence,
    next_atlas_delta,
)
from ..factory.atlas_delta_scope import AtlasDeltaScopeHandoff
from ..factory.atlas_frontier_progress import FrontierStatus
from ..factory.autonomy import AutonomyPlan
from .atlas_admission_policy import AdmissionResult, AdmissionStatus
from .atlas_lease_contracts import _invalid


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
                    or result.retained_release_sha256 != expected_retained_release
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
