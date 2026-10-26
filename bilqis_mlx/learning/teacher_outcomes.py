"""Portable evidence model for teacher proposal quality.

The exact visit/event ledger remains provenance.  This module maintains a compact,
generalizable statistical view that both the current Prometheus teacher and a future
teacher implementation can consume without sharing runtime internals.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math


REGION_SCHEMA = "bilqis.teacher-student-region/v1"
OBSERVATION_SCHEMA = "bilqis.teacher-outcome-observation/v1"
MODEL_SCHEMA = "bilqis.teacher-outcome-model/v1"
MODEL_VERSION = 1
WILSON_Z_95 = 1.959963984540054
RECENT_OBSERVATION_LIMIT = 128
PERCENT_SCALE = 100
SCORE_BAND_PERFECT_MIN = 100
SCORE_BAND_EXCELLENT_MIN = 95
SCORE_BAND_STRONG_MIN = 85
SCORE_BAND_MID_MIN = 70
SCORE_BAND_WEAK_MIN = 50
COUNT_BAND_LOW_MAX = 3
COUNT_BAND_MID_MAX = 7
MIN_VARIANCE_SAMPLE_SIZE = 2


class TeacherOutcomeError(str, Enum):
    ACTION_INVALID = "TEACHER_OUTCOME_ACTION_INVALID"
    HEALTH_OBSERVATION_INVALID = "TEACHER_HEALTH_OBSERVATION_INVALID"
    HEALTH_POLICY_INVALID = "TEACHER_HEALTH_POLICY_INVALID"
    MODEL_DRIFT = "TEACHER_OUTCOME_MODEL_DRIFT"
    OBSERVATION_METRIC_INVALID = "TEACHER_OUTCOME_OBSERVATION_METRIC_INVALID"
    OBSERVATION_REGION_INVALID = "TEACHER_OUTCOME_OBSERVATION_REGION_INVALID"
    OBSERVATION_RESULT_INVALID = "TEACHER_OUTCOME_OBSERVATION_RESULT_INVALID"
    OBSERVATION_SCHEMA_INVALID = "TEACHER_OUTCOME_OBSERVATION_SCHEMA_INVALID"
    PREDICTION_INVALID = "TEACHER_OUTCOME_PREDICTION_INVALID"
    PROPOSED_ACTION_INVALID = "TEACHER_PROPOSED_ACTION_INVALID"
    PROTECTED_INVALID = "TEACHER_OUTCOME_PROTECTED_INVALID"
    REGION_COUNT_INVALID = "TEACHER_REGION_COUNT_INVALID"
    REGION_IDENTITY_INVALID = "TEACHER_REGION_IDENTITY_INVALID"
    REGION_INVALID = "TEACHER_OUTCOME_REGION_INVALID"
    REGION_KEY_COLLISION = "TEACHER_OUTCOME_REGION_KEY_COLLISION"
    REGION_OVERFRAGMENTED = "TEACHER_OUTCOME_REGION_OVERFRAGMENTED"
    REGION_SCORE_INVALID = "TEACHER_REGION_SCORE_INVALID"
    RESULT_INVALID = "TEACHER_OUTCOME_RESULT_INVALID"
    SHADOW_REVIEW_INVALID = "TEACHER_OUTCOME_SHADOW_REVIEW_INVALID"
    STATE_INVALID = "TEACHER_OUTCOME_STATE_INVALID"
    STEP_COST_INVALID = "TEACHER_OUTCOME_STEP_COST_INVALID"
    TARGET_INVALID = "TEACHER_OUTCOME_TARGET_INVALID"
    WALL_TIME_INVALID = "TEACHER_OUTCOME_WALL_TIME_INVALID"


@dataclass(frozen=True)
class HealthPolicy:
    version: str
    minimum_support: int
    exhausted_zero_retention_visits: int
    low_yield_retention_fraction: float

    def __post_init__(self) -> None:
        if (not self.version or type(self.minimum_support) is not int or
                type(self.exhausted_zero_retention_visits) is not int or
                self.minimum_support < 1 or
                self.exhausted_zero_retention_visits < self.minimum_support or
                not 0 < self.low_yield_retention_fraction < 1):
            raise ValueError(TeacherOutcomeError.HEALTH_POLICY_INVALID.value)


DEFAULT_HEALTH_POLICY = HealthPolicy(
    version="teacher-health/v1",
    minimum_support=8,
    exhausted_zero_retention_visits=16,
    low_yield_retention_fraction=.10,
)


def _score_band(correct: int | None, total: int | None) -> str:
    if correct is None and total is None:
        return "UNMEASURED"
    if (type(correct) is not int or type(total) is not int or total < 1 or
            not 0 <= correct <= total):
        raise ValueError(TeacherOutcomeError.REGION_SCORE_INVALID.value)
    percent = PERCENT_SCALE * correct / total
    if percent == SCORE_BAND_PERFECT_MIN:
        return "P100"
    if percent >= SCORE_BAND_EXCELLENT_MIN:
        return "P095_099"
    if percent >= SCORE_BAND_STRONG_MIN:
        return "P085_094"
    if percent >= SCORE_BAND_MID_MIN:
        return "P070_084"
    if percent >= SCORE_BAND_WEAK_MIN:
        return "P050_069"
    return "P000_049"


def _count_band(value: int, *, prefix: str) -> str:
    if type(value) is not int or value < 0:
        raise ValueError(TeacherOutcomeError.REGION_COUNT_INVALID.value)
    if value == 0:
        return prefix + "00"
    if value <= COUNT_BAND_LOW_MAX:
        return prefix + "01_03"
    if value <= COUNT_BAND_MID_MAX:
        return prefix + "04_07"
    return prefix + "08_PLUS"


def student_region(*, capability: str, phase: str, lesson_grade: str,
                   curriculum_scope: str, geometry_epoch: str | None,
                   numeric_maximum: int | None,
                   capability_correct: int | None,
                   capability_total: int | None,
                   grade_correct: int | None, grade_total: int | None,
                   rejection_streak: int, attempts_since_retained: int,
                   mastery_debt_count: int) -> dict:
    """Return a coarse predictive region with exact identities deliberately absent."""
    if (not isinstance(capability, str) or "." not in capability or
            not isinstance(phase, str) or not phase or
            not isinstance(lesson_grade, str) or not lesson_grade or
            not isinstance(curriculum_scope, str) or
            (geometry_epoch is not None and not isinstance(geometry_epoch, str)) or
            (numeric_maximum is not None and
             (type(numeric_maximum) is not int or numeric_maximum < 0))):
        raise ValueError(TeacherOutcomeError.REGION_IDENTITY_INVALID.value)
    region = {
        "schema": REGION_SCHEMA,
        "capability": capability,
        "phase": phase.removeprefix("ASSESS_"),
        "lesson_grade": lesson_grade,
        "curriculum_scope": curriculum_scope,
        "geometry_epoch": geometry_epoch,
        "numeric_maximum": numeric_maximum,
        "capability_score_band": _score_band(
            capability_correct, capability_total),
        "grade_score_band": _score_band(grade_correct, grade_total),
        "rejection_pressure_band": _count_band(
            rejection_streak, prefix="R"),
        "attempts_since_retained_band": _count_band(
            attempts_since_retained, prefix="A"),
        "mastery_debt_band": _count_band(mastery_debt_count, prefix="D"),
    }
    region["key"] = hashlib.sha256(json.dumps(
        region, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()[:20]
    return region


def proposed_action(*, family: str, effective_policy_key: str,
                    policy_key: str | None = None,
                    parameters: dict | None = None) -> dict:
    if (not isinstance(family, str) or not family or
            not isinstance(effective_policy_key, str) or not effective_policy_key or
            (policy_key is not None and not isinstance(policy_key, str)) or
            (parameters is not None and not isinstance(parameters, dict))):
        raise ValueError(TeacherOutcomeError.PROPOSED_ACTION_INVALID.value)
    predictive = {
        "family": family,
        "effective_policy_key": effective_policy_key,
        "parameters": dict(sorted((parameters or {}).items())),
    }
    return {
        **predictive,
        "policy_key": policy_key,
        "key": hashlib.sha256(json.dumps(
            predictive, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()[:20],
    }


def validate_portable_observation(observation: dict) -> None:
    """Validate the architecture-neutral evidence contract consumed by #321/#130."""
    if (not isinstance(observation, dict) or
            observation.get("schema") != OBSERVATION_SCHEMA):
        raise ValueError(TeacherOutcomeError.OBSERVATION_SCHEMA_INVALID.value)
    region = observation.get("region")
    action = observation.get("proposed_action")
    if (not isinstance(region, dict) or region.get("schema") != REGION_SCHEMA or
            not isinstance(region.get("key"), str)):
        raise ValueError(TeacherOutcomeError.OBSERVATION_REGION_INVALID.value)
    forbidden_region_keys = {
        "student_sha256", "checkpoint_sha256", "cohort_sha256",
        "batch_sha256", "source_cohort_sha256",
    }
    if forbidden_region_keys & set(region):
        raise ValueError(TeacherOutcomeError.REGION_OVERFRAGMENTED.value)
    _validate_action(action)
    if (type(observation.get("retained")) is not bool or
            not isinstance(observation.get("rejection_reason"), str) or
            type(observation.get("attempted_steps")) is not int or
            type(observation.get("retained_steps")) is not int or
            not 0 <= observation["retained_steps"] <= observation["attempted_steps"]):
        raise ValueError(TeacherOutcomeError.OBSERVATION_RESULT_INVALID.value)
    for key in ("target_delta", "protected_net_delta",
                "worst_protected_loss", "wall_seconds"):
        if (not isinstance(observation.get(key), (int, float)) or
                not math.isfinite(observation[key])):
            raise ValueError(TeacherOutcomeError.OBSERVATION_METRIC_INVALID.value)
    if observation["worst_protected_loss"] < 0 or observation["wall_seconds"] < 0:
        raise ValueError(TeacherOutcomeError.OBSERVATION_METRIC_INVALID.value)


def _validate_action(action: dict) -> None:
    if (not isinstance(action, dict) or not isinstance(action.get("family"), str) or
            not isinstance(action.get("effective_policy_key"), str)):
        raise ValueError(TeacherOutcomeError.ACTION_INVALID.value)


def _model(teacher: dict) -> dict:
    if not isinstance(teacher, dict):
        raise ValueError(TeacherOutcomeError.STATE_INVALID.value)
    model = teacher.setdefault("outcome_model", {
        "schema": MODEL_SCHEMA,
        "version": MODEL_VERSION,
        "events": 0,
        "contexts": {},
        "recent": [],
    })
    if (model.get("schema") != MODEL_SCHEMA or
            model.get("version") != MODEL_VERSION or
            type(model.get("events")) is not int or
            not isinstance(model.get("contexts"), dict) or
            not isinstance(model.setdefault("recent", []), list)):
        raise ValueError(TeacherOutcomeError.MODEL_DRIFT.value)
    return model


def _context_key(region: dict, action: dict) -> str:
    if region.get("schema") != REGION_SCHEMA or not isinstance(region.get("key"), str):
        raise ValueError(TeacherOutcomeError.REGION_INVALID.value)
    _validate_action(action)
    action_key = action.get("key") or hashlib.sha256(json.dumps({
        "family": action["family"],
        "effective_policy_key": action["effective_policy_key"],
        "parameters": action.get("parameters", {}),
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
    return region["key"] + "|" + action_key


def _finite_number(value, *, name: str, minimum: float | None = None) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name)
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise ValueError(name)
    return numeric


def _outcome_record(model: dict, key: str, region: dict, action: dict) -> dict:
    record = model["contexts"].setdefault(key, {
        "region": region,
        "action": {
            "family": action["family"],
            "effective_policy_key": action["effective_policy_key"],
            "key": action.get("key"),
            "parameters": dict(action.get("parameters") or {}),
        },
        "trials": 0, "retained": 0,
        "target_delta_sum": 0., "target_delta_sq_sum": 0.,
        "protected_net_delta_sum": 0., "protected_net_delta_sq_sum": 0.,
        "worst_protected_loss_sum": 0., "attempted_steps_sum": 0,
        "retained_steps_sum": 0, "wall_seconds_sum": 0.,
        "wall_seconds_sq_sum": 0., "rejection_reasons": {},
    })
    if record.get("region") != region:
        raise ValueError(TeacherOutcomeError.REGION_KEY_COLLISION.value)
    return record


def _update_outcome_record(record: dict, *, retained: bool,
                           rejection_reason: str, target_delta: float,
                           protected_net_delta: float, worst_protected_loss: float,
                           attempted_steps: int, retained_steps: int,
                           wall_seconds: float) -> None:
    record["trials"] += 1
    record["retained"] += int(retained)
    for name, value in (
        ("target_delta", target_delta),
        ("protected_net_delta", protected_net_delta),
        ("wall_seconds", wall_seconds),
    ):
        record[name + "_sum"] += value
        record[name + "_sq_sum"] += value * value
    record["worst_protected_loss_sum"] += worst_protected_loss
    record["attempted_steps_sum"] += attempted_steps
    record["retained_steps_sum"] += retained_steps
    if not retained:
        reasons = record["rejection_reasons"]
        reasons[rejection_reason] = reasons.get(rejection_reason, 0) + 1


def observe(teacher: dict, *, region: dict, action: dict, retained: bool,
            rejection_reason: str, target_delta: float,
            protected_net_delta: float, worst_protected_loss: float,
            attempted_steps: int, retained_steps: int,
            wall_seconds: float,
            predicted_retention_probability: float | None = None,
            shadow_review: dict | None = None) -> dict:
    """Update compact predictive aggregates and return a portable event observation."""
    if type(retained) is not bool or not isinstance(rejection_reason, str) or not rejection_reason:
        raise ValueError(TeacherOutcomeError.RESULT_INVALID.value)
    if (type(attempted_steps) is not int or type(retained_steps) is not int or
            attempted_steps < 0 or not 0 <= retained_steps <= attempted_steps):
        raise ValueError(TeacherOutcomeError.STEP_COST_INVALID.value)
    target_delta = _finite_number(
        target_delta, name=TeacherOutcomeError.TARGET_INVALID.value)
    protected_net_delta = _finite_number(
        protected_net_delta, name=TeacherOutcomeError.PROTECTED_INVALID.value)
    worst_protected_loss = _finite_number(
        worst_protected_loss, name=TeacherOutcomeError.PROTECTED_INVALID.value,
        minimum=0.)
    wall_seconds = _finite_number(
        wall_seconds, name=TeacherOutcomeError.WALL_TIME_INVALID.value, minimum=0.)
    if (predicted_retention_probability is not None and
            (not isinstance(predicted_retention_probability, (int, float)) or
             not math.isfinite(predicted_retention_probability) or
             not 0 <= predicted_retention_probability <= 1)):
        raise ValueError(TeacherOutcomeError.PREDICTION_INVALID.value)
    if shadow_review is not None and not isinstance(shadow_review, dict):
        raise ValueError(TeacherOutcomeError.SHADOW_REVIEW_INVALID.value)
    key = _context_key(region, action)
    model = _model(teacher)
    record = _outcome_record(model, key, region, action)
    _update_outcome_record(
        record, retained=retained, rejection_reason=rejection_reason,
        target_delta=target_delta, protected_net_delta=protected_net_delta,
        worst_protected_loss=worst_protected_loss,
        attempted_steps=attempted_steps, retained_steps=retained_steps,
        wall_seconds=wall_seconds)
    model["events"] += 1
    observation = {
        "schema": OBSERVATION_SCHEMA,
        "region": region,
        "proposed_action": action,
        "retained": retained,
        "rejection_reason": rejection_reason,
        "target_delta": target_delta,
        "protected_net_delta": protected_net_delta,
        "worst_protected_loss": worst_protected_loss,
        "attempted_steps": attempted_steps,
        "retained_steps": retained_steps,
        "wall_seconds": wall_seconds,
        "model_context_key": key,
    }
    if predicted_retention_probability is not None:
        observation["predicted_retention_probability"] = float(
            predicted_retention_probability)
    if shadow_review is not None:
        observation["shadow_review"] = shadow_review
    model["recent"].append({
        "retained": retained,
        "target_delta": target_delta,
        "protected_net_delta": protected_net_delta,
        "worst_protected_loss": worst_protected_loss,
        "attempted_steps": attempted_steps,
        "retained_steps": retained_steps,
        "wall_seconds": wall_seconds,
        "proposal_family": action["family"],
        "predicted_retention_probability": predicted_retention_probability,
        "shadow_review": shadow_review,
    })
    del model["recent"][:-RECENT_OBSERVATION_LIMIT]
    validate_portable_observation(observation)
    return observation


def _wilson(retained: int, trials: int) -> tuple[float, float]:
    if trials == 0:
        return 0., 1.
    proportion = retained / trials
    z2 = WILSON_Z_95 * WILSON_Z_95
    denominator = 1 + z2 / trials
    centre = (proportion + z2 / (2 * trials)) / denominator
    radius = (WILSON_Z_95 / denominator) * math.sqrt(
        proportion * (1 - proportion) / trials + z2 / (4 * trials * trials))
    return max(0., centre - radius), min(1., centre + radius)


def _standard_error(total: float, square_total: float, trials: int) -> float:
    if trials < MIN_VARIANCE_SAMPLE_SIZE:
        return 0.
    mean = total / trials
    variance = max(0., (square_total - trials * mean * mean) / (trials - 1))
    return math.sqrt(variance / trials)


def predict(teacher: dict, *, region: dict, action: dict) -> dict:
    model = _model(teacher)
    record = model["contexts"].get(_context_key(region, action))
    if record is None:
        return {
            "trials": 0,
            "retained": 0,
            "retention_probability": .5,
            "retention_interval": (0., 1.),
            "expected_target_delta": 0.,
            "target_delta_standard_error": 0.,
            "expected_protected_net_delta": 0.,
            "protected_delta_standard_error": 0.,
            "expected_candidate_steps": 0.,
            "expected_retained_steps": 0.,
            "expected_wall_seconds": 0.,
            "wall_seconds_standard_error": 0.,
        }
    trials = int(record["trials"])
    retained = int(record["retained"])
    return {
        "trials": trials,
        "retained": retained,
        "retention_probability": retained / trials,
        "retention_interval": _wilson(retained, trials),
        "expected_target_delta": record["target_delta_sum"] / trials,
        "target_delta_standard_error": _standard_error(
            record["target_delta_sum"], record["target_delta_sq_sum"], trials),
        "expected_protected_net_delta": record["protected_net_delta_sum"] / trials,
        "protected_delta_standard_error": _standard_error(
            record["protected_net_delta_sum"],
            record["protected_net_delta_sq_sum"], trials),
        "expected_candidate_steps": record["attempted_steps_sum"] / trials,
        "expected_retained_steps": record["retained_steps_sum"] / trials,
        "expected_wall_seconds": record["wall_seconds_sum"] / trials,
        "wall_seconds_standard_error": _standard_error(
            record["wall_seconds_sum"], record["wall_seconds_sq_sum"], trials),
        "mean_worst_protected_loss": record["worst_protected_loss_sum"] / trials,
        "rejection_reasons": dict(sorted(record["rejection_reasons"].items())),
    }


def health_summary(observations, *, policy: HealthPolicy = DEFAULT_HEALTH_POLICY) -> dict:
    rows = tuple(observations)
    for row in rows:
        if (not isinstance(row, dict) or type(row.get("retained")) is not bool or
                type(row.get("attempted_steps")) is not int or
                type(row.get("retained_steps")) is not int):
            raise ValueError(TeacherOutcomeError.HEALTH_OBSERVATION_INVALID.value)
    attempted = len(rows)
    retained = sum(int(row["retained"]) for row in rows)
    attempted_steps = sum(row["attempted_steps"] for row in rows)
    retained_steps = sum(row["retained_steps"] for row in rows)
    wall_seconds = sum(float(row.get("wall_seconds", 0.)) for row in rows)
    prediction_pairs = [
        (float(row["predicted_retention_probability"]), int(row["retained"]))
        for row in rows
        if isinstance(row.get("predicted_retention_probability"), (int, float))
    ]
    proposal_families = {}
    shadow_reviews = []
    for row in rows:
        family = row.get("proposal_family")
        if isinstance(family, str) and family:
            proposal_families[family] = proposal_families.get(family, 0) + 1
        if isinstance(row.get("shadow_review"), dict):
            shadow_reviews.append(row["shadow_review"])
    rate = retained / attempted if attempted else None
    if attempted < policy.minimum_support:
        status = "UNCERTAIN_EXPLORING"
    elif retained == 0 and attempted >= policy.exhausted_zero_retention_visits:
        status = "SEARCH_NEIGHBORHOOD_EXHAUSTED"
    elif rate is not None and rate < policy.low_yield_retention_fraction:
        status = "LOW_YIELD"
    else:
        status = "PRODUCTIVE"
    return {
        "policy_version": policy.version,
        "status": status,
        "attempted_candidates": attempted,
        "retained_candidates": retained,
        "retention_rate": rate,
        "attempted_optimizer_steps": attempted_steps,
        "retained_optimizer_steps": retained_steps,
        "optimizer_steps_per_retention": (
            attempted_steps / retained if retained else None),
        "visits_per_retention": attempted / retained if retained else None,
        "wall_seconds": wall_seconds,
        "wall_seconds_per_retention": wall_seconds / retained if retained else None,
        "retention_brier_score": (
            sum((probability - actual) ** 2
                for probability, actual in prediction_pairs) / len(prediction_pairs)
            if prediction_pairs else None),
        "calibration_observations": len(prediction_pairs),
        "proposal_family_allocation": dict(sorted(proposal_families.items())),
        "shadow_early_stop_recommendations": sum(
            review.get("first_would_stop_step") is not None
            for review in shadow_reviews),
        "shadow_false_kills": sum(bool(review.get("false_kill"))
                                  for review in shadow_reviews),
        "shadow_false_continues": sum(bool(review.get("false_continue"))
                                      for review in shadow_reviews),
        "shadow_steps_saved_if_active": sum(
            int(review.get("shadow_steps_saved", 0)) for review in shadow_reviews),
    }


def current_health(teacher: dict, *,
                   policy: HealthPolicy = DEFAULT_HEALTH_POLICY) -> dict:
    return health_summary(_model(teacher)["recent"], policy=policy)
