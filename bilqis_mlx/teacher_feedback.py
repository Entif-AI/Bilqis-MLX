"""Typed receipts connecting diagnostics, teacher actions, and later exams.

This module observes the inherited teacher. It does not replace its strategy
selector, mutate neural state, invent semantic identities, or assign golds.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Final

from .diagnostics.signals import DiagnosticStatus, LearningSignal


VERSION: Final = "bilqis.teacher-feedback/v1"


class TeachingOpportunity(str, Enum):
    EXAM_MISTAKE_REPLAY = "EXAM_MISTAKE_REPLAY"
    PREREQUISITE_CONNECTION = "PREREQUISITE_CONNECTION"
    SIMPLER_INTRODUCTION = "SIMPLER_INTRODUCTION"
    CHAMPION_PRIORITY = "CHAMPION_PRIORITY"


class OutcomeAttribution(str, Enum):
    MEASURED_FIXED_EXAM_UNIQUE_ACTION = "MEASURED_FIXED_EXAM_UNIQUE_ACTION"
    NOT_MEASURED_NO_FIXED_BASELINE = "NOT_MEASURED_NO_FIXED_BASELINE"
    NOT_MEASURED_CHANGED_EXAM = "NOT_MEASURED_CHANGED_EXAM"
    NOT_MEASURED_MULTIPLE_ACTIONS = "NOT_MEASURED_MULTIPLE_ACTIONS"
    NOT_MEASURED_SCORE_UNAVAILABLE = "NOT_MEASURED_SCORE_UNAVAILABLE"


_ACTIVE: Final = frozenset((
    DiagnosticStatus.OBSERVED_IN_COHORT,
    DiagnosticStatus.OBSERVED_LONGITUDINALLY,
    DiagnosticStatus.OBSERVED_IN_INSTRUCTION,
))


@dataclass(frozen=True)
class TeacherDecisionInput:
    capability: str
    policy_key: str
    warnings: tuple[LearningSignal, ...]
    unresolved_miss_count: int
    champion_candidate_count: int
    prerequisite_capabilities: tuple[str, ...]
    methodology: dict
    delivered_examples: int
    replayed_misses: int
    resolved_exam_misses: int
    champion_prioritized: int
    seed: int


@dataclass(frozen=True)
class FairMissRequest:
    exposures: dict[str, int]
    selected_this_visit: frozenset[str]
    remaining_steps: int
    batch_size: int
    gold_capacity: dict[str, int]


@dataclass(frozen=True)
class _OutcomeMeasurement:
    attribution: OutcomeAttribution
    before_correct: int | None = None
    after_correct: int | None = None
    total: int | None = None
    delta_correct: int | None = None


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _diagnostic_findings(last_exam: dict | None,
                         methodology: dict | None) -> tuple[dict, ...]:
    findings = []
    if isinstance(last_exam, dict):
        diagnostics = last_exam.get("learning_diagnostics")
        if isinstance(diagnostics, dict) and isinstance(diagnostics.get("findings"), list):
            findings.extend(diagnostics["findings"])
    if isinstance(methodology, dict) and isinstance(methodology.get("findings"), list):
        findings.extend(methodology["findings"])
    return tuple(finding for finding in findings if isinstance(finding, dict))


def _finding_applies(finding: dict, capability: str) -> bool:
    target = finding.get("target")
    finding_capability = finding.get("capability")
    if target == "GRADE":
        return finding_capability == capability.split(".", 1)[0]
    return finding_capability == capability


def _active_signal(finding: dict, capability: str) -> LearningSignal | None:
    if not _finding_applies(finding, capability):
        return None
    try:
        signal = LearningSignal(finding.get("signal"))
        status = DiagnosticStatus(finding.get("status"))
    except (TypeError, ValueError):
        return None
    return signal if status in _ACTIVE else None


def active_warning_signals(last_exam: dict | None, methodology: dict | None,
                           capability: str) -> tuple[LearningSignal, ...]:
    """Return active evidence for one capability in stable signal order."""
    observed = {
        signal for finding in _diagnostic_findings(last_exam, methodology)
        if (signal := _active_signal(finding, capability)) is not None
    }
    return tuple(signal for signal in LearningSignal if signal in observed)


def _row_identity(row: dict, seen: set[str], error: str) -> str:
    identity = row.get("id") if isinstance(row, dict) else None
    if not isinstance(identity, str) or not identity or identity in seen:
        raise ValueError(error)
    seen.add(identity)
    return identity


def _miss_sort_key(row: dict) -> tuple[str, str]:
    return str(row.get("capability", "")), row["id"]


def reconcile_unresolved_misses(previous: list[dict] | tuple[dict, ...],
                                rows: list[dict] | tuple[dict, ...],
                                predictions: dict[str, str]) -> list[dict]:
    """Retain unresolved errors across changing cohorts until retested correct."""
    unresolved = {}
    historical_ids = set()
    for row in previous:
        identity = _row_identity(row, historical_ids,
                                 "TEACHER_MISS_HISTORY_IDENTITY_CONFLICT")
        unresolved[identity] = row
    current = set()
    for row in rows:
        identity = _row_identity(row, current, "TEACHER_MISS_CURRENT_COHORT_INVALID")
        gold = row.get("gold") if isinstance(row, dict) else None
        if not isinstance(gold, str):
            raise ValueError("TEACHER_MISS_CURRENT_COHORT_INVALID")
        if identity not in predictions:
            raise ValueError("TEACHER_MISS_PREDICTION_MISSING")
        if predictions[identity] == gold:
            unresolved.pop(identity, None)
        else:
            unresolved[identity] = row
    return sorted(unresolved.values(), key=_miss_sort_key)


def _valid_gold_capacity(gold_capacity: dict[str, int], batch_size: int) -> bool:
    if not isinstance(gold_capacity, dict) or not gold_capacity:
        return False
    valid_entries = all(
        isinstance(label, str) and label and
        type(capacity) is int and capacity >= 0
        for label, capacity in gold_capacity.items())
    return valid_entries and sum(gold_capacity.values()) <= batch_size


def _validate_fair_miss_request(request: FairMissRequest) -> None:
    if type(request.remaining_steps) is not int or request.remaining_steps < 1:
        raise ValueError("TEACHER_MISS_FAIRNESS_INPUT_INVALID")
    if type(request.batch_size) is not int or request.batch_size < 2 or request.batch_size % 2:
        raise ValueError("TEACHER_MISS_FAIRNESS_INPUT_INVALID")
    if any(type(value) is not int or value < 0 for value in request.exposures.values()):
        raise ValueError("TEACHER_MISS_FAIRNESS_INPUT_INVALID")
    if not _valid_gold_capacity(request.gold_capacity, request.batch_size):
        raise ValueError("TEACHER_MISS_FAIRNESS_INPUT_INVALID")


def _available_misses(misses: list[dict] | tuple[dict, ...],
                      selected_this_visit: set[str]) -> list[dict]:
    available = []
    seen = set()
    for row in misses:
        identity = _row_identity(row, seen, "TEACHER_MISS_FAIRNESS_IDENTITY_CONFLICT")
        if identity not in selected_this_visit:
            available.append(row)
    return available


def _fairness_key(row: dict, request: FairMissRequest) -> tuple[int, str, str]:
    return (request.exposures.get(row["id"], 0), *_miss_sort_key(row))


def _misses_by_gold(rows: list[dict]) -> dict[str, list[dict]]:
    grouped = {}
    for row in rows:
        gold = row.get("gold")
        if not isinstance(gold, str) or not gold:
            raise ValueError("TEACHER_MISS_FAIRNESS_GOLD_INVALID")
        grouped.setdefault(gold, []).append(row)
    return grouped


def _select_gold_window(gold: str, rows: list[dict],
                        request: FairMissRequest) -> list[dict]:
    capacity = request.gold_capacity.get(gold, 0)
    if not capacity:
        return []
    ordered = sorted(rows, key=lambda row: _fairness_key(row, request))
    target = (len(ordered) + request.remaining_steps - 1) // request.remaining_steps
    return ordered[:min(capacity, target)]


def select_fair_miss_window(misses: list[dict] | tuple[dict, ...],
                            request: FairMissRequest) -> list[dict]:
    """Cover unresolved errors fairly with capacity derived from backlog size.

    There is no universal rehearsal percentage: the requested count follows
    each answer-class backlog and remaining visit budget, bounded by the
    replaceable answer classes in the already selected batch.
    """
    _validate_fair_miss_request(request)
    available = _available_misses(misses, set(request.selected_this_visit))
    if not available:
        return []
    selected = [
        row
        for gold, rows in sorted(_misses_by_gold(available).items())
        for row in _select_gold_window(gold, rows, request)
    ]
    return sorted(selected, key=lambda row: _fairness_key(row, request))


def _validate_decision_input(request: TeacherDecisionInput) -> None:
    counts = (request.unresolved_miss_count, request.champion_candidate_count,
              request.delivered_examples, request.replayed_misses,
              request.resolved_exam_misses, request.champion_prioritized)
    valid_identity = bool(request.capability and request.policy_key)
    valid_seed = type(request.seed) is int
    valid_counts = all(type(value) is int and value >= 0 for value in counts)
    if not (valid_identity and valid_seed and valid_counts):
        raise ValueError("TEACHER_DECISION_INPUT_INVALID")


def _opportunities(request: TeacherDecisionInput) -> list[TeachingOpportunity]:
    opportunities = []
    if request.unresolved_miss_count:
        opportunities.append(TeachingOpportunity.EXAM_MISTAKE_REPLAY)
    if request.prerequisite_capabilities:
        opportunities.append(TeachingOpportunity.PREREQUISITE_CONNECTION)
    if LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY in request.warnings:
        opportunities.append(TeachingOpportunity.SIMPLER_INTRODUCTION)
    if request.champion_candidate_count:
        opportunities.append(TeachingOpportunity.CHAMPION_PRIORITY)
    return opportunities


def _selected_actions(request: TeacherDecisionInput) -> dict:
    delivered_constituents = (
        request.methodology.get("constituent_capabilities_delivered", ())
        if isinstance(request.methodology, dict) else ())
    prerequisite_connections = sorted(
        set(request.prerequisite_capabilities) & set(delivered_constituents))
    return {
        "delivered_examples": request.delivered_examples,
        "exam_mistake_replay": request.replayed_misses,
        "exam_mistakes_resolved": request.resolved_exam_misses,
        "champion_priority": request.champion_prioritized,
        "prerequisite_connections": prerequisite_connections,
        "simplest_delivered_first_batch": (
            request.methodology.get("simplest_delivered_first_batch")
            if isinstance(request.methodology, dict) else None),
    }


def _decision_payload(request: TeacherDecisionInput) -> dict:
    return {
        "schema": VERSION,
        "capability": request.capability,
        "policy_key": request.policy_key,
        "policy_selection": {
            "origin": "INHERITED_LEGACY_UCB",
            "diagnostic_context_consumed": False,
        },
        "warning_signals": list(request.warnings),
        "opportunities": _opportunities(request),
        "prerequisite_capabilities": list(request.prerequisite_capabilities),
        "available": {
            "unresolved_exam_misses": request.unresolved_miss_count,
            "champion_priority_candidates": request.champion_candidate_count,
        },
        "selected": _selected_actions(request),
        "seed": request.seed,
    }


def summarize_teacher_decision(request: TeacherDecisionInput) -> dict:
    """Record the actual intervention under the already selected legacy policy."""
    _validate_decision_input(request)
    payload = _decision_payload(request)
    payload["decision_id"] = _digest(payload)
    return payload


def _group_decisions(pending_visits: list[dict] | tuple[dict, ...]) -> dict[str, list[dict]]:
    grouped = {}
    for event in pending_visits:
        decision = event.get("teacher_decision") if isinstance(event, dict) else None
        capability = decision.get("capability") if isinstance(decision, dict) else None
        if isinstance(capability, str) and capability:
            grouped.setdefault(capability, []).append(decision)
    return grouped


def _score(scores: dict, capability: str) -> dict | None:
    value = scores.get(capability) if isinstance(scores, dict) else None
    return value if isinstance(value, dict) else None


def _valid_score_pair(before: dict | None, after: dict | None) -> bool:
    if before is None or after is None:
        return False
    fields = (before.get("correct"), before.get("total"),
              after.get("correct"), after.get("total"))
    return all(type(value) is int for value in fields) and before["total"] == after["total"]


def _measure_outcome(previous_exam: dict | None, current_exam: dict,
                     decisions: list[dict], capability: str) -> _OutcomeMeasurement:
    if not isinstance(previous_exam, dict):
        return _OutcomeMeasurement(OutcomeAttribution.NOT_MEASURED_NO_FIXED_BASELINE)
    if previous_exam.get("cohort_sha256") != current_exam.get("cohort_sha256"):
        return _OutcomeMeasurement(OutcomeAttribution.NOT_MEASURED_CHANGED_EXAM)
    if len(decisions) != 1:
        return _OutcomeMeasurement(OutcomeAttribution.NOT_MEASURED_MULTIPLE_ACTIONS)
    before = _score(previous_exam.get("scores", {}), capability)
    after = _score(current_exam.get("scores", {}), capability)
    if not _valid_score_pair(before, after):
        return _OutcomeMeasurement(OutcomeAttribution.NOT_MEASURED_SCORE_UNAVAILABLE)
    return _OutcomeMeasurement(
        OutcomeAttribution.MEASURED_FIXED_EXAM_UNIQUE_ACTION,
        before["correct"], after["correct"], after["total"],
        after["correct"] - before["correct"],
    )


def _outcome_payload(previous_exam: dict | None, current_exam: dict,
                     capability: str, decisions: list[dict]) -> dict:
    measurement = _measure_outcome(previous_exam, current_exam, decisions, capability)
    return {
        "schema": VERSION,
        "capability": capability,
        "policy_keys": sorted({decision["policy_key"] for decision in decisions
                               if isinstance(decision.get("policy_key"), str)}),
        "decision_ids": [decision["decision_id"] for decision in decisions
                         if isinstance(decision.get("decision_id"), str)],
        "attribution": measurement.attribution,
        "cohort_sha256": current_exam.get("cohort_sha256"),
        "before_optimizer_step": (previous_exam or {}).get("optimizer_step"),
        "after_optimizer_step": current_exam.get("optimizer_step"),
        "before_correct": measurement.before_correct,
        "after_correct": measurement.after_correct,
        "total": measurement.total,
        "delta_correct": measurement.delta_correct,
    }


def summarize_teacher_outcomes(previous_exam: dict | None, current_exam: dict,
                               pending_visits: list[dict] | tuple[dict, ...]) -> list[dict]:
    """Attribute the next fixed-exam change only when one action window is identifiable."""
    groups = _group_decisions(pending_visits)
    return [_outcome_payload(previous_exam, current_exam, capability, decisions)
            for capability, decisions in sorted(groups.items())]
