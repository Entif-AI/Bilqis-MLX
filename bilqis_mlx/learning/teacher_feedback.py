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

from bilqis_mlx.diagnostics.signals import DiagnosticStatus, LearningSignal


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


class WeaknessTargetError(str, Enum):
    TEACHER_WEAKNESS_TARGET_INPUT_INVALID = "TEACHER_WEAKNESS_TARGET_INPUT_INVALID"
    LEARNING_EXPERIMENT_SUPPORT_CAPACITY_INVALID = "LEARNING_EXPERIMENT_SUPPORT_CAPACITY_INVALID"
    LEARNING_EXPERIMENT_WEAKNESS_TARGET_CAPACITY_DRIFT = "LEARNING_EXPERIMENT_WEAKNESS_TARGET_CAPACITY_DRIFT"
    LEARNING_EXPERIMENT_WEAKNESS_TARGET_OUTSIDE_CURRENT = "LEARNING_EXPERIMENT_WEAKNESS_TARGET_OUTSIDE_CURRENT"


class LearningExperimentError(str, Enum):
    CANDIDATE_STAGNATION_INVALID = "LEARNING_EXPERIMENT_CANDIDATE_STAGNATION_INVALID"
    CANDIDATE_STEPS_INVALID = "LEARNING_EXPERIMENT_CANDIDATE_STEPS_INVALID"
    CONTEXT_ID_DRIFT = "LEARNING_EXPERIMENT_CONTEXT_ID_DRIFT"
    DIAGNOSTIC_CONTEXT_COLLISION = "LEARNING_EXPERIMENT_DIAGNOSTIC_CONTEXT_COLLISION"
    DIAGNOSTIC_REASON_DRIFT = "LEARNING_EXPERIMENT_DIAGNOSTIC_REASON_DRIFT"
    EFFECTIVE_POLICY_LR_DRIFT = "LEARNING_EXPERIMENT_EFFECTIVE_POLICY_LR_DRIFT"
    POLICY_INVALID = "LEARNING_EXPERIMENT_POLICY_INVALID"
    POLICY_LR_INVALID = "LEARNING_EXPERIMENT_POLICY_LR_INVALID"
    PRIORITY_TARGET_INVALID = "LEARNING_EXPERIMENT_PRIORITY_TARGET_INVALID"
    REJECTION_REASON_INVALID = "LEARNING_EXPERIMENT_REJECTION_REASON_INVALID"
    STUDENT_CHECKPOINT_INVALID = "LEARNING_EXPERIMENT_STUDENT_CHECKPOINT_INVALID"
    STUDENT_POLICY_EPOCH_INVALID = "LEARNING_EXPERIMENT_STUDENT_POLICY_EPOCH_INVALID"
    STUDENT_POLICY_FAILURE_INVALID = "LEARNING_EXPERIMENT_STUDENT_POLICY_FAILURE_INVALID"
    STRATEGY_ID_DRIFT = "LEARNING_EXPERIMENT_STRATEGY_ID_DRIFT"


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
    diagnostic_context_consumed: bool = False
    diagnostic_context_key: str | None = None
    policy_selection_origin: str = "INHERITED_LEGACY_UCB"
    actual_authority_changed: bool = False
    legacy_policy_key: str | None = None
    vnext_canary_status: str | None = None
    vnext_canary_policy_version: str | None = None
    vnext_evidence_level: str | None = None


@dataclass(frozen=True)
class WeaknessTargetRequest:
    exposures: dict[str, int]
    capacity: int


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


def _numeric_witness_signature(row: dict) -> tuple:
    witness = row.get("witness")
    if not isinstance(witness, dict):
        return ()
    parts = []
    for name in ("ordinal_members", "before", "after",
                 "left_members", "right_members"):
        value = witness.get(name)
        if isinstance(value, list):
            parts.append((name + "_count", len(value)))
    groups = witness.get("groups")
    if isinstance(groups, list) and all(isinstance(group, list) for group in groups):
        parts.append(("group_sizes", tuple(sorted(len(group) for group in groups))))
    relation = witness.get("relation")
    if isinstance(relation, str) and relation:
        parts.append(("relation", relation))
    return tuple(parts)


def _source_structural_miss_identity(row: dict) -> dict | None:
    """Project a source-owned teaching class without exact specimen identity.

    Exact failed rows remain durable in their immutable exam/cohort evidence.
    The active miss queue instead needs a class that can be re-tested by a
    fresh, source-equivalent construction; otherwise every generated world is
    an immortal new "semantic" merely because its entity order or row ID
    changed.
    """
    capability = row.get("capability")
    gold = row.get("gold")
    answer_kind = row.get("answer_kind", "binary")
    record = row.get("record")
    if (not isinstance(capability, str) or not capability or
            not isinstance(gold, str) or
            not isinstance(answer_kind, str) or
            not isinstance(record, dict)):
        return None
    if capability.startswith("B."):
        try:
            raw = row.get("operand_truths")
            if isinstance(raw, list) and len(raw) == 2:
                from bilqis_mlx.learning.fragile_replay import structural_signature
                return {
                    "family": "boolean-connective",
                    "signature": structural_signature(row),
                    "answer_kind": answer_kind,
                    "gold": gold,
                }
            from bilqis_mlx.source_adapters.structure import (
                inspect_boolean_identification, inspect_source_query,
            )
            if capability == "B.IDBOOLOPS":
                shape = inspect_boolean_identification(record, row.get("root"))
                extras = {
                    "operator_options": tuple(row.get("operator_options", ())),
                    "observation_count": row.get("observation_count"),
                }
            else:
                query = record.get("query")
                shape = inspect_source_query(query)
                extras = {
                    "operators": tuple(row.get("operators", ())),
                    "composition_width": row.get("composition_width"),
                    "universe_size": row.get("universe_size"),
                }
            return {
                "family": "boolean-structured",
                "capability": capability,
                "answer_kind": answer_kind,
                "gold": gold,
                "root": shape.root,
                "rooted_operators": shape.rooted_operators,
                "semantic_operations": shape.semantic_operations,
                "operator_depth": shape.operator_depth,
                **extras,
            }
        except (KeyError, TypeError, ValueError):
            return None
    if capability.startswith("C."):
        try:
            from bilqis_mlx.source_adapters.numeric import inspect_record
            shape = inspect_record(record)
        except (KeyError, TypeError, ValueError):
            return None
        native = row.get("native_output")
        native_identity = (
            native.get("identity") if isinstance(native, dict) else None)
        return {
            "family": "finite-numeric",
            "capability": capability,
            "lesson_id": row.get("lesson_id"),
            "answer_kind": answer_kind,
            "gold": gold,
            "native_output_identity": native_identity,
            "root": shape.root,
            "rooted_operators": shape.rooted_operators,
            "semantic_operations": shape.semantic_operations,
            "operator_depth": shape.operator_depth,
            "witness": _numeric_witness_signature(row),
        }
    return None


def _miss_semantic_identity(row: dict) -> str:
    source_id = row.get("source_id")
    record = row.get("record")
    tokens = row.get("tokens")
    if (not isinstance(source_id, str) or not source_id or
            not isinstance(record, dict) or
            not isinstance(tokens, list)):
        return "id:" + row["id"]
    structural = _source_structural_miss_identity(row)
    if structural is not None:
        return "structural:" + _digest(structural)
    return "semantic:" + _digest({
        key: value for key, value in row.items()
        if key not in {"id", "integer_max"}
    })


def reconcile_unresolved_misses(previous: list[dict] | tuple[dict, ...],
                                rows: list[dict] | tuple[dict, ...],
                                predictions: dict[str, str]) -> list[dict]:
    """Retain unresolved errors across changing cohorts until retested correct."""
    unresolved = {}
    historical_ids = set()
    for row in previous:
        _row_identity(row, historical_ids,
                      "TEACHER_MISS_HISTORY_IDENTITY_CONFLICT")
        unresolved.setdefault(_miss_semantic_identity(row), row)
    current = set()
    current_semantics = {}
    for row in rows:
        identity = _row_identity(row, current, "TEACHER_MISS_CURRENT_COHORT_INVALID")
        gold = row.get("gold") if isinstance(row, dict) else None
        if not isinstance(gold, str):
            raise ValueError("TEACHER_MISS_CURRENT_COHORT_INVALID")
        if identity not in predictions:
            raise ValueError("TEACHER_MISS_PREDICTION_MISSING")
        current_semantics.setdefault(_miss_semantic_identity(row), []).append(row)
    for semantic_identity, equivalent_rows in current_semantics.items():
        wrong = [
            row for row in equivalent_rows
            if predictions[row["id"]] != row["gold"]
        ]
        if wrong:
            unresolved.setdefault(semantic_identity, wrong[0])
        else:
            unresolved.pop(semantic_identity, None)
    return sorted(unresolved.values(), key=_miss_sort_key)


def _validate_weakness_target_request(request: WeaknessTargetRequest) -> None:
    invalid_capacity = type(request.capacity) is not int or request.capacity < 0
    invalid_exposures = any(
        type(value) is not int or value < 0 for value in request.exposures.values())
    if invalid_capacity or invalid_exposures:
        raise ValueError(WeaknessTargetError.TEACHER_WEAKNESS_TARGET_INPUT_INVALID.value)


def _validated_misses(misses: list[dict] | tuple[dict, ...]) -> list[dict]:
    available = []
    seen = set()
    for row in misses:
        _row_identity(row, seen, "TEACHER_WEAKNESS_TARGET_IDENTITY_CONFLICT")
        available.append(row)
    return available


def _weakness_target_key(row: dict,
                         request: WeaknessTargetRequest) -> tuple[int, str, str]:
    return (request.exposures.get(row["id"], 0), *_miss_sort_key(row))


def select_weakness_targets(misses: list[dict] | tuple[dict, ...],
                            request: WeaknessTargetRequest) -> list[dict]:
    """Use available current-capability slots on the least-exposed weak semantics."""
    _validate_weakness_target_request(request)
    if not request.capacity:
        return []
    available = _validated_misses(misses)
    ordered = sorted(
        available, key=lambda row: _weakness_target_key(row, request))
    return ordered[:min(request.capacity, len(ordered))]


def _validate_decision_input(request: TeacherDecisionInput) -> None:
    counts = (request.unresolved_miss_count, request.champion_candidate_count,
              request.delivered_examples, request.replayed_misses,
              request.resolved_exam_misses, request.champion_prioritized)
    valid_identity = bool(request.capability and request.policy_key)
    valid_seed = type(request.seed) is int
    valid_counts = all(type(value) is int and value >= 0 for value in counts)
    valid_diagnostics = (
        type(request.diagnostic_context_consumed) is bool and
        (request.diagnostic_context_key is None or
         isinstance(request.diagnostic_context_key, str) and
         bool(request.diagnostic_context_key)))
    valid_selection = (
        isinstance(request.policy_selection_origin, str) and
        bool(request.policy_selection_origin) and
        type(request.actual_authority_changed) is bool and
        all(value is None or isinstance(value, str) and bool(value) for value in (
            request.legacy_policy_key, request.vnext_canary_status,
            request.vnext_canary_policy_version, request.vnext_evidence_level)))
    if not (valid_identity and valid_seed and valid_counts and valid_diagnostics and
            valid_selection):
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
    policy_selection = {
        "origin": request.policy_selection_origin,
        "actual_authority_changed": request.actual_authority_changed,
        "diagnostic_context_consumed": request.diagnostic_context_consumed,
    }
    if request.diagnostic_context_key is not None:
        policy_selection["diagnostic_context_key"] = request.diagnostic_context_key
    for key, value in (
        ("legacy_policy_key", request.legacy_policy_key),
        ("vnext_canary_status", request.vnext_canary_status),
        ("vnext_canary_policy_version", request.vnext_canary_policy_version),
        ("vnext_evidence_level", request.vnext_evidence_level),
    ):
        if value is not None:
            policy_selection[key] = value
    return {
        "schema": VERSION,
        "capability": request.capability,
        "policy_key": request.policy_key,
        "policy_selection": policy_selection,
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
    """Record the actual intervention and its auditable policy-selection origin."""
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
                     decisions: list[dict], capability: str,
                     intervening_visits: int) -> _OutcomeMeasurement:
    if not isinstance(previous_exam, dict):
        return _OutcomeMeasurement(OutcomeAttribution.NOT_MEASURED_NO_FIXED_BASELINE)
    if previous_exam.get("cohort_sha256") != current_exam.get("cohort_sha256"):
        return _OutcomeMeasurement(OutcomeAttribution.NOT_MEASURED_CHANGED_EXAM)
    # A single visit on this skill is not a unique intervention when other
    # capability visits have also changed the same whole student's weights.
    if len(decisions) != 1 or intervening_visits != 1:
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
                     capability: str, decisions: list[dict],
                     intervening_visits: int) -> dict:
    measurement = _measure_outcome(previous_exam, current_exam, decisions,
                                   capability, intervening_visits)
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
    return [_outcome_payload(previous_exam, current_exam, capability, decisions,
                             len(pending_visits))
            for capability, decisions in sorted(groups.items())]
