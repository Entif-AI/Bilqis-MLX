"""Read-only, explicitly unratified capability-health replay proposals."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json

from .observations import ExamObservation


class ShadowHealthState(str, Enum):
    ACTIVE = "ACTIVE"
    WATCH = "WATCH"
    QUARANTINE_RECOMMENDATION = "QUARANTINE_RECOMMENDATION"
    RECOVERY_RECOMMENDATION = "RECOVERY_RECOMMENDATION"
    REINTEGRATION_RECOMMENDATION = "REINTEGRATION_RECOMMENDATION"
    NOT_MEASURED = "NOT_MEASURED"


class ShadowPhase(str, Enum):
    ACQUISITION = "ACQUISITION"
    REPLAY = "REPLAY"


@dataclass(frozen=True)
class ShadowContext:
    active_grade: str
    phase: ShadowPhase

    def __post_init__(self) -> None:
        if len(self.active_grade) != 1 or not self.active_grade.isalpha() or not self.active_grade.isupper():
            raise ValueError("SHADOW_ACTIVE_GRADE_INVALID")


@dataclass(frozen=True)
class ShadowPolicy:
    """Required research experiment configuration; no policy defaults exist."""
    experiment_id: str
    version: str
    minimum_support: int
    hysteresis_observations: int
    minimum_score_drop: int
    baseline_margin: int
    normal_variation_maximum: int

    def __post_init__(self) -> None:
        if not self.experiment_id or not self.version:
            raise ValueError("SHADOW_POLICY_IDENTITY_REQUIRED")
        if self.minimum_support < 3 or self.hysteresis_observations < 2:
            raise ValueError("SHADOW_POLICY_INSUFFICIENT_SUPPORT")
        if min(self.minimum_score_drop, self.baseline_margin,
               self.normal_variation_maximum) < 0 or self.minimum_score_drop < 1:
            raise ValueError("SHADOW_POLICY_INVALID_THRESHOLD")

    @property
    def digest(self) -> str:
        return sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ShadowCapabilityProposal:
    capability: str
    state: ShadowHealthState
    evidence_count: int
    trajectory: tuple[tuple[int, int, int], ...]
    note: str
    unratified: bool = True


@dataclass(frozen=True)
class ShadowReviewAlert:
    capability: str
    delivery: str
    state: ShadowHealthState
    note: str
    evidence_sha256: str
    action: str
    consequence_if_deferred: str


@dataclass(frozen=True)
class ShadowReplay:
    policy: ShadowPolicy
    policy_digest: str
    by_capability: dict[str, ShadowCapabilityProposal]
    end_of_run_alerts: tuple[ShadowReviewAlert, ...]
    required_capability_debt: tuple[str, ...]
    lineage_gap: bool
    lineage_note: str
    excluded_from_mastery: tuple[str, ...] = ()
    lineage_sha256: str = ""

    @property
    def proposed_quarantine(self) -> tuple[str, ...]:
        return tuple(capability for capability, proposal in self.by_capability.items()
                     if proposal.state is ShadowHealthState.QUARANTINE_RECOMMENDATION)

    @property
    def proposed_active_capabilities(self) -> tuple[str, ...]:
        return tuple(capability for capability in self.by_capability
                     if capability not in self.proposed_quarantine)


def changed_shadow_alerts(previous: ShadowReplay | None,
                         current: ShadowReplay) -> tuple[ShadowReviewAlert, ...]:
    """Batch one notice per state change within one comparable experiment.

    The caller may retain the previous report through its existing evidence
    channel. No live teacher, run state or new warning ledger is written here.
    """
    comparable = (previous is not None and previous.policy_digest == current.policy_digest
                  and previous.lineage_sha256 == current.lineage_sha256)
    return tuple(alert for alert in current.end_of_run_alerts
                 if not comparable or alert.capability not in previous.by_capability or
                 alert.state != previous.by_capability[alert.capability].state)


def _complete_lineage(observation: ExamObservation) -> bool:
    return all((observation.run_id, observation.cohort_sha256, observation.student_sha256,
                observation.rubric_sha256, observation.generator_version,
                observation.source_manifest_sha256, observation.generator_code_sha256,
                observation.assessment_scope_sha256))


def _validate(observation: ExamObservation) -> None:
    identifiers = [cap.capability for cap in observation.capabilities]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("SHADOW_DUPLICATE_CAPABILITY_ID")
    for cap in observation.capabilities:
        if not (0 <= cap.correct <= cap.total and cap.total > 0):
            raise ValueError("SHADOW_INVALID_CORRECT_TOTAL:" + cap.capability)


def _lineage(observation: ExamObservation) -> tuple[object, ...]:
    return observation.run_id, observation.contract, observation.cohort_sha256


def _latest_segment(history: tuple[ExamObservation, ...]) -> tuple[tuple[ExamObservation, ...], bool]:
    """Keep the latest contiguous same-lineage suffix; expose preceding drift."""
    if not history:
        return (), False
    for observation in history:
        _validate(observation)
    if not _complete_lineage(history[-1]):
        return (), True
    latest = _lineage(history[-1])
    start = len(history) - 1
    while start and _complete_lineage(history[start - 1]) and _lineage(history[start - 1]) == latest:
        start -= 1
    return history[start:], start != 0


def _series(segment: tuple[ExamObservation, ...], capability: str) -> tuple[tuple[int, int, int, int | None], ...] | None:
    rows = []
    for observation in segment:
        cap = next((candidate for candidate in observation.capabilities if candidate.capability == capability), None)
        if cap is None:
            return None
        rows.append((observation.optimizer_step, cap.correct, cap.total,
                     cap.majority_baseline if cap.baseline_measured else None))
    if (not rows or len({step for step, _, _, _ in rows}) != len(rows) or
            len({observation.student_sha256 for observation in segment}) != len(segment) or
            any(later[0] <= earlier[0] for earlier, later in zip(rows, rows[1:])) or
            len({total for _, _, total, _ in rows}) != 1):
        return None
    return tuple(rows)


def _prior_sustained(values: tuple[int, ...], predicate, width: int) -> bool:
    return any(all(predicate(value) for value in values[index:index + width])
               for index in range(len(values) - width))


def _proposal(capability: str, series: tuple[tuple[int, int, int, int | None], ...] | None,
              policy: ShadowPolicy, context: ShadowContext) -> ShadowCapabilityProposal:
    if series is None:
        return ShadowCapabilityProposal(capability, ShadowHealthState.NOT_MEASURED, 0, (),
                                        "NOT_MEASURED: required immutable lineage or capability is absent")
    trajectory = tuple((step, correct, total) for step, correct, total, _ in series)
    if len(series) < policy.minimum_support:
        return ShadowCapabilityProposal(capability, ShadowHealthState.NOT_MEASURED, len(series), trajectory,
                                        "NOT_MEASURED: experiment minimum support is not met")
    scores = tuple(correct for _, correct, _, _ in series)
    baselines = tuple(baseline for *_, baseline in series)
    if any(baseline is None for baseline in baselines):
        return ShadowCapabilityProposal(capability, ShadowHealthState.NOT_MEASURED, len(series), trajectory,
                                        "NOT_MEASURED: capability-relative baseline is absent")
    prior_peak, latest = max(scores[:-1]), scores[-1]
    regressed = lambda score: prior_peak - score >= policy.minimum_score_drop
    stable_low = (max(scores) - min(scores) <= policy.normal_variation_maximum and
                  all(score <= baseline + policy.baseline_margin
                      for score, baseline in zip(scores, baselines)))
    sustained_regression = _prior_sustained(scores, regressed, policy.hysteresis_observations)
    earlier_grade = capability.split(".", 1)[0] < context.active_grade
    suppress = earlier_grade and context.phase is ShadowPhase.ACQUISITION
    if sustained_regression and latest > scores[-2]:
        state = (ShadowHealthState.REINTEGRATION_RECOMMENDATION if latest == series[-1][2]
                 else ShadowHealthState.RECOVERY_RECOMMENDATION)
    elif regressed(latest):
        trailing = 0
        for score in reversed(scores):
            if not regressed(score):
                break
            trailing += 1
        state = (ShadowHealthState.QUARANTINE_RECOMMENDATION
                 if trailing >= policy.hysteresis_observations and not suppress else ShadowHealthState.WATCH)
    elif stable_low:
        # Stable low results establish no improving excursion, but do not
        # establish an intervention effect or a calibrated containment rule.
        state = ShadowHealthState.WATCH
    else:
        state = ShadowHealthState.ACTIVE
    note = "UNRATIFIED: capability-relative experimental proposal only"
    if suppress and state is ShadowHealthState.WATCH:
        note += "; earlier-grade acquisition context suppresses containment"
    return ShadowCapabilityProposal(capability, state, len(series), trajectory, note)


def replay_health_shadow(history: tuple[ExamObservation, ...], *, required_capabilities: tuple[str, ...],
                         policy: ShadowPolicy, context: ShadowContext) -> ShadowReplay:
    """Replay only the latest comparable lineage; never control a live run."""
    if len(set(required_capabilities)) != len(required_capabilities):
        raise ValueError("SHADOW_REQUIRED_CAPABILITY_DUPLICATE")
    segment, gap = _latest_segment(history)
    proposals = {capability: _proposal(capability, _series(segment, capability), policy, context)
                 for capability in required_capabilities}
    latest = {cap.capability: cap for cap in segment[-1].capabilities} if segment else {}
    debt = tuple(capability for capability in required_capabilities
                 if capability not in latest or latest[capability].correct != latest[capability].total)
    alert_states = {ShadowHealthState.WATCH, ShadowHealthState.QUARANTINE_RECOMMENDATION,
                    ShadowHealthState.RECOVERY_RECOMMENDATION, ShadowHealthState.REINTEGRATION_RECOMMENDATION}
    lineage = sha256(json.dumps(_lineage(segment[-1]) if segment else None,
                               separators=(",", ":")).encode()).hexdigest()
    alerts = tuple(ShadowReviewAlert(capability, "END_OF_RUN_REVIEW", proposal.state, proposal.note,
                   sha256(json.dumps({"policy": policy.digest, "lineage": lineage,
                       "checkpoints": [(obs.optimizer_step, obs.student_sha256, obs.event_outbox_verified)
                                       for obs in segment],
                       "proposal": asdict(proposal)}, sort_keys=True,
                       separators=(",", ":")).encode()).hexdigest(),
                   "Review the source-bound trajectory and qualify any proposed intervention before activation",
                   "Live training is unchanged; unresolved required capability remains learning debt")
                   for capability, proposal in proposals.items() if proposal.state in alert_states)
    note = ("Latest contiguous source/exam/checkpoint lineage selected; earlier lineage drift excluded"
            if gap else "Entire supplied history is one comparable source/exam/checkpoint lineage")
    return ShadowReplay(policy, policy.digest, proposals, alerts, debt, gap, note,
                        lineage_sha256=lineage)
