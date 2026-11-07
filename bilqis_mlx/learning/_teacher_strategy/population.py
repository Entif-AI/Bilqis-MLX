"""Bounded active teacher strategies over an immutable historical archive."""
from __future__ import annotations

import hashlib
import json
import math

from bilqis_mlx.learning.teacher_feedback import LearningExperimentError


UCB_EXPLORATION_WEIGHT = 0.6
SELECTION_POLICY = "bilqis.mlx.teacher-selection/349-replay-v1"
BAMF_SUCCESSOR_SELECTION = "bilqis.bamf.teacher-selection/replay-16-8-v1"
ACTIVE_EFFECTIVE_STRATEGY_LIMIT = 16
ACTIVE_EFFECTIVE_INCUMBENT_LIMIT = 8
DEEP_POLICY_DEPTH_MINIMUM = 3
SAME_STUDENT_POLICY_NO_TARGET_GAIN_LIMIT = 4
SAME_STUDENT_POLICY_UNRETAINED_LIMIT = 4
DURABLE_POLICY_FAILED_STUDENT_LIMIT = 2
DURABLE_POLICY_COOLDOWN_CAPABILITY_VISITS = 8
SIBLING_COOLDOWN_PENALTY = .025
MAX_FAILED_STUDENT_EPOCHS = 3
CONTEXT_PART_COUNT = 3
STUDENT_SHA256_HEX_LENGTH = 64
_INEFFECTIVE_POLICY_FIELDS = frozenset({"preview"})


def mint_novel_effective_strategy(engine, teacher: dict, rng):
    """Create one genuinely new executable strategy from the allowed knob space."""
    strategies = teacher.get("strategies", {})
    knobs = getattr(engine, "KNOBS", None)
    if not knobs:
        return None
    max_strategies = int(getattr(engine, "MAX_STRATEGIES", 512))
    max_attempts = int(getattr(engine, "MAX_MUTATION_ATTEMPTS", 24))
    max_context = int(getattr(engine, "MAX_TEACHER_CONTEXT_ITEMS", 24))
    if len(strategies) >= max_strategies:
        return None
    existing = set(effective_strategy_inventory(teacher))
    fields = tuple(knobs)
    for _ in range(max_attempts):
        variant = {field: rng.choice(knobs[field]) for field in fields}
        if variant["old"] + variant["preview"] > max_context:
            continue
        effective = effective_policy_key(variant)
        if effective in existing:
            continue
        identity = hashlib.sha256(
            json.dumps(variant, sort_keys=True).encode()).hexdigest()[:12]
        if identity in strategies:
            continue
        strategies[identity] = variant
        teacher.setdefault("global_stats", {})[identity] = {
            "trials": 0, "reward_sum": 0.0, "reward_ema": 0.0, "latest": None,
        }
        teacher["mutations"] = int(teacher.get("mutations", 0)) + 1
        return identity, variant
    return None


def effective_policy_features(policy: dict) -> dict:
    """Canonical pre-action knobs that actually change the current source lesson."""
    if not isinstance(policy, dict):
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    effective = {
        key: value for key, value in sorted(policy.items())
        if key not in _INEFFECTIVE_POLICY_FIELDS
    }
    if "depth" in effective:
        effective["depth"] = (
            "DEEP" if float(effective["depth"]) >= DEEP_POLICY_DEPTH_MINIMUM
            else "SHALLOW")
    if "contrast" in effective:
        effective["contrast"] = (
            "DIVERSE" if float(effective["contrast"]) >= .5 else "RANDOM")
    return effective


def effective_policy_key(policy: dict) -> str:
    """Identity for knobs that actually change the current source lesson."""
    effective = effective_policy_features(policy)
    return hashlib.sha256(
        json.dumps(effective, sort_keys=True).encode()).hexdigest()[:12]


def effective_context_scope(teacher: dict, scope: dict) -> dict:
    """Aggregate contextual evidence across behaviorally identical policies."""
    groups = {}
    strategies = teacher.get("strategies", {})
    for policy_key, record in scope.items():
        policy = strategies.get(policy_key)
        if policy is None:
            raise ValueError(LearningExperimentError.STRATEGY_ID_DRIFT.value)
        # Exact realized actions are forensic subrecords.  The contextual policy
        # record remains the predictive aggregate over legacy and realized outcomes.
        evidence = record
        effective_key = effective_policy_key(policy)
        group = groups.setdefault(effective_key, {
            "trials": 0, "reward_sum": 0., "unsafe": 0, "retained": 0,
            "no_target_gain_streak": 0, "members": [],
        })
        group["trials"] += int(evidence.get("trials", 0))
        group["reward_sum"] += float(evidence.get("reward_sum", 0.))
        group["unsafe"] += int(evidence.get("unsafe", 0))
        group["retained"] += int(evidence.get("retained", 0))
        group["no_target_gain_streak"] += int(
            evidence.get("no_target_gain_streak", 0))
        group["members"].append(policy_key)
    return groups


def historical_policy_mean(teacher: dict, grade: str, policy_key: str) -> float:
    """Bounded historical reward prior for challenger tie-breaking."""
    local = {} if teacher.get("selection_contract") == BAMF_SUCCESSOR_SELECTION else teacher.get("grade_stats", {}).get(str(grade), {})
    info = local.get(policy_key) or teacher.get("global_stats", {}).get(policy_key)
    if not isinstance(info, dict) or not info.get("trials"):
        return 0.
    trials = int(info["trials"])
    reward_sum = float(info.get("reward_sum", 0.))
    if trials < 1 or not math.isfinite(reward_sum):
        return 0.
    return max(-1., min(1., reward_sum / trials))


def effective_strategy_inventory(teacher: dict) -> dict[str, list[str]]:
    """Group immutable nominal strategies by currently executable behavior."""
    strategies = teacher.get("strategies", {})
    if not isinstance(strategies, dict) or not strategies:
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    inventory: dict[str, list[str]] = {}
    for policy_key, policy in strategies.items():
        inventory.setdefault(effective_policy_key(policy), []).append(policy_key)
    return inventory


def _retention_lower_bound(retained: int, trials: int) -> float:
    """One-sigma Wilson lower bound for conservative incumbent ranking."""
    if type(retained) is not int or type(trials) is not int or not 0 <= retained <= trials:
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    if trials == 0:
        return 0.
    proportion = retained / trials
    denominator = 1 + 1 / trials
    centre = proportion + 1 / (2 * trials)
    spread = math.sqrt(
        proportion * (1 - proportion) / trials + 1 / (4 * trials * trials))
    return (centre - spread) / denominator


def _group_prior(teacher: dict, grade: str, members: list[str]) -> float:
    return sum(
        historical_policy_mean(teacher, grade, member)
        for member in members
    ) / len(members)


def active_effective_strategy_keys(
        teacher: dict, grade: str,
        scope: dict, *, total_capabilities: int | None = None
        ) -> tuple[tuple[str, ...], dict[str, list[str]]]:
    """Choose <=16 context-local incumbents and rotating challengers."""
    inventory = effective_strategy_inventory(teacher)
    eligible = set(inventory)
    active_limit = ACTIVE_EFFECTIVE_STRATEGY_LIMIT
    incumbent_limit = ACTIVE_EFFECTIVE_INCUMBENT_LIMIT
    if total_capabilities is not None and teacher.get("selection_contract") != BAMF_SUCCESSOR_SELECTION:
        from .teacher_population_control import population_limits, rebalance_live_population
        eligible = set(rebalance_live_population(
            teacher, total_capabilities=total_capabilities))
        limits = population_limits(total_capabilities)
        active_limit = limits.active_effective
        incumbent_limit = max(1, active_limit // 2)
    if len(eligible) <= active_limit:
        return tuple(sorted(eligible)), inventory
    evidence = effective_context_scope(teacher, scope) if scope else {}

    def incumbent_rank(effective_key: str):
        record = evidence.get(effective_key) or {}
        trials = int(record.get("trials", 0))
        retained = int(record.get("retained", 0))
        reward_sum = float(record.get("reward_sum", 0.))
        mean = reward_sum / trials if trials else float("-inf")
        return (
            _retention_lower_bound(retained, trials), mean, trials,
            _group_prior(teacher, grade, inventory[effective_key]), effective_key,
        )

    proven = [
        effective_key for effective_key in eligible
        if int((evidence.get(effective_key) or {}).get("retained", 0)) > 0
    ]
    incumbents = sorted(
        proven, key=incumbent_rank, reverse=True)[:incumbent_limit]
    remaining = [key for key in eligible if key not in incumbents]

    def challenger_rank(effective_key: str):
        record = evidence.get(effective_key) or {}
        return (
            int(record.get("trials", 0)),
            int(record.get("retained", 0)),
            -_group_prior(teacher, grade, inventory[effective_key]),
            effective_key,
        )

    slots = active_limit - len(incumbents)
    challengers = sorted(remaining, key=challenger_rank)[:slots]
    return tuple((*incumbents, *challengers)), inventory
