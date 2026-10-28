"""Scale and recycle the live teacher strategy population with curriculum size."""
from __future__ import annotations

from dataclasses import dataclass
from .teacher_feedback import LearningExperimentError


MIN_LIVE_EFFECTIVE = 48
LIVE_EFFECTIVE_PER_CAPABILITY = 24
MIN_ACTIVE_EFFECTIVE = 8
ACTIVE_EFFECTIVE_PER_CAPABILITY = 2
NEWBORN_GRACE_TRIALS = 4


@dataclass(frozen=True)
class PopulationLimits:
    max_effective: int
    active_effective: int


def population_limits(total_capabilities: int) -> PopulationLimits:
    if type(total_capabilities) is not int or total_capabilities < 1:
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    maximum = max(MIN_LIVE_EFFECTIVE,
                  LIVE_EFFECTIVE_PER_CAPABILITY * total_capabilities)
    active = min(maximum, max(
        MIN_ACTIVE_EFFECTIVE,
        ACTIVE_EFFECTIVE_PER_CAPABILITY * total_capabilities))
    return PopulationLimits(maximum, active)


def _evidence(teacher: dict, inventory: dict[str, list[str]]) -> dict[str, dict]:
    from .teacher_strategy_population import effective_policy_key

    strategies = teacher.get("strategies", {})
    evidence = {
        key: {"trials": 0, "retained": 0, "reward_sum": 0.}
        for key in inventory
    }
    for scope in teacher.get("causal_experiment", {}).get("contexts", {}).values():
        if not isinstance(scope, dict):
            continue
        for policy_key, record in scope.items():
            policy = strategies.get(policy_key)
            if policy is None or not isinstance(record, dict):
                continue
            effective = effective_policy_key(policy)
            target = evidence.setdefault(
                effective, {"trials": 0, "retained": 0, "reward_sum": 0.})
            target["trials"] += int(record.get("trials", 0))
            target["retained"] += int(record.get("retained", 0))
            target["reward_sum"] += float(record.get("reward_sum", 0.))
    return evidence


def _global_prior(teacher: dict, members: list[str]) -> float:
    weighted = []
    for member in members:
        info = teacher.get("global_stats", {}).get(member)
        if not isinstance(info, dict) or not int(info.get("trials", 0)):
            continue
        weighted.append(float(info.get("reward_sum", 0.)) /
                        int(info["trials"]))
    return sum(weighted) / len(weighted) if weighted else 0.


def _keep_rank(teacher: dict, effective: str, members: list[str], record: dict):
    channel = teacher.get("causal_experiment", {})
    birth = channel.get("strategy_births", {}).get(effective) or {}
    usage = channel.get("strategy_usage", {}).get(effective) or {}
    trials = int(record.get("trials", 0))
    retained = int(record.get("retained", 0))
    reward_sum = float(record.get("reward_sum", 0.))
    rate = retained / trials if trials else 0.
    mean = reward_sum / trials if trials else _global_prior(teacher, members)
    newborn_grace = bool(
        birth and not birth.get("proven_retained") and trials < NEWBORN_GRACE_TRIALS)
    return (
        1 if newborn_grace else 0,
        retained,
        rate,
        mean,
        int(usage.get("last_event", 0)),
        int(birth.get("birth_event", 0)),
        trials,
        effective,
    )


def rebalance_live_population(teacher: dict, *, total_capabilities: int,
                              max_effective_override: int | None = None
                              ) -> tuple[str, ...]:
    """Retire weak/old effective strategies from live selection, preserving history."""
    from .teacher_strategy_population import effective_strategy_inventory

    inventory = effective_strategy_inventory(teacher)
    limits = population_limits(total_capabilities)
    capacity = limits.max_effective if max_effective_override is None else int(max_effective_override)
    if capacity < 1:
        raise ValueError(LearningExperimentError.POLICY_INVALID.value)
    evidence = _evidence(teacher, inventory)
    ranked = sorted(
        inventory,
        key=lambda key: _keep_rank(teacher, key, inventory[key], evidence[key]),
        reverse=True)
    live = tuple(sorted(ranked[:capacity]))
    retired = tuple(sorted(set(inventory) - set(live)))
    channel = teacher.setdefault("causal_experiment", {})
    channel["live_effective_strategies"] = list(live)
    channel["retired_effective_strategies"] = list(retired)
    channel["strategy_population_limits"] = {
        "total_capabilities": total_capabilities,
        "max_effective": limits.max_effective,
        "active_effective": limits.active_effective,
    }
    return live


def record_strategy_usage(channel: dict, effective_key: str) -> None:
    usage = channel.setdefault("strategy_usage", {}).setdefault(effective_key, {})
    usage["last_event"] = int(channel.get("events", 0)) + 1
