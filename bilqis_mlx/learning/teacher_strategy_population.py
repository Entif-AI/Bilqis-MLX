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


def _validated_student_checkpoint(student_checkpoint_sha256: str | None) -> str | None:
    if student_checkpoint_sha256 is None:
        return None
    if (not isinstance(student_checkpoint_sha256, str) or
            len(student_checkpoint_sha256) != STUDENT_SHA256_HEX_LENGTH or
            any(char not in "0123456789abcdef" for char in student_checkpoint_sha256)):
        raise ValueError(LearningExperimentError.STUDENT_CHECKPOINT_INVALID.value)
    return student_checkpoint_sha256


def _context_parts(context_key: str) -> tuple[str, str, str]:
    parts = context_key.split("|", 2)
    if len(parts) != CONTEXT_PART_COUNT or not parts[0]:
        raise ValueError(LearningExperimentError.STUDENT_POLICY_FAILURE_INVALID.value)
    return parts[0], parts[1], parts[2]


def _capability_attempts(channel: dict, capability: str, curriculum_scope: str) -> int:
    record = channel.get("capability_stagnation", {}).get(
        capability + "|" + curriculum_scope, {})
    return int(record.get("total_rejections", 0)) + int(record.get("total_retained", 0))


def _cooldown_bucket(channel: dict, capability: str, curriculum_scope: str,
                     *, create: bool = False) -> dict:
    all_cooldowns = channel.setdefault("policy_cooldowns", {}) if create else channel.get("policy_cooldowns", {})
    key = capability + "|" + curriculum_scope
    if create:
        return all_cooldowns.setdefault(key, {})
    bucket = all_cooldowns.get(key, {})
    return bucket if isinstance(bucket, dict) else {}


def durable_policy_cooldown_status(channel: dict, capability: str,
                                   curriculum_scope: str,
                                   effective_policy_key: str) -> dict:
    bucket = _cooldown_bucket(channel, capability, curriculum_scope)
    record = bucket.get(effective_policy_key)
    if not isinstance(record, dict):
        return {"active": False, "failed_student_epochs": 0,
                "remaining_capability_visits": 0}
    attempts = _capability_attempts(channel, capability, curriculum_scope)
    until = int(record.get("cooldown_until_attempt", 0))
    failed = list(record.get("failed_student_sha256", ()))
    if until and attempts >= until:
        # Expiry decays one epoch of bad evidence rather than granting amnesia.
        record["failed_student_sha256"] = failed[-1:]
        record.pop("cooldown_until_attempt", None)
        until = 0
        failed = record["failed_student_sha256"]
    active = until > attempts
    return {
        "active": active,
        "status": "SEARCH_NEIGHBORHOOD_EXHAUSTED" if active else None,
        "failed_student_epochs": len(failed),
        "remaining_capability_visits": max(0, until - attempts),
    }


def durable_cooled_effective_keys(channel: dict, capability: str,
                                  curriculum_scope: str) -> set[str]:
    return {
        key for key in _cooldown_bucket(channel, capability, curriculum_scope)
        if durable_policy_cooldown_status(
            channel, capability, curriculum_scope, key)["active"]
    }


def sibling_cooldown_penalty(channel: dict, capability: str,
                             curriculum_scope: str,
                             effective_policy_key: str) -> float:
    if channel.get("selection_contract") == BAMF_SUCCESSOR_SELECTION:
        # No source-qualified sibling relation is supplied at this boundary.
        return 0.
    grade = capability.partition(".")[0]
    siblings = 0
    for bucket_key in channel.get("policy_cooldowns", {}):
        sibling, separator, scope = bucket_key.partition("|")
        if (not separator or sibling == capability or scope != curriculum_scope or
                sibling.partition(".")[0] != grade):
            continue
        if durable_policy_cooldown_status(
                channel, sibling, scope, effective_policy_key)["active"]:
            siblings += 1
    return min(.05, siblings * SIBLING_COOLDOWN_PENALTY)


def _record_durable_capability_outcome(
        channel: dict, context_key: str, effective_policy_key: str,
        checkpoint: str, *, same_student_unretained: int, retained: bool) -> None:
    capability, _phase, curriculum_scope = _context_parts(context_key)
    bucket = _cooldown_bucket(channel, capability, curriculum_scope, create=True)
    if retained:
        bucket.pop(effective_policy_key, None)
        return
    if same_student_unretained < SAME_STUDENT_POLICY_UNRETAINED_LIMIT:
        return
    record = bucket.setdefault(effective_policy_key, {
        "failed_student_sha256": [],
    })
    failed = record.setdefault("failed_student_sha256", [])
    if checkpoint in failed:
        return
    failed.append(checkpoint)
    del failed[:-MAX_FAILED_STUDENT_EPOCHS]
    if len(failed) >= DURABLE_POLICY_FAILED_STUDENT_LIMIT:
        attempts = _capability_attempts(channel, capability, curriculum_scope)
        record["cooldown_until_attempt"] = (
            attempts + DURABLE_POLICY_COOLDOWN_CAPABILITY_VISITS)


def _checkpoint_policy_no_gain_streaks(channel: dict, context_key: str,
                                       student_checkpoint_sha256: str | None) -> dict:
    checkpoint = _validated_student_checkpoint(student_checkpoint_sha256)
    if checkpoint is None:
        return {}
    epoch = channel.get("student_policy_epoch")
    if not isinstance(epoch, dict) or epoch.get("student_sha256") != checkpoint:
        return {}
    if not isinstance(epoch.get("contexts"), dict):
        raise ValueError(LearningExperimentError.STUDENT_POLICY_EPOCH_INVALID.value)
    failures = epoch["contexts"].get(context_key, {})
    if (not isinstance(failures, dict) or any(
            not isinstance(key, str) or type(value) is not int or value < 0
            for key, value in failures.items())):
        raise ValueError(LearningExperimentError.STUDENT_POLICY_FAILURE_INVALID.value)
    return failures


def record_checkpoint_policy_outcome(
        channel: dict, context_key: str, effective_policy_key: str,
        student_checkpoint_sha256: str | None, *, no_target_gain: bool,
        retained: bool) -> None:
    checkpoint = _validated_student_checkpoint(student_checkpoint_sha256)
    if checkpoint is None:
        return
    epoch = channel.get("student_policy_epoch")
    if not isinstance(epoch, dict) or epoch.get("student_sha256") != checkpoint:
        epoch = {
            "student_sha256": checkpoint,
            "contexts": {},
            "unretained_contexts": {},
        }
        channel["student_policy_epoch"] = epoch
    if (not isinstance(epoch.get("contexts"), dict) or
            not isinstance(epoch.setdefault("unretained_contexts", {}), dict)):
        raise ValueError(LearningExperimentError.STUDENT_POLICY_EPOCH_INVALID.value)
    streaks = epoch["contexts"].setdefault(context_key, {})
    if no_target_gain:
        streaks[effective_policy_key] = streaks.get(effective_policy_key, 0) + 1
    else:
        streaks.pop(effective_policy_key, None)

    unretained = epoch["unretained_contexts"].setdefault(context_key, {})
    if retained:
        unretained.pop(effective_policy_key, None)
    else:
        unretained[effective_policy_key] = unretained.get(effective_policy_key, 0) + 1
    _record_durable_capability_outcome(
        channel, context_key, effective_policy_key, checkpoint,
        same_student_unretained=unretained.get(effective_policy_key, 0),
        retained=retained)


def checkpoint_active_effective_strategy_keys(
        teacher: dict, grade: str, scope: dict, channel: dict,
        context_key: str, active_effective: tuple[str, ...],
        inventory: dict[str, list[str]],
        student_checkpoint_sha256: str | None) -> tuple[tuple[str, ...], set[str]]:
    checkpoint_failures = _checkpoint_policy_no_gain_streaks(
        channel, context_key, student_checkpoint_sha256)
    checkpoint = _validated_student_checkpoint(student_checkpoint_sha256)
    unretained_failures = {}
    if checkpoint is not None:
        epoch = channel.get("student_policy_epoch")
        if isinstance(epoch, dict) and epoch.get("student_sha256") == checkpoint:
            unretained_contexts = epoch.get("unretained_contexts", {})
            if not isinstance(unretained_contexts, dict):
                raise ValueError(LearningExperimentError.STUDENT_POLICY_EPOCH_INVALID.value)
            unretained_failures = unretained_contexts.get(context_key, {})
            if (not isinstance(unretained_failures, dict) or any(
                    not isinstance(key, str) or type(value) is not int or value < 0
                    for key, value in unretained_failures.items())):
                raise ValueError(LearningExperimentError.STUDENT_POLICY_FAILURE_INVALID.value)
    capability, _phase, curriculum_scope = _context_parts(context_key)
    durable_retired = durable_cooled_effective_keys(
        channel, capability, curriculum_scope)
    retired = durable_retired | {
        key for key in set(checkpoint_failures) | set(unretained_failures)
        if (checkpoint_failures.get(key, 0) >= SAME_STUDENT_POLICY_NO_TARGET_GAIN_LIMIT or
            unretained_failures.get(key, 0) >= SAME_STUDENT_POLICY_UNRETAINED_LIMIT)
    }
    if not retired:
        return active_effective, retired
    evidence = effective_context_scope(teacher, scope) if scope else {}
    eligible = [key for key in active_effective if key not in retired]
    replacements = [
        key for key in inventory if key not in retired and key not in eligible
    ]

    def replacement_rank(key):
        record = evidence.get(key) or {}
        members = inventory[key]
        return (
            int(record.get("trials", 0)),
            int(record.get("retained", 0)),
            -sum(historical_policy_mean(teacher, grade, member)
                 for member in members) / len(members),
            key,
        )

    replacements.sort(key=replacement_rank)
    eligible.extend(replacements[:max(0, len(active_effective) - len(eligible))])
    if not eligible:
        eligible = [min(
            inventory, key=lambda key: (checkpoint_failures.get(key, 0), key))]
    return tuple(eligible), retired


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
