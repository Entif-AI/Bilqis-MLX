"""Inherited UCB selection over the active effective teacher population."""
from __future__ import annotations

import math

from .population import BAMF_SUCCESSOR_SELECTION, UCB_EXPLORATION_WEIGHT

def pick_existing_active(engine, teacher: dict, grade: str, rng,
                         active_effective: tuple[str, ...],
                         inventory: dict[str, list[str]]):
    """Consult inherited UCB ranking without growing the strategy archive."""
    allowed = {
        policy_key
        for effective_key in active_effective
        for policy_key in inventory[effective_key]
    }
    if teacher.get("selection_contract") == BAMF_SUCCESSOR_SELECTION:
        teacher = {**teacher, "grade_stats": {}}
        grade = ""
    strategies = teacher.get("strategies", {})
    picker = getattr(engine, "pick_existing", None)
    if picker is not None:
        return picker(teacher, grade, rng, exclude=set(strategies) - allowed)
    if allowed == set(strategies):
        return engine.pick(teacher, grade, rng)
    local = {} if teacher.get("selection_contract") == BAMF_SUCCESSOR_SELECTION else teacher.get("grade_stats", {}).get(str(grade), {})
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
