"""Pure, evidence-only projections for replayable Factory teacher observations.

This module neither selects teaching nor changes a learner, teacher, release, or
retention outcome.  It translates already-recorded evidence into a bounded,
portable-safe observation shape.
"""
from __future__ import annotations

from collections import Counter
from enum import StrEnum
import hashlib
import json
import math
from typing import Mapping
from bilqis_mlx.errors import ErrorBus, SCHOOL


class MeasurementStatus(StrEnum):
    MEASURED = "MEASURED"
    NOT_MEASURED = "NOT_MEASURED"


MEASURED = MeasurementStatus.MEASURED
NOT_MEASURED = MeasurementStatus.NOT_MEASURED
OBSERVATION_SCHEMA = "bilqis.factory-teacher-observation/v1"
PORTABLE_V1_SCHEMA = "bilqis.teacher-outcome-observation/v1"


def _measured(value):
    return {"status": MEASURED, "value": value}


def _unmeasured(reason: str):
    return {"status": NOT_MEASURED, "reason": reason}


def _score_pair(value):
    if (isinstance(value, (tuple, list)) and len(value) == 2):
        correct, total = value
        if (type(correct) is int and type(total) is int and
                0 <= correct <= total and total > 0):
            return correct, total
        return None
    if not isinstance(value, Mapping):
        return None
    correct, total = value.get("correct"), value.get("total")
    if (type(correct) is not int or type(total) is not int or
            correct < 0 or total < 1 or correct > total):
        return None
    return correct, total


def _score_band(correct, total):
    if correct is None or total is None or total < 1:
        return "UNMEASURED"
    percent = 100 * correct / total
    if percent == 100:
        return "P100"
    if percent >= 95:
        return "P095_099"
    if percent >= 85:
        return "P085_094"
    if percent >= 70:
        return "P070_084"
    if percent >= 50:
        return "P050_069"
    return "P000_049"


def _count_band(value, *, prefix):
    if type(value) is not int or value < 0:
        return "UNMEASURED"
    if value == 0:
        return prefix + "00"
    if value <= 3:
        return prefix + "01_03"
    if value <= 7:
        return prefix + "04_07"
    if value <= 15:
        return prefix + "08_15"
    if value <= 31:
        return prefix + "16_31"
    return prefix + "32_PLUS"


def _program_grade(program, capability: str) -> str:
    for grade in program.grades:
        if capability in {item.id for item in grade.capabilities}:
            return grade.id
    ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID, capability=capability)


def _stagnation(teacher, capability, phase):
    if not isinstance(teacher, Mapping):
        return 0, 0
    causal = teacher.get("causal_experiment")
    if not isinstance(causal, Mapping):
        return 0, 0
    entries = causal.get("capability_stagnation")
    if not isinstance(entries, Mapping):
        return 0, 0
    # The authoritative runtime uses capability|scope as its key.  This
    # projection deliberately aggregates matching contexts rather than making
    # scope identity a region key.
    matches = [item for key, item in entries.items()
               if isinstance(key, str) and key.startswith(capability + "|") and
               isinstance(item, Mapping)]
    if not matches:
        return 0, 0
    return (max(int(item.get("rejection_streak", 0)) for item in matches),
            max(int(item.get("attempts_since_retained", 0)) for item in matches))


def student_region(receipt: Mapping, program, capability: str, phase: str,
                   teacher: Mapping | None = None, *,
                   curriculum_scope: str = NOT_MEASURED,
                   geometry_epoch: str | None = None,
                   numeric_maximum: int | None = None,
                   grade_correct: int | None = None, grade_total: int | None = None,
                   grade_capability_scores: Mapping | None = None) -> dict:
    """Build a coarse region from declared roster ownership and past evidence.

    Checkpoint, cohort, source specimen, policy epoch, and topology identities
    are intentionally excluded: they belong to comparison provenance, not the
    predictive region key.
    """
    if (not isinstance(receipt, Mapping) or not isinstance(capability, str) or
            not capability or not isinstance(phase, str) or not phase or
            not isinstance(curriculum_scope, str)):
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID)
    lesson_grade = _program_grade(program, capability)
    scores = (receipt.get("last_exam") or {}).get("scores") or {}
    if not isinstance(scores, Mapping):
        scores = {}
    capability_pair = _score_pair(scores.get(capability))
    raw_grade_scores = grade_capability_scores if isinstance(grade_capability_scores, Mapping) else scores
    grade_scores = [(name, _score_pair(value)) for name, value in raw_grade_scores.items()
                    if _program_grade(program, name) == lesson_grade] if grade_capability_scores else [
                        (item.id, _score_pair(scores.get(item.id)))
                        for grade in program.grades if grade.id == lesson_grade for item in grade.capabilities]
    present = [(name, pair) for name, pair in grade_scores if pair is not None]
    grade_correct = grade_correct if grade_correct is not None else (sum(pair[0] for _, pair in present) if present else None)
    grade_total = grade_total if grade_total is not None else (sum(pair[1] for _, pair in present) if present else None)
    shape = "|".join(f"{name}={_score_band(*pair) if pair else 'UNMEASURED'}"
                     for name, pair in sorted(grade_scores)) or "UNMEASURED"
    debt = tuple((receipt.get("school") or {}).get("carried_mastery_debt") or ())
    grade_by_capability = {
        item.id: grade.id for grade in program.grades for item in grade.capabilities
    }
    debt_grades = Counter(grade_by_capability[item] for item in debt
                          if item in grade_by_capability)
    rejection_streak, attempts_since_retained = _stagnation(teacher, capability, phase)
    predictive = {
        "schema": "bilqis.teacher-student-region/v1",
        "capability": capability,
        "phase": phase.removeprefix("ASSESS_"),
        "lesson_grade": lesson_grade,
        "curriculum_scope": curriculum_scope,
        "geometry_epoch": geometry_epoch,
        "numeric_maximum": numeric_maximum,
        "capability_score_band": _score_band(*(capability_pair or (None, None))),
        "grade_score_band": _score_band(grade_correct, grade_total),
        "grade_score_shape": shape,
        "rejection_pressure_band": _count_band(rejection_streak, prefix="R"),
        "attempts_since_retained_band": _count_band(attempts_since_retained, prefix="A"),
        "mastery_debt_band": _count_band(len(debt), prefix="D"),
        "mastery_debt_shape": "|".join(
            f"{grade}:{debt_grades[grade]}" for grade in sorted(debt_grades)) or "NONE",
    }
    predictive["key"] = hashlib.sha256(json.dumps(
        predictive, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
    return predictive


def _paired_measurements(paired, protected):
    protected = set(protected or ())
    if not isinstance(paired, Mapping):
        return _unmeasured("PAIRED_PROBE_NOT_RECORDED"), _unmeasured("PAIRED_PROBE_NOT_RECORDED")
    entries = {}
    for capability, evidence in paired.items():
        if not isinstance(capability, str) or not isinstance(evidence, Mapping):
            return _unmeasured("PAIRED_PROBE_INVALID"), _unmeasured("PAIRED_PROBE_INVALID")
        before, after, total = evidence.get("before"), evidence.get("after"), evidence.get("total")
        if any(type(value) is not int for value in (before, after, total)) or not 0 <= before <= total or not 0 <= after <= total:
            return _unmeasured("PAIRED_PROBE_INVALID"), _unmeasured("PAIRED_PROBE_INVALID")
        entries[capability] = {"before": before, "after": after, "total": total}
    protected_entries = {cap: entries[cap] for cap in sorted(protected) if cap in entries}
    if protected and set(protected) - set(protected_entries):
        return _measured(entries), _unmeasured("PROTECTED_PROBE_INCOMPLETE")
    return _measured(entries), _measured({
        "capabilities": protected_entries,
        "net_correct_delta": sum(value["after"] - value["before"]
                                 for value in protected_entries.values()),
        "denominator": sum(value["total"] for value in protected_entries.values()),
    })


def candidate_outcome(decision: Mapping | None, *, paired=None, protected=None,
                      stage: str, attempted_steps: int, retained_steps: int,
                      wall_seconds: float) -> dict:
    """Project an already-decided candidate screen without inventing evidence."""
    if (not isinstance(stage, str) or type(attempted_steps) is not int or
            type(retained_steps) is not int or attempted_steps < 0 or
            not 0 <= retained_steps <= attempted_steps or
            not isinstance(wall_seconds, (int, float)) or wall_seconds < 0):
        ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID)
    base = {
        "schema": OBSERVATION_SCHEMA,
        "stage": stage,
        "attempted_steps": attempted_steps,
        "retained_steps": retained_steps,
        "wall_seconds": wall_seconds,
        "fixed_grade": _unmeasured("NO_CANDIDATE_SCREEN"),
        "fixed_frontier": _unmeasured("NO_CANDIDATE_SCREEN"),
    }
    if decision is None:
        return {**base, "retention": _unmeasured("ORDINARY_DIRECT_TEACHING"),
                "rejection_class": _unmeasured("ORDINARY_DIRECT_TEACHING"),
                "target": {"before": _unmeasured("ORDINARY_DIRECT_TEACHING"),
                           "after": _unmeasured("ORDINARY_DIRECT_TEACHING"),
                           "total": _unmeasured("ORDINARY_DIRECT_TEACHING")},
                "paired": _unmeasured("ORDINARY_DIRECT_TEACHING"),
                "protected": {"net_correct_delta": _unmeasured("ORDINARY_DIRECT_TEACHING")}}
    before, after, total = (decision.get("active_probe_before"),
                            decision.get("active_probe_after"),
                            decision.get("active_probe_total"))
    target_valid = all(type(value) is int for value in (before, after, total)) and 0 <= before <= total and 0 <= after <= total
    target_only = stage == "TARGET_ONLY_REJECTED"
    paired_evidence, protected_evidence = _paired_measurements(paired, protected)
    if target_only:
        protected_evidence = _unmeasured("TARGET_DID_NOT_GAIN")
    retained = decision.get("decision") == "PROVISIONAL"
    fixed_grade = decision.get("fixed_grade_replay")
    fixed_frontier = decision.get("fixed_frontier_replay")
    return {**base,
        "retention": _measured("RETAINED" if retained else "REJECTED"),
        "rejection_class": _measured(str(decision.get("reason", "UNSPECIFIED"))),
        "target": ({"before": _measured(before), "after": _measured(after), "total": _measured(total)}
                   if target_valid else {"before": _unmeasured("TARGET_PROBE_INVALID"), "after": _unmeasured("TARGET_PROBE_INVALID"), "total": _unmeasured("TARGET_PROBE_INVALID")}),
        "paired": paired_evidence,
        "protected": {"net_correct_delta": (protected_evidence if protected_evidence["status"] == NOT_MEASURED else _measured(protected_evidence["value"]["net_correct_delta"])),
                      "scope": protected_evidence},
        "fixed_grade": fixed_grade if isinstance(fixed_grade, Mapping) else _unmeasured("FIXED_GRADE_NOT_RECORDED"),
        "fixed_frontier": fixed_frontier if isinstance(fixed_frontier, Mapping) else _unmeasured("FIXED_FRONTIER_NOT_RECORDED"),
        "worst_protected_loss": (_unmeasured("TARGET_DID_NOT_GAIN") if target_only else
            (_measured(decision["worst_protected_loss"])
             if type(decision.get("worst_protected_loss")) is int else _unmeasured("PROTECTED_LOSS_NOT_RECORDED"))),
    }


def portable_v1_observation(region: Mapping, action: Mapping, outcome: Mapping):
    """Return #321 v1-compatible data only when every v1 field is measured."""
    target = outcome.get("target", {})
    protected = outcome.get("protected", {})
    values = (target.get("before"), target.get("after"), protected.get("net_correct_delta"),
              outcome.get("worst_protected_loss"), outcome.get("retention"), outcome.get("rejection_class"))
    if any(not isinstance(value, Mapping) or value.get("status") != MEASURED for value in values):
        return _unmeasured("PORTABLE_V1_INCOMPLETE")
    predictive_action = {"family": action.get("family"),
                         "effective_policy_key": action.get("effective_policy_key"),
                         "parameters": dict(sorted((action.get("parameters") or {}).items()))}
    if not all(isinstance(predictive_action[key], str) and predictive_action[key]
               for key in ("family", "effective_policy_key")):
        return _unmeasured("PORTABLE_V1_ACTION_INVALID")
    normalized_action = {**predictive_action, "policy_key": action.get("policy_key"),
                         "key": hashlib.sha256(json.dumps(predictive_action, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]}
    observation = {
        "schema": PORTABLE_V1_SCHEMA, "region": dict(region),
        "proposed_action": normalized_action,
        "retained": outcome["retention"]["value"] == "RETAINED",
        "rejection_reason": outcome["rejection_class"]["value"],
        "target_delta": target["after"]["value"] - target["before"]["value"],
        "protected_net_delta": protected["net_correct_delta"]["value"],
        "worst_protected_loss": outcome["worst_protected_loss"]["value"],
        "attempted_steps": outcome["attempted_steps"],
        "retained_steps": outcome["retained_steps"], "wall_seconds": outcome["wall_seconds"],
    }
    return observation


def summarize_observations(receipts) -> dict:
    """Summarize observed outcomes; absent prediction surfaces stay explicit."""
    outcomes = [item.get("outcome", item) if isinstance(item, Mapping) else None
                for item in receipts]
    outcomes = [item for item in outcomes if isinstance(item, Mapping)]
    retained = sum(item.get("retention", {}).get("value") == "RETAINED" for item in outcomes)
    rejected = sum(item.get("retention", {}).get("value") == "REJECTED" for item in outcomes)
    delivered = sum(len(item.get("delivered_teaching", ())) for item in receipts if isinstance(item, Mapping))
    return {"schema": OBSERVATION_SCHEMA, "observation_count": len(outcomes),
            "attempted_steps": _measured(sum(item.get("attempted_steps", 0) for item in outcomes)),
            "retained_steps": _measured(sum(item.get("retained_steps", 0) for item in outcomes)),
            "wall_seconds": _measured(sum(item.get("wall_seconds", 0.) for item in outcomes)),
            "retention_yield": _measured(retained / (retained + rejected)) if retained + rejected else _unmeasured("NO_CANDIDATE_SCREENS"),
            "rejection_mix": _measured(dict(Counter(
                item.get("rejection_class", {}).get("value") for item in outcomes
                if (item.get("retention", {}).get("value") == "REJECTED" and
                    item.get("rejection_class", {}).get("status") == MEASURED)))) if rejected else _unmeasured("NO_REJECTIONS"),
            "coverage": {"delivered_rows": _measured(delivered) if delivered else _unmeasured("DELIVERED_ROWS_NOT_EXPANDED")},
            "calibration": _unmeasured("NO_PREDICTION_EVIDENCE"),
            "shadow_probes": _unmeasured("NO_SHADOW_PROBE_EVIDENCE")}
