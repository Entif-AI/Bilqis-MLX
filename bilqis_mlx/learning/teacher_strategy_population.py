"""Bounded active teacher strategies over an immutable historical archive."""
from __future__ import annotations

import hashlib
import json
import math

from bilqis_mlx.learning.teacher_feedback import LearningExperimentError


UCB_EXPLORATION_WEIGHT = 0.6
ACTIVE_EFFECTIVE_STRATEGY_LIMIT = 16
ACTIVE_EFFECTIVE_INCUMBENT_LIMIT = 8
DEEP_POLICY_DEPTH_MINIMUM = 3
_INEFFECTIVE_POLICY_FIELDS = frozenset({"preview"})


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
    local = teacher.get("grade_stats", {}).get(str(grade), {})
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
        scope: dict) -> tuple[tuple[str, ...], dict[str, list[str]]]:
    """Choose <=16 context-local incumbents and rotating challengers."""
    inventory = effective_strategy_inventory(teacher)
    if len(inventory) <= ACTIVE_EFFECTIVE_STRATEGY_LIMIT:
        return tuple(sorted(inventory)), inventory
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
        effective_key for effective_key in inventory
        if int((evidence.get(effective_key) or {}).get("retained", 0)) > 0
    ]
    incumbents = sorted(
        proven, key=incumbent_rank, reverse=True)[:ACTIVE_EFFECTIVE_INCUMBENT_LIMIT]
    remaining = [key for key in inventory if key not in incumbents]

    def challenger_rank(effective_key: str):
        record = evidence.get(effective_key) or {}
        return (
            int(record.get("trials", 0)),
            int(record.get("retained", 0)),
            -_group_prior(teacher, grade, inventory[effective_key]),
            effective_key,
        )

    slots = ACTIVE_EFFECTIVE_STRATEGY_LIMIT - len(incumbents)
    challengers = sorted(remaining, key=challenger_rank)[:slots]
    return tuple((*incumbents, *challengers)), inventory


def pick_existing_active(engine, teacher: dict, grade: str, rng,
                         active_effective: tuple[str, ...],
                         inventory: dict[str, list[str]]):
    """Consult inherited UCB ranking without growing the strategy archive."""
    allowed = {
        policy_key
        for effective_key in active_effective
        for policy_key in inventory[effective_key]
    }
    strategies = teacher.get("strategies", {})
    picker = getattr(engine, "pick_existing", None)
    if picker is not None:
        return picker(teacher, grade, rng, exclude=set(strategies) - allowed)
    if allowed == set(strategies):
        return engine.pick(teacher, grade, rng)
    local = teacher.get("grade_stats", {}).get(str(grade), {})
    total = int(teacher.get("events", 0)) + 1

    def rank(policy_key: str):
        info = local.get(policy_key) or teacher.get("global_stats", {}).get(policy_key, {})
        trials = int(info.get("trials", 0))
        if trials == 0:
            return 10 + rng.random()
        exploitation = float(info.get("reward_sum", 0.)) / trials
        exploration = UCB_EXPLORATION_WEIGHT * math.sqrt(
            math.log(total + 2) / (1 + trials))
        return exploitation + exploration

    policy_key = max(sorted(allowed), key=rank)
    return policy_key, strategies[policy_key]
