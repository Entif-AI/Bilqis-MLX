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
OUTCOME_SCHEMA = "bilqis.factory.teacher-outcome/v1"
SUMMARY_SCHEMA = "bilqis.factory.teacher-observation-summary/v1"
PORTABLE_V1_SCHEMA = "bilqis.teacher-outcome-observation/v1"
REGION_SCHEMA = "bilqis.teacher-student-region/v1"
PERCENT_SCALE = 100
SCORE_BANDS = ((100, "P100"), (95, "P095_099"), (85, "P085_094"),
               (70, "P070_084"), (50, "P050_069"))
COUNT_BANDS = ((0, "00"), (3, "01_03"), (7, "04_07"),
               (15, "08_15"), (31, "16_31"))
PAIR_LENGTH = 2
MINIMUM_SCORE_TOTAL = 1


def _measured(value):
    return {"status": MEASURED, "value": value}


def _unmeasured(reason: str):
    return {"status": NOT_MEASURED, "reason": reason}


def _score_pair(value):
    if (isinstance(value, (tuple, list)) and len(value) == PAIR_LENGTH):
        correct, total = value
        if (type(correct) is int and type(total) is int and
                0 <= correct <= total and total >= MINIMUM_SCORE_TOTAL):
            return correct, total
        return None
    if not isinstance(value, Mapping):
        return None
    correct, total = value.get("correct"), value.get("total")
    if (type(correct) is not int or type(total) is not int or
            correct < 0 or total < MINIMUM_SCORE_TOTAL or correct > total):
        return None
    return correct, total


def _score_band(correct, total):
    if correct is None or total is None or total < MINIMUM_SCORE_TOTAL:
        return "UNMEASURED"
    percent = PERCENT_SCALE * correct / total
    for minimum, label in SCORE_BANDS:
        if percent >= minimum:
            return label
    return "P000_049"


def _count_band(value, *, prefix):
    if type(value) is not int or value < 0:
        return "UNMEASURED"
    for maximum, label in COUNT_BANDS:
        if value <= maximum:
            return prefix + label
    return prefix + "32_PLUS"


def _program_grade(program, capability: str) -> str:
    for grade in program.grades:
        if capability in {item.id for item in grade.capabilities}:
            return grade.id
    ErrorBus.Raise(SCHOOL.TEACHER_OBSERVATION.INVALID, capability=capability)


def _stagnation(teacher, capability, scope):
    if not isinstance(teacher, Mapping):
        return None, None
    causal = teacher.get("causal_experiment")
    if not isinstance(causal, Mapping):
        return 0, 0
    entries = causal.get("capability_stagnation")
    if not isinstance(entries, Mapping):
        return 0, 0
    # Rejection pressure is current-scope evidence, not a maximum over older curricula.
    entry = entries.get(capability + "|" + scope, {})
    if not isinstance(entry, Mapping):
        return None, None
    return entry.get("rejection_streak", 0), entry.get("attempts_since_retained", 0)


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
    grade_correct = grade_correct if grade_correct is not None else (sum(pair[0] for _, pair in present) if present and len(present) == len(grade_scores) else None)
    grade_total = grade_total if grade_total is not None else (sum(pair[1] for _, pair in present) if present and len(present) == len(grade_scores) else None)
    shape = "|".join(f"{name}={_score_band(*pair) if pair else 'UNMEASURED'}"
                     for name, pair in sorted(grade_scores)) or "UNMEASURED"
    debt = tuple((receipt.get("school") or {}).get("carried_mastery_debt") or ())
    grade_by_capability = {
        item.id: grade.id for grade in program.grades for item in grade.capabilities
    }
    debt_grades = Counter(grade_by_capability[item] for item in debt
                          if item in grade_by_capability)
    rejection_streak, attempts_since_retained = _stagnation(teacher, capability, curriculum_scope)
    predictive = {
        "schema": REGION_SCHEMA,
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
        if any(type(value) is not int for value in (before, after, total)) or total < MINIMUM_SCORE_TOTAL or not 0 <= before <= total or not 0 <= after <= total:
            return _unmeasured("PAIRED_PROBE_INVALID"), _unmeasured("PAIRED_PROBE_INVALID")
        entries[capability] = {"before": before, "after": after, "total": total}
    if not protected:
        return _measured(entries), _unmeasured("EMPTY_PROTECTED_MEASUREMENT_SCOPE")
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
        "schema": OUTCOME_SCHEMA,
        "stage": stage,
        "attempted_steps": attempted_steps,
        "retained_steps": retained_steps,
        "wall_seconds": wall_seconds,
        "fixed_grade": _unmeasured("NO_CANDIDATE_SCREEN"),
        "fixed_frontier": _unmeasured("NO_CANDIDATE_SCREEN"),
    }
    if decision is None:
        return {**base, "retention": _unmeasured("NO_CANDIDATE_SCREEN"),
                "rejection_class": _unmeasured("NO_CANDIDATE_SCREEN"),
                "target": {"before": _unmeasured("NO_CANDIDATE_SCREEN"),
                           "after": _unmeasured("NO_CANDIDATE_SCREEN"),
                           "total": _unmeasured("NO_CANDIDATE_SCREEN")},
                "paired": _unmeasured("NO_CANDIDATE_SCREEN"),
                "protected": {"net_correct_delta": _unmeasured("NO_CANDIDATE_SCREEN")}}
    before, after, total = (decision.get("active_probe_before"),
                            decision.get("active_probe_after"),
                            decision.get("active_probe_total"))
    target_valid = all(type(value) is int for value in (before, after, total)) and total >= MINIMUM_SCORE_TOTAL and 0 <= before <= total and 0 <= after <= total
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
             if protected_evidence["status"] == MEASURED and type(decision.get("worst_protected_loss")) is int else _unmeasured("PROTECTED_LOSS_NOT_RECORDED"))),
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


def _total(outcomes, field):
    values = [item.get(field) for item in outcomes]
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        return _unmeasured("COST_FIELD_NOT_RECORDED")
    return _measured(sum(values))


def _ratio(numerator, denominator):
    if numerator.get("status") != MEASURED or denominator is None or denominator <= 0:
        return _unmeasured("NO_MEASURED_RETENTION_DENOMINATOR")
    return _measured(numerator["value"] / denominator)


def summarize_observations(receipts) -> dict:
    """Summarize observed outcomes; absent prediction surfaces stay explicit."""
    envelopes = [item for item in receipts if isinstance(item, Mapping)]
    outcomes = [item.get("outcome", item) for item in envelopes]
    outcomes = [item for item in outcomes if isinstance(item, Mapping)]
    retained = sum(item.get("retention", {}).get("value") == "RETAINED" for item in outcomes)
    rejected = sum(item.get("retention", {}).get("value") == "REJECTED" for item in outcomes)
    expanded = [item for item in envelopes if isinstance(item.get("steps"), (tuple, list))]
    positions = [position for item in expanded for step in item["steps"]
                 if isinstance(step, Mapping) for position in step.get("positions", ())
                 if isinstance(position, Mapping)]
    role_counts = Counter(role for position in positions
                          for role in position.get("roles", ()) if isinstance(role, str))
    delivered_steps = sum(bool(step.get("delivered_teaching")) for item in expanded
                          for step in item["steps"] if isinstance(step, Mapping))
    proposals = [item.get("proposal") for item in expanded
                 if isinstance(item.get("proposal"), Mapping)]
    scheduling = (_measured({"lesson_grades": dict(Counter(
        proposal.get("student_region", {}).get("lesson_grade") for proposal in proposals
        if isinstance(proposal.get("student_region"), Mapping))),
        "phases": dict(Counter(proposal.get("phase") for proposal in proposals)),
        "mastery_debt_shapes": dict(Counter(
            proposal.get("student_region", {}).get("mastery_debt_shape") for proposal in proposals
            if isinstance(proposal.get("student_region"), Mapping)))})
        if proposals else _unmeasured("PROPOSAL_NOT_EXPANDED"))
    accepted = [item for item in envelopes
                if item.get("outcome", item).get("retention", {}).get("value") == "RETAINED"]
    publications_known = all(isinstance(item.get("publication"), Mapping) for item in accepted)
    durable = (sum(item["publication"].get("status") == "DURABLE_CHECKPOINT_OUTBOX"
                   for item in accepted) if publications_known else None)
    shadow_reviews = [item.get("teacher_multifidelity_shadow") for item in envelopes
                      if isinstance(item.get("teacher_multifidelity_shadow"), Mapping)]
    shadow_activations = [item.get("teacher_multifidelity_activation") for item in envelopes
                          if isinstance(item.get("teacher_multifidelity_activation"), Mapping)]
    totals = {name: _total(outcomes, name) for name in ("attempted_steps", "retained_steps", "wall_seconds")}
    return {"schema": SUMMARY_SCHEMA, "observation_count": len(outcomes),
            "predictions": _unmeasured("NO_PREDICTION_EVIDENCE"),
            "attempted_steps_per_provisional_retention": _ratio(totals["attempted_steps"], retained),
            "seconds_per_provisional_retention": _ratio(totals["wall_seconds"], retained),
            "seconds_per_durable_retention": _ratio(totals["wall_seconds"], durable),
            "attempted_steps": totals["attempted_steps"],
            "retained_steps": totals["retained_steps"],
            "wall_seconds": totals["wall_seconds"],
            "retention_yield": _measured(retained / (retained + rejected)) if retained + rejected else _unmeasured("NO_CANDIDATE_SCREENS"),
            "retention_yield_semantics": "PROVISIONAL_RAM_CANDIDATE_ACCEPTANCE",
            "durable_retention_yield": (_measured(durable / (retained + rejected))
                if durable is not None and retained + rejected else _unmeasured("NO_DURABLE_RETENTION_DENOMINATOR")),
            "retention": {"provisional_accepted_attempts": _measured(len(accepted)),
                          "provisional_retained_steps": _measured(sum(
                              item.get("outcome", item).get("retained_steps", 0) for item in accepted)),
                          "durable_accepted_attempts": (_measured(durable)
                              if durable is not None else _unmeasured("PUBLICATION_NOT_EXPANDED"))},
            "rejection_mix": _measured(dict(Counter(
                item.get("rejection_class", {}).get("value") for item in outcomes
                if (item.get("retention", {}).get("value") == "REJECTED" and
                    item.get("rejection_class", {}).get("status") == MEASURED)))) if rejected else _unmeasured("NO_REJECTIONS"),
            "coverage": ({"optimizer_rows": _measured(len(positions)),
                          "delivered_teaching_steps": _measured(delivered_steps),
                          "roles": _measured(dict(role_counts))}
                         if expanded else {"optimizer_rows": _unmeasured("STEPS_NOT_EXPANDED"),
                                           "delivered_teaching_steps": _unmeasured("STEPS_NOT_EXPANDED"),
                                           "roles": _unmeasured("STEPS_NOT_EXPANDED")}),
            "scheduling": scheduling,
            "calibration": (_measured(shadow_activations[-1]) if shadow_activations
                            else _unmeasured("NO_PREDICTION_EVIDENCE")),
            "shadow_probes": (_measured({
                "reviews": len(shadow_reviews),
                "early_stop_recommendations": sum(
                    row.get("first_would_stop_step") is not None for row in shadow_reviews),
                "false_kills": sum(bool(row.get("false_kill")) for row in shadow_reviews),
                "shadow_steps_saved": sum(
                    int(row.get("shadow_steps_saved", 0)) for row in shadow_reviews),
            }) if shadow_reviews else _unmeasured("NO_SHADOW_PROBE_EVIDENCE"))}
