"""Evidence-seeded teacher-policy breeding for sustained rejection pressure."""
from __future__ import annotations

import hashlib
import json
import math

from .teacher_strategy_population import (
    active_effective_strategy_keys, checkpoint_active_effective_strategy_keys,
    effective_policy_features, effective_policy_key, effective_strategy_inventory,
    historical_policy_mean,
)


UNPROVEN_BESPOKE_PER_CAPABILITY = 8
_INEFFECTIVE_MUTATION_FIELDS = frozenset({"preview"})
_ADAPTIVE_NUMERIC_FIELDS = ("old", "lr", "distill")
_ADAPTIVE_OLD_RESOLUTION = 1
_ADAPTIVE_LR_RESOLUTION = 0.000001
_ADAPTIVE_DISTILL_RESOLUTION = 0.01


def _numeric_scope_family(scope: str) -> str | None:
    """Return the stable release family for a numeric-scope revision."""
    if not isinstance(scope, str):
        return None
    family, separator, leaf = scope.rpartition("/")
    return family if separator and family and leaf.isdigit() else None


def portable_retained_challenger(teacher: dict, *, capability: str, phase: str,
                                 curriculum_scope: str):
    """Retry one proven same-capability policy after a numeric scope revision.

    Prior-scope reward remains prior-scope evidence. This helper uses retention
    only to prioritize one fresh trial in the new scope; it never copies the old
    contextual record forward.
    """
    family = _numeric_scope_family(curriculum_scope)
    if family is None:
        return None
    channel = teacher.get("causal_experiment", {})
    strategies = teacher.get("strategies", {})
    inventory = effective_strategy_inventory(teacher)
    live = set(channel.get("live_effective_strategies", inventory))
    current = channel.get("contexts", {}).get(
        capability + "|" + phase + "|" + curriculum_scope, {})
    tried = {
        effective_policy_key(strategies[key])
        for key in current if key in strategies
    }
    candidates = {}
    for context_key, records in channel.get("contexts", {}).items():
        try:
            context_capability, _context_phase, context_scope = context_key.split("|", 2)
        except ValueError:
            continue
        if (context_capability != capability or context_scope == curriculum_scope or
                _numeric_scope_family(context_scope) != family or
                not isinstance(records, dict)):
            continue
        for policy_key, record in records.items():
            policy = strategies.get(policy_key)
            if policy is None or not isinstance(record, dict):
                continue
            retained = int(record.get("retained", 0))
            trials = int(record.get("trials", 0))
            if retained < 1 or trials < retained:
                continue
            effective = effective_policy_key(policy)
            if effective not in live or effective in tried:
                continue
            target = candidates.setdefault(effective, {
                "retained": 0, "trials": 0, "reward_sum": 0.,
                "members": [], "source_scopes": set(),
            })
            target["retained"] += retained
            target["trials"] += trials
            target["reward_sum"] += float(record.get("reward_sum", 0.))
            target["members"].append(policy_key)
            target["source_scopes"].add(context_scope)
    if not candidates:
        return None

    def rank(item):
        effective, record = item
        return (
            record["retained"] / record["trials"], record["retained"],
            record["reward_sum"] / record["trials"], record["trials"], effective,
        )

    effective, record = max(candidates.items(), key=rank)
    member = max(
        record["members"],
        key=lambda key: (
            int(teacher.get("global_stats", {}).get(key, {}).get("trials", 0)), key))
    return member, strategies[member], {
        "portable_effective_policy_key": effective,
        "portable_prior_retained": record["retained"],
        "portable_prior_trials": record["trials"],
        "portable_source_scopes": sorted(record["source_scopes"]),
    }


def pressure_challenger(engine, teacher: dict, rng, *, capability: str, phase: str,
                        curriculum_scope: str, diagnostic_key: str | None,
                        total_capabilities: int):
    portable = portable_retained_challenger(
        teacher, capability=capability, phase=phase,
        curriculum_scope=curriculum_scope)
    if portable is not None:
        return (*portable[:2], "PORTABLE_RETAINED_CHALLENGER", portable[2])
    novel = mint_bespoke_effective_strategy(
        engine, teacher, rng, capability=capability,
        curriculum_scope=curriculum_scope, diagnostic_key=diagnostic_key,
        total_capabilities=total_capabilities)
    return ((*novel[:2], "FRESH_MUTATED_CHALLENGER", novel[2])
            if novel is not None else None)


def selection_population(teacher: dict, *, grade: str, capability: str,
                         curriculum_scope: str, scope: dict, channel: dict,
                         context_key: str, student_checkpoint_sha256: str | None,
                         total_capabilities: int | None):
    active, inventory = active_effective_strategy_keys(
        teacher, grade, scope, total_capabilities=total_capabilities)
    active = filter_active_effective(
        teacher, grade=grade, capability=capability,
        curriculum_scope=curriculum_scope, active_effective=active,
        inventory=inventory)
    active, retired = checkpoint_active_effective_strategy_keys(
        teacher, grade, scope, channel, context_key, active, inventory,
        student_checkpoint_sha256)
    return active, inventory, retired


def selection_metadata(teacher: dict, *, channel: dict, inventory: dict,
                       active_effective, checkpoint_retired,
                       total_capabilities: int | None,
                       diagnostic_context_consumed: bool,
                       diagnostic_context_key: str | None,
                       selection_reason: str, selection_policy: str,
                       selection_detail: dict | None = None) -> dict:
    live = channel.get("live_effective_strategies")
    live_count = len(live) if isinstance(live, list) else len(inventory)
    result = {
        "diagnostic_context_consumed": diagnostic_context_consumed,
        "diagnostic_context_key": diagnostic_context_key,
        "selection_reason": selection_reason, "selection_policy": selection_policy,
        "active_effective_strategy_count": len(active_effective),
        "dormant_effective_strategy_count": live_count - len(active_effective),
        "live_effective_strategy_count": live_count,
        "retired_effective_strategy_count": len(channel.get("retired_effective_strategies", ())),
        "strategy_archive_count": len(teacher.get("strategies", {})),
        "realized_action_ecology_count": len(
            channel.get("realized_action_ecology", {})),
        "checkpoint_retired_effective_strategy_count": len(checkpoint_retired),
    }
    if total_capabilities is not None:
        from .teacher_population_control import population_limits
        limits = population_limits(total_capabilities)
        result.update(strategy_population_capacity=limits.max_effective,
                      active_effective_strategy_capacity=limits.active_effective)
    if selection_detail:
        result.update(selection_detail)
    return result


def _record_rank(record: dict) -> tuple[float, float, int]:
    trials = int(record.get("trials", 0))
    retained = int(record.get("retained", 0))
    reward_sum = float(record.get("reward_sum", 0.))
    return (retained / trials if trials else 0.,
            reward_sum / trials if trials else float("-inf"), trials)


def _birth_novelty(teacher: dict, policy_key: str) -> tuple[int, int]:
    policy = teacher.get("strategies", {}).get(policy_key)
    if policy is None:
        return (0, 0)
    birth = teacher.get("causal_experiment", {}).get(
        "strategy_births", {}).get(effective_policy_key(policy), {})
    if not isinstance(birth, dict):
        return (0, 0)
    return (
        int(birth.get("retained_novel_realized_action_count", 0)),
        int(birth.get("novel_realized_action_count", 0)),
    )


def _retained_parent_candidates(teacher: dict, capability: str,
                                curriculum_scope: str,
                                diagnostic_key: str | None):
    strategies = teacher.get("strategies", {})
    channel = teacher.get("causal_experiment", {})
    contexts = channel.get("contexts", {})
    grade = capability.partition(".")[0]
    levels = (
        ("CAPABILITY_DIAGNOSTIC_RETAINED", True, True),
        ("CAPABILITY_RETAINED", True, False),
        ("GRADE_DIAGNOSTIC_RETAINED", False, True),
        ("GRADE_RETAINED", False, False),
    )
    for basis, exact_capability, diagnostic_only in levels:
        candidates = []
        for context_key, scope in contexts.items():
            try:
                context_capability, _phase, context_scope = context_key.split("|", 2)
            except ValueError:
                continue
            if context_scope != curriculum_scope:
                continue
            if exact_capability:
                if context_capability != capability:
                    continue
            elif context_capability.partition(".")[0] != grade:
                continue
            for policy_key, record in scope.items():
                if policy_key not in strategies or not isinstance(record, dict):
                    continue
                evidence = record
                if diagnostic_only:
                    evidence = record.get("diagnostic_stats", {}).get(diagnostic_key)
                    if not isinstance(evidence, dict):
                        continue
                if int(evidence.get("retained", 0)) < 1:
                    continue
                candidates.append((
                    _record_rank(evidence), _birth_novelty(teacher, policy_key),
                    policy_key))
        if candidates:
            for _rank, _novelty, policy_key in sorted(candidates, reverse=True):
                yield policy_key, basis

    local = teacher.get("grade_stats", {}).get(grade, {})
    grade_candidates = [
        (historical_policy_mean(teacher, grade, key), key)
        for key, info in local.items()
        if key in strategies and isinstance(info, dict) and int(info.get("trials", 0)) > 0
    ]
    for _score, policy_key in sorted(grade_candidates, reverse=True):
        yield policy_key, "GRADE_REWARD_FALLBACK"
    global_candidates = [
        (float(info.get("reward_ema", 0.)), key)
        for key, info in teacher.get("global_stats", {}).items()
        if key in strategies and isinstance(info, dict) and int(info.get("trials", 0)) > 0
    ]
    for _score, policy_key in sorted(global_candidates, reverse=True):
        yield policy_key, "GLOBAL_REWARD_FALLBACK"


def _one_knob_children(base: dict, knobs: dict, rng):
    fields = [field for field in knobs if field not in _INEFFECTIVE_MUTATION_FIELDS]
    rng.shuffle(fields)
    for field in fields:
        values = [value for value in knobs[field] if value != base.get(field)]
        rng.shuffle(values)
        for value in values:
            child = dict(base)
            child[field] = value
            yield field, child


def _quantized_midpoint(field: str, left: float, right: float):
    if field == "lr":
        value = math.sqrt(left * right)
    else:
        value = (left + right) / 2
    resolution = (_ADAPTIVE_OLD_RESOLUTION if field == "old" else
                  _ADAPTIVE_LR_RESOLUTION if field == "lr" else
                  _ADAPTIVE_DISTILL_RESOLUTION)
    value = round(value / resolution) * resolution
    if field == "old":
        return int(round(value))
    decimals = 6 if field == "lr" else 2
    return round(value, decimals)


def _adaptive_numeric_children(base: dict, strategies: dict,
                               knobs: dict, rng):
    """Bisect one local numeric gap without leaving the historical envelope."""
    fields = [field for field in _ADAPTIVE_NUMERIC_FIELDS
              if field in knobs and field in base]
    rng.shuffle(fields)
    for field in fields:
        allowed = tuple(knobs[field])
        if not allowed or any(not isinstance(value, (int, float)) for value in allowed):
            continue
        lower_bound = float(min(allowed))
        upper_bound = float(max(allowed))
        base_value = float(base[field])
        observed = sorted({
            float(policy[field]) for policy in strategies.values()
            if isinstance(policy, dict) and isinstance(policy.get(field), (int, float))
            and lower_bound <= float(policy[field]) <= upper_bound
        })
        neighbors = []
        lower = [value for value in observed if value < base_value]
        upper = [value for value in observed if value > base_value]
        if lower:
            neighbors.append(max(lower))
        if upper:
            neighbors.append(min(upper))
        rng.shuffle(neighbors)
        for neighbor in neighbors:
            value = _quantized_midpoint(field, base_value, neighbor)
            numeric = float(value)
            if (numeric <= lower_bound or numeric >= upper_bound or
                    numeric == base_value or numeric == neighbor or
                    numeric in observed):
                continue
            child = dict(base)
            child[field] = value
            yield field, child


def _register_child(teacher: dict, child: dict, *, effective: str,
                    parent_key: str, parent: dict, basis: str,
                    field: str, capability: str, curriculum_scope: str,
                    total_capabilities: int, mutation_mode: str):
    strategies = teacher["strategies"]
    identity = hashlib.sha256(
        json.dumps(child, sort_keys=True).encode()).hexdigest()[:12]
    if identity in strategies:
        return None
    strategies[identity] = child
    teacher.setdefault("global_stats", {})[identity] = {
        "trials": 0, "reward_sum": 0.0, "reward_ema": 0.0, "latest": None,
    }
    teacher["mutations"] = int(teacher.get("mutations", 0)) + 1
    channel = teacher.setdefault("causal_experiment", {})
    channel.setdefault("strategy_births", {})[effective] = {
        "origin_capability": capability,
        "origin_grade": capability.partition(".")[0],
        "curriculum_scope": curriculum_scope,
        "parent_policy_key": parent_key,
        "parent_effective_policy_key": effective_policy_key(parent),
        "parent_basis": basis,
        "changed_fields": [field],
        "mutation_mode": mutation_mode,
        "birth_event": int(channel.get("events", 0)) + 1,
        "proven_retained": False,
    }
    from .teacher_population_control import rebalance_live_population
    rebalance_live_population(teacher, total_capabilities=total_capabilities)
    return identity, child, {
        "mutation_parent_policy_key": parent_key,
        "mutation_parent_basis": basis,
        "mutation_changed_fields": [field],
        "mutation_mode": mutation_mode,
    }


def mint_bespoke_effective_strategy(engine, teacher: dict, rng, *,
                                    capability: str, curriculum_scope: str,
                                    diagnostic_key: str | None = None,
                                    total_capabilities: int = 1):
    """Breed one novel effective policy from retained capability/grade ancestry."""
    strategies = teacher.get("strategies", {})
    knobs = getattr(engine, "KNOBS", None)
    if not knobs:
        return None
    existing = set(effective_strategy_inventory(teacher))
    max_context = int(getattr(engine, "MAX_TEACHER_CONTEXT_ITEMS", 24))
    seen_parents = set()
    parents = []
    for parent_key, basis in _retained_parent_candidates(
            teacher, capability, curriculum_scope, diagnostic_key):
        if parent_key in seen_parents:
            continue
        seen_parents.add(parent_key)
        parent = strategies[parent_key]
        if any(field not in parent for field in knobs):
            continue
        parents.append((parent_key, basis, parent))
    for mutation_mode, children in (
            ("LEGACY_GRID", lambda parent: _one_knob_children(parent, knobs, rng)),
            ("ADAPTIVE_LOCAL_REFINEMENT",
             lambda parent: _adaptive_numeric_children(parent, strategies, knobs, rng))):
        for parent_key, basis, parent in parents:
            for field, child in children(parent):
                if child["old"] + child["preview"] > max_context:
                    continue
                effective = effective_policy_key(child)
                if effective in existing:
                    continue
                registered = _register_child(
                    teacher, child, effective=effective, parent_key=parent_key,
                    parent=parent, basis=basis, field=field,
                    capability=capability, curriculum_scope=curriculum_scope,
                    total_capabilities=total_capabilities,
                    mutation_mode=mutation_mode)
                if registered is not None:
                    return registered
    return None


def mark_bespoke_retained(channel: dict, effective_key: str, *,
                          capability: str, curriculum_scope: str) -> None:
    birth = channel.get("strategy_births", {}).get(effective_key)
    if not isinstance(birth, dict):
        return
    if (birth.get("origin_capability") == capability and
            birth.get("curriculum_scope") == curriculum_scope):
        birth["proven_retained"] = True


def record_policy_outcome_side_effects(channel: dict, effective_key: str, *,
                                       capability: str, curriculum_scope: str,
                                       retained: bool,
                                       realized_action_key: str | None = None) -> None:
    from .teacher_population_control import record_strategy_usage
    record_strategy_usage(channel, effective_key)
    if realized_action_key is not None:
        ecology = channel.setdefault("realized_action_ecology", {})
        novel = realized_action_key not in ecology
        record = ecology.setdefault(realized_action_key, {
            "trials": 0, "retained": 0,
            "first_event": int(channel.get("events", 0)) + 1,
            "last_event": int(channel.get("events", 0)) + 1,
            "effective_policy_keys": [],
        })
        record["trials"] += 1
        record["retained"] += int(retained)
        record["last_event"] = int(channel.get("events", 0)) + 1
        if effective_key not in record["effective_policy_keys"]:
            record["effective_policy_keys"].append(effective_key)
            record["effective_policy_keys"].sort()
        birth = channel.get("strategy_births", {}).get(effective_key)
        if isinstance(birth, dict):
            actions = birth.setdefault("realized_action_keys", [])
            if realized_action_key not in actions:
                actions.append(realized_action_key)
            if novel:
                birth["novel_realized_action_count"] = int(
                    birth.get("novel_realized_action_count", 0)) + 1
                if retained:
                    birth["retained_novel_realized_action_count"] = int(
                        birth.get("retained_novel_realized_action_count", 0)) + 1
    if retained:
        mark_bespoke_retained(
            channel, effective_key, capability=capability,
            curriculum_scope=curriculum_scope)


def filter_active_effective(teacher: dict, *, grade: str, capability: str,
                            curriculum_scope: str, active_effective,
                            inventory):
    """Keep newborn bespoke policies local until retention proves them."""
    births = teacher.get("causal_experiment", {}).get("strategy_births", {})
    local_unproven = sorted(
        ((int(birth.get("birth_event", 0)), key)
         for key, birth in births.items()
         if isinstance(birth, dict) and not birth.get("proven_retained") and
         birth.get("origin_capability") == capability and
         birth.get("curriculum_scope") == curriculum_scope),
        reverse=True)
    current_unproven = {key for _, key in local_unproven[:UNPROVEN_BESPOKE_PER_CAPABILITY]}

    def allowed(key):
        birth = births.get(key)
        if not isinstance(birth, dict):
            return True
        if birth.get("proven_retained"):
            return birth.get("origin_grade") == grade
        if birth.get("curriculum_scope") != curriculum_scope:
            return False
        return (birth.get("origin_capability") == capability and
                key in current_unproven)

    live = set(teacher.get("causal_experiment", {}).get(
        "live_effective_strategies", inventory))
    eligible = [key for key in active_effective if key in live and allowed(key)]
    for key in sorted(live):
        if len(eligible) >= len(active_effective):
            break
        if key in inventory and key not in eligible and allowed(key):
            eligible.append(key)
    return tuple(eligible)
