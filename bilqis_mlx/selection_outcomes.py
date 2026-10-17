"""Draft Pareto comparison of matched, post-replay curriculum observations.

The result is a research frontier, not a selected grade or teacher policy.
Caller-supplied hashes bind observations; authentic independent outcome
attestation and causal qualification remain separate unfinished boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .semantics.domains import contract_digest, require_sha256


@dataclass(frozen=True)
class CapabilityOutcome:
    capability: str
    before_correct: int
    after_correct: int
    total: int

    def __post_init__(self) -> None:
        if (not self.capability or any(type(value) is not int for value in
                (self.before_correct, self.after_correct, self.total)) or self.total < 1
                or not 0 <= self.before_correct <= self.total
                or not 0 <= self.after_correct <= self.total):
            raise ValueError("SELECTION_INVALID_CAPABILITY_OUTCOME")


@dataclass(frozen=True)
class SelectionTrial:
    candidate: str
    protocol_sha256: str
    source_scope_sha256: str
    parent_bundle_sha256: str
    final_bundle_sha256: str
    assessment_sha256: str
    outcomes: tuple[CapabilityOutcome, ...]
    optimizer_steps: int
    human_attention_seconds: int | None
    cumulative_replay_complete: bool

    def __post_init__(self) -> None:
        for value in (self.protocol_sha256, self.source_scope_sha256,
                      self.parent_bundle_sha256, self.final_bundle_sha256,
                      self.assessment_sha256):
            require_sha256(value)
        if (not self.candidate or not isinstance(self.outcomes, tuple) or not self.outcomes
                or any(not isinstance(item, CapabilityOutcome) for item in self.outcomes)
                or type(self.optimizer_steps) is not int or self.optimizer_steps < 0
                or type(self.cumulative_replay_complete) is not bool
                or len({item.capability for item in self.outcomes}) != len(self.outcomes)
                or (self.human_attention_seconds is not None and
                    (type(self.human_attention_seconds) is not int or self.human_attention_seconds < 0))):
            raise ValueError("SELECTION_INVALID_TRIAL")


class ComparisonStatus(str, Enum):
    NOT_MEASURED = "NOT_MEASURED"
    UNQUALIFIED_FRONTIER = "UNQUALIFIED_OBSERVATIONAL_FRONTIER"


@dataclass(frozen=True)
class SelectionComparison:
    trials_sha256: str
    status: ComparisonStatus
    frontier: tuple[str, ...]
    dominated: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    selected_grade: None = None


def compare_selection_trials(trials: tuple[SelectionTrial, ...]) -> SelectionComparison:
    """Retain negative results and tradeoffs without inventing score weights."""
    if not trials or len({trial.candidate for trial in trials}) != len(trials):
        raise ValueError("SELECTION_DISTINCT_CANDIDATES_REQUIRED")
    digest = contract_digest(trials)
    first, gaps = trials[0], []

    def cohort(trial):
        return tuple(sorted((item.capability, item.before_correct, item.total)
                            for item in trial.outcomes))

    for trial in trials:
        if ((trial.protocol_sha256, trial.source_scope_sha256, trial.parent_bundle_sha256,
             trial.assessment_sha256, cohort(trial)) !=
                (first.protocol_sha256, first.source_scope_sha256, first.parent_bundle_sha256,
                 first.assessment_sha256, cohort(first))):
            gaps.append("INCOMPARABLE_TRIAL:" + trial.candidate)
        if not trial.cumulative_replay_complete:
            gaps.append("POST_REPLAY_OUTCOME_MISSING:" + trial.candidate)
        if trial.human_attention_seconds is None:
            gaps.append("ATTENTION_NOT_MEASURED:" + trial.candidate)
    if len(trials) < 2:
        gaps.append("ALTERNATIVE_OUTCOME_MISSING")
    if gaps:
        return SelectionComparison(digest, ComparisonStatus.NOT_MEASURED, (), (), tuple(gaps))

    def objectives(trial):
        # Per-capability objectives preserve losses hidden by an aggregate gain.
        scores = tuple(item.after_correct for item in
                       sorted(trial.outcomes, key=lambda item: item.capability))
        return (*scores, -trial.optimizer_steps, -trial.human_attention_seconds)

    vectors = {trial.candidate: objectives(trial) for trial in trials}
    dominated = set()
    for candidate, values in vectors.items():
        for other, comparison in vectors.items():
            if (other != candidate and all(a >= b for a, b in zip(comparison, values))
                    and any(a > b for a, b in zip(comparison, values))):
                dominated.add(candidate)
    return SelectionComparison(digest, ComparisonStatus.UNQUALIFIED_FRONTIER,
                               tuple(sorted(set(vectors) - dominated)), tuple(sorted(dominated)),
                               ("INDEPENDENT_OUTCOME_ATTESTATION_REQUIRED",
                                "CAUSAL_TRANSFER_QUALIFICATION_REQUIRED"))
