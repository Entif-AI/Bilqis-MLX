"""Evidence-limited learning diagnostics over source-scored exam observations.

These findings do not change the learned teacher or stop a grade in progress.
Five signal identities preserve the user's original warning questions. The
current observable source supports only S1/S2; S3-S5 stay NOT_MEASURED until
delivered/retained instruction and typed prerequisite/minimality evidence exist.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable

from .observations import CapabilityObservation, ExamObservation, aggregate_capabilities


class LearningSignal(str, Enum):
    REPETITIVE_ANSWERS = "REPETITIVE_ANSWERS"
    CHANCE_LEVEL_OR_LAGGING = "CHANCE_LEVEL_OR_LAGGING"
    LACK_OF_DURABLE_GAIN = "LACK_OF_DURABLE_GAIN"
    DISCONNECTED_PREREQUISITES = "DISCONNECTED_PREREQUISITES"
    EXCESSIVE_INTRODUCTORY_COMPLEXITY = "EXCESSIVE_INTRODUCTORY_COMPLEXITY"


class DiagnosticStatus(str, Enum):
    OBSERVED_IN_COHORT = "OBSERVED_IN_COHORT"
    OBSERVED_LONGITUDINALLY = "OBSERVED_LONGITUDINALLY"
    NOT_OBSERVED = "NOT_OBSERVED"
    NOT_MEASURED = "NOT_MEASURED"


class ObservationScope(str, Enum):
    SINGLE_COHORT = "SINGLE_COHORT"
    DISTINCT_COHORT_SERIES = "DISTINCT_COHORT_SERIES"


class DiagnosticTarget(str, Enum):
    CAPABILITY = "CAPABILITY"
    GRADE = "GRADE"
    WHOLE_STUDENT = "WHOLE_STUDENT"


@dataclass(frozen=True)
class DiagnosticFinding:
    signal: LearningSignal
    status: DiagnosticStatus
    capability: str
    target: DiagnosticTarget
    scope: ObservationScope
    evidence_count: int
    observed_correct: int | None
    observed_total: int | None
    majority_baseline: int | None
    source_cohorts: tuple[str, ...]
    note: str


def _inspect_capability(cap: CapabilityObservation, cohort_sha256: str,
                        target: DiagnosticTarget) -> tuple[DiagnosticFinding, ...]:
    scope = ObservationScope.SINGLE_COHORT
    repeated = (cap.constant_prediction and cap.mixed_gold)
    # This is a *within-cohort* observation. A diagnosis of learned collapse
    # across time requires distinct source-verified cohorts below.
    s1 = DiagnosticFinding(
        LearningSignal.REPETITIVE_ANSWERS,
        DiagnosticStatus.OBSERVED_IN_COHORT if repeated else DiagnosticStatus.NOT_OBSERVED,
        cap.capability, target, scope, cap.total, cap.correct, cap.total,
        cap.majority_baseline, (cohort_sha256,),
        "Constant output on both source-attested gold classes" if repeated else
        "No constant output across mixed-gold examples",
    )
    # Scoring below the observable majority-class baseline is a useful
    # warning, not a statistical proof of nonlearning or chance stagnation.
    below_baseline = cap.correct <= cap.majority_baseline
    s2 = DiagnosticFinding(
        LearningSignal.CHANCE_LEVEL_OR_LAGGING,
        DiagnosticStatus.OBSERVED_IN_COHORT if below_baseline else DiagnosticStatus.NOT_OBSERVED,
        cap.capability, target, scope, cap.total, cap.correct, cap.total,
        cap.majority_baseline, (cohort_sha256,),
        "Observed correctness at or below the gold majority baseline" if below_baseline else
        "Observed correctness above the gold majority baseline",
    )
    if not cap.mixed_gold:
        note = "A single gold class cannot distinguish collapse or baseline-level learning"
        s1 = replace(s1, status=DiagnosticStatus.NOT_MEASURED, note=note)
    if not cap.baseline_measured:
        s2 = replace(s2, status=DiagnosticStatus.NOT_MEASURED,
                     note="Each constituent capability needs both gold classes for baseline discrimination")
    missing = {
        LearningSignal.LACK_OF_DURABLE_GAIN:
            "Requires delivered lessons, new source-cohort retest and delayed retention comparisons",
        LearningSignal.DISCONNECTED_PREREQUISITES:
            "Requires typed approved prerequisite closure, legal world bridges and actual exposure",
        LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY:
            "Requires source-verified minimal introduction and delivered complexity evidence",
    }
    return (s1, s2, *(DiagnosticFinding(
        signal, DiagnosticStatus.NOT_MEASURED, cap.capability, target, scope, 0,
        None, None, None, (cohort_sha256,), reason,
    ) for signal, reason in missing.items()))


def diagnose_exam(observation: ExamObservation) -> tuple[DiagnosticFinding, ...]:
    """Observe, never intervene. Same tested vocabulary as original warnings."""
    return tuple(finding for cap, target in _targets(observation)
        for finding in _inspect_capability(cap, observation.cohort_sha256, target))


def _targets(observation):
    yield from ((cap, DiagnosticTarget.CAPABILITY) for cap in observation.capabilities)
    for grade in sorted({c.capability.split(".", 1)[0] for c in observation.capabilities}):
        yield observation.grade_total(grade), DiagnosticTarget.GRADE
    yield aggregate_capabilities("*", observation.capabilities), DiagnosticTarget.WHOLE_STUDENT


def diagnose_history(observations: Iterable[ExamObservation]) -> tuple[DiagnosticFinding, ...]:
    """Mark repeated S1/S2 signals only across *distinct* saved cohorts.

    No inference of durable forgetting can follow from independently sampled
    exam scores without evidence of what was actually taught in between.
    """
    history = tuple(sorted(observations, key=lambda obs: obs.optimizer_step))
    if len({o.cohort_sha256 for o in history}) != len(history):
        raise ValueError("DIAGNOSTIC_REPEATED_COHORT_IS_NOT_NEW_EVIDENCE")
    if (len({o.optimizer_step for o in history}) != len(history) or
            len({o.student_sha256 for o in history}) != len(history)):
        raise ValueError("DIAGNOSTIC_REPEATED_CHECKPOINT_IS_NOT_A_LEARNING_TRAJECTORY")
    if len({o.inventory for o in history}) > 1:
        raise ValueError("DIAGNOSTIC_INVENTORY_DRIFT")
    if len({o.run_id for o in history}) > 1:
        raise ValueError("DIAGNOSTIC_INCOMPARABLE_RUN_HISTORY")
    by_cap: dict[tuple[DiagnosticTarget, str], list[tuple[ExamObservation, CapabilityObservation]]] = {}
    for obs in history:
        for cap, target in _targets(obs):
            by_cap.setdefault((target, cap.capability), []).append((obs, cap))
    findings = []
    for (target, cap_name), rows in sorted(by_cap.items()):
        if len(rows) < 2:
            continue
        if len({o.contract for o, _ in rows}) != 1:
            raise ValueError("DIAGNOSTIC_INCOMPARABLE_RUBRIC_HISTORY")
        # Do not call one checkpoint repeatedly evaluated on new questions a
        # learned trajectory: it is observationally new, not temporal gain.
        for signal, pattern in (
            (LearningSignal.REPETITIVE_ANSWERS,
             lambda c: c.constant_prediction and c.mixed_gold),
            (LearningSignal.CHANCE_LEVEL_OR_LAGGING,
             lambda c: c.baseline_measured and c.correct <= c.majority_baseline),
        ):
            streak = []
            for pair in reversed(rows):
                if not pattern(pair[1]):
                    break
                streak.append(pair)
            sustained = len(streak) >= 2
            window = tuple(reversed(streak)) if sustained else (rows[-1],)
            status = (DiagnosticStatus.OBSERVED_LONGITUDINALLY if sustained else
                      DiagnosticStatus.OBSERVED_IN_COHORT if streak else
                      DiagnosticStatus.NOT_OBSERVED)
            if (not rows[-1][1].mixed_gold or
                    (signal is LearningSignal.CHANCE_LEVEL_OR_LAGGING and
                     not rows[-1][1].baseline_measured)):
                status = DiagnosticStatus.NOT_MEASURED
            findings.append(DiagnosticFinding(
                signal, status,
                cap_name, target, ObservationScope.DISTINCT_COHORT_SERIES,
                len(window), sum(cap.correct for _, cap in window),
                sum(cap.total for _, cap in window),
                sum(cap.majority_baseline for _, cap in window),
                tuple(obs.cohort_sha256 for obs, _ in window),
                "Consecutive observations on distinct cohorts and checkpoints; not a paired gain" if sustained else
                "No sustained warning in the latest consecutive cohort window",
            ))
    return tuple(findings)
