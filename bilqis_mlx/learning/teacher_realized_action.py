"""Delivered teacher-action identity for causal contextual credit."""
from __future__ import annotations

import hashlib
import json
import math

from bilqis_mlx.learning.teacher_feedback import LearningExperimentError
from bilqis_mlx.learning.teacher_strategy_population import effective_policy_key


SCHEMA = "bilqis.teacher-realized-action/v1"


def describe(policy: dict, *, candidate_steps: int, batch_size: int,
             policy_controls, guidance_applied_steps: int,
             enrichment_examples: int) -> dict:
    """Describe what the optimizer actually received, not what policy requested."""
    if (not isinstance(policy, dict) or type(candidate_steps) is not int or
            candidate_steps < 1 or type(batch_size) is not int or batch_size < 1 or
            type(guidance_applied_steps) is not int or
            not 0 <= guidance_applied_steps <= candidate_steps or
            type(enrichment_examples) is not int or enrichment_examples < 0):
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    controls = tuple(policy_controls or ())
    if any(not isinstance(item, dict) for item in controls):
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    lr = policy.get("lr")
    if not isinstance(lr, (int, float)) or not math.isfinite(lr) or lr <= 0:
        raise ValueError(LearningExperimentError.POLICY_LR_INVALID.value)

    def delivered_total(field: str) -> int:
        values = [item.get(field, 0) for item in controls]
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError(LearningExperimentError.POLICY_INVALID.value)
        return sum(values)

    def mode_counts(field: str) -> dict[str, int]:
        counts = {}
        for item in controls:
            value = item.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                raise ValueError(LearningExperimentError.POLICY_INVALID.value)
            counts[value] = counts.get(value, 0) + 1
        return dict(sorted(counts.items()))

    answer_kinds = sorted({
        kind for item in controls for kind in item.get("selected_answer_kinds", ())
        if isinstance(kind, str) and kind
    })
    distill = float(policy.get("distill", 0.0))
    if not math.isfinite(distill) or distill < 0:
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    features = {
        "learning_rate": float(lr),
        "candidate_steps": candidate_steps,
        "batch_size": batch_size,
        "optimizer_batches_observed": len(controls),
        "depth_controls": mode_counts("depth_control"),
        "contrast_controls": mode_counts("contrast_control"),
        "old_grade_examples_delivered": delivered_total(
            "effective_old_grade_examples"),
        "fragile_preservation_delivered": delivered_total(
            "fragile_preservation_delivered"),
        "retention_support_delivered": delivered_total(
            "retention_support_delivered"),
        "fresh_support_delivered": delivered_total("fresh_support_delivered"),
        "weakness_targets_delivered": delivered_total(
            "weakness_targets_delivered"),
        "priority_weakness_targets_delivered": delivered_total(
            "priority_weakness_targets_delivered"),
        "semantic_patterns_delivered": delivered_total(
            "current_semantic_patterns_delivered"),
        "semantic_patterns_required": delivered_total(
            "current_semantic_patterns_required"),
        "guided_optimizer_steps": guidance_applied_steps,
        "distill_weight_applied": distill if guidance_applied_steps else 0.0,
        "enrichment_examples": enrichment_examples,
        "answer_kinds": answer_kinds,
    }
    key = hashlib.sha256(
        json.dumps(features, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return {"schema": SCHEMA, "key": key, "features": features}


def validate(action: dict | None) -> tuple[str, dict] | None:
    if action is None:
        return None
    if (not isinstance(action, dict) or action.get("schema") != SCHEMA or
            not isinstance(action.get("key"), str) or
            not isinstance(action.get("features"), dict)):
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    expected = hashlib.sha256(json.dumps(
        action["features"], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()[:16]
    if action["key"] != expected:
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    return action["key"], action["features"]


def bind_record(record: dict, action: dict | None,
                nominal_stagnation_key: str) -> tuple[str | None, dict | None, str]:
    """Bind one delivered-action record while preserving legacy nominal evidence."""
    realized = validate(action)
    if realized is None:
        return None, None, nominal_stagnation_key
    action_key, action_features = realized
    actions = record.setdefault("realized_actions", {})
    action_record = actions.setdefault(action_key, {
        "action": action_features,
        "trials": 0,
        "reward_sum": 0.,
        "unsafe": 0,
        "retained": 0,
        "latest": None,
        "no_target_gain_streak": 0,
    })
    if action_record.get("action") != action_features:
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    record["latest_realized_action_key"] = action_key
    return action_key, action_record, "realized:" + action_key


def record_outcome(action_record: dict | None, *, rejected: bool,
                   no_target_gain: bool, reward: float,
                   diagnostic_key: str) -> None:
    """Update realized-action evidence after the nominal compatibility record."""
    if action_record is None:
        return
    action_record["unsafe" if rejected else "retained"] += 1
    action_record["no_target_gain_streak"] = (
        action_record["no_target_gain_streak"] + 1 if no_target_gain else 0)
    action_record["trials"] += 1
    action_record["reward_sum"] += reward
    action_record["latest"] = reward
    diagnostic = action_record.setdefault("diagnostic_stats", {}).setdefault(
        diagnostic_key, {
            "trials": 0, "reward_sum": 0., "unsafe": 0, "retained": 0,
        })
    diagnostic["trials"] += 1
    diagnostic["reward_sum"] += reward
    diagnostic["unsafe" if rejected else "retained"] += 1


def selection_record(policy: dict, record: dict) -> tuple[str, dict]:
    actions = record.get("realized_actions")
    latest = record.get("latest_realized_action_key")
    if isinstance(actions, dict) and isinstance(latest, str):
        action_record = actions.get(latest)
        if isinstance(action_record, dict) and action_record.get("trials", 0) > 0:
            return "realized:" + latest, action_record
    return "nominal:" + effective_policy_key(policy), record


def context_scope(teacher: dict, scope: dict, *,
                  active_effective: set[str] | None = None,
                  diagnostic_key: str | None = None) -> dict:
    """Pool evidence by the latest delivered action of each active nominal policy."""
    groups = {}
    strategies = teacher.get("strategies", {})
    for policy_key, record in scope.items():
        policy = strategies.get(policy_key)
        if policy is None:
            raise ValueError(LearningExperimentError.STRATEGY_ID_DRIFT.value)
        nominal_effective = effective_policy_key(policy)
        if active_effective is not None and nominal_effective not in active_effective:
            continue
        group_key, evidence = selection_record(policy, record)
        if diagnostic_key is not None:
            evidence = evidence.get("diagnostic_stats", {}).get(diagnostic_key)
            if not isinstance(evidence, dict) or not evidence.get("trials"):
                continue
        group = groups.setdefault(group_key, {
            "trials": 0, "reward_sum": 0., "unsafe": 0, "retained": 0,
            "no_target_gain_streak": 0, "members": [], "member_records": {},
        })
        group["trials"] += int(evidence.get("trials", 0))
        group["reward_sum"] += float(evidence.get("reward_sum", 0.))
        group["unsafe"] += int(evidence.get("unsafe", 0))
        group["retained"] += int(evidence.get("retained", 0))
        group["no_target_gain_streak"] += int(
            evidence.get("no_target_gain_streak", 0))
        group["members"].append(policy_key)
        group["member_records"][policy_key] = evidence
    return groups
