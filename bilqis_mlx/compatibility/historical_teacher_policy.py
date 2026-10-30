"""Torch-free projection of the historical teacher's pure bandit policy.

The legacy bilqis_school.engine module couples these small policy functions
to the retired PyTorch training stack at import time. The MLX runtime only
needs pick and observe, with mutate behind pick, so keep that behavior in a
stdlib-only compatibility surface.
"""
from __future__ import annotations

import hashlib
import json
import math
from types import MappingProxyType


KNOBS = MappingProxyType({
    "old": [4, 8, 12, 16, 20],
    "preview": [0, 2, 4],
    "depth": [1, 2, 3, 4],
    "contrast": [0.0, 0.5, 1.0],
    "lr": [0.00004, 0.00008, 0.00013, 0.0002, 0.0003],
    "distill": [0.0, 0.15, 0.35, 0.65],
})
MAX_STRATEGIES = 512
MAX_MUTATION_ATTEMPTS = 24
MAX_TEACHER_CONTEXT_ITEMS = 24
MUTATION_EVENT_INTERVAL = 3

# Legacy exception identities are part of the historical teacher contract.
NONFINITE_TEACHER_REWARD_ERROR = "NONFINITE_TEACHER_REWARD"
NO_UNTRIED_TEACHER_STRATEGY_ERROR = "NO_UNTRIED_TEACHER_STRATEGY_FOR_GRADE_ATTEMPT"


def _policy_key(policy):
    return hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()[:12]


def _stats():
    return {"trials": 0, "reward_sum": 0.0, "reward_ema": 0.0, "latest": None}


def mutate(teacher, rng):
    if len(teacher["strategies"]) >= MAX_STRATEGIES:
        return None
    viable = [(key, info) for key, info in teacher["global_stats"].items()
              if info["trials"]]
    base = (teacher["strategies"][max(viable, key=lambda v: v[1]["reward_ema"])[0]]
            if viable else rng.choice(list(teacher["strategies"].values())))
    for _ in range(MAX_MUTATION_ATTEMPTS):
        variant = dict(base)
        field = rng.choice(list(KNOBS))
        candidates = [value for value in KNOBS[field] if value != variant[field]]
        variant[field] = rng.choice(candidates)
        if variant["old"] + variant["preview"] > MAX_TEACHER_CONTEXT_ITEMS:
            continue
        identity = _policy_key(variant)
        if identity not in teacher["strategies"]:
            teacher["strategies"][identity] = variant
            teacher["global_stats"][identity] = _stats()
            teacher["mutations"] += 1
            return identity
    return None


def pick_existing(teacher, grade, rng, exclude=None):
    """Pick from the existing archive without growing the strategy inventory."""
    local = teacher["grade_stats"].get(str(grade), {})
    total = teacher["events"] + 1
    excluded = set(exclude or ())

    def rank(item):
        key, _policy = item
        info = local.get(key) or teacher["global_stats"][key]
        if info["trials"] == 0:
            return 10 + rng.random()
        exploitation = info["reward_sum"] / info["trials"]
        exploration = 0.6 * math.sqrt(math.log(total + 2) / (1 + info["trials"]))
        return exploitation + exploration

    choices = [
        item for item in teacher["strategies"].items()
        if item[0] not in excluded
    ]
    if not choices:
        raise ValueError(NO_UNTRIED_TEACHER_STRATEGY_ERROR)
    return max(choices, key=rank)


def pick(teacher, grade, rng, exclude=None):
    if teacher["events"] and teacher["events"] % MUTATION_EVENT_INTERVAL == 0:
        mutate(teacher, rng)
    return pick_existing(teacher, grade, rng, exclude=exclude)


def observe(teacher, grade, policy_key, reward):
    if not math.isfinite(reward):
        raise ValueError(NONFINITE_TEACHER_REWARD_ERROR)
    for entry in (
        teacher["global_stats"][policy_key],
        teacher["grade_stats"].setdefault(str(grade), {}).setdefault(policy_key, _stats()),
    ):
        entry["trials"] += 1
        entry["reward_sum"] += reward
        entry["reward_ema"] = (
            reward if entry["latest"] is None
            else 0.8 * entry["reward_ema"] + 0.2 * reward
        )
        entry["latest"] = reward
    teacher["events"] += 1
