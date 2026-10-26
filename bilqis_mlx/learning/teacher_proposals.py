"""Shadow proposal families and posterior acquisition for Teacher vNext.

This module is deliberately neural-inert. It can propose interventions that are not
present in the historical strategy archive, but it never trains or admits them. The
runtime records the recommendation so the controller can be evaluated before any
future authority change.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from bilqis_mlx.compatibility.historical_teacher_policy import KNOBS
from bilqis_mlx.learning.teacher_outcomes import predict, proposed_action
from bilqis_mlx.learning.teacher_strategy_population import (
    active_effective_strategy_keys,
    effective_policy_features,
    effective_policy_key,
)


PROPOSAL_FAMILIES = (
    "INCUMBENT_REPLAY",
    "LOCAL_INCUMBENT_MUTATION",
    "NEIGHBOR_TRANSFER",
    "GLOBAL_CHALLENGER",
    "LEARNED_LOCAL_DISTRIBUTION",
)


@dataclass(frozen=True)
class AcquisitionPolicy:
    version: str
    exploration_weight: float
    protected_risk_weight: float
    target_prior_gain: float

    def __post_init__(self) -> None:
        if (not self.version or
                not all(isinstance(value, (int, float)) and math.isfinite(value)
                        for value in (self.exploration_weight,
                                      self.protected_risk_weight,
                                      self.target_prior_gain)) or
                self.exploration_weight < 0 or
                self.protected_risk_weight < 0 or
                self.target_prior_gain <= 0):
            raise ValueError("TEACHER_ACQUISITION_POLICY_INVALID")


DEFAULT_ACQUISITION_POLICY = AcquisitionPolicy(
    version="teacher-acquisition/v1",
    exploration_weight=.20,
    protected_risk_weight=1.0,
    target_prior_gain=.5,
)


def _policy_action(family: str, policy_key: str | None, policy: dict, *,
                   candidate_steps: int, batch_size: int) -> dict:
    if family not in PROPOSAL_FAMILIES:
        raise ValueError("TEACHER_PROPOSAL_FAMILY_INVALID")
    parameters = effective_policy_features(policy)
    parameters.update(candidate_steps=candidate_steps, batch_size=batch_size)
    return proposed_action(
        family=family,
        effective_policy_key=effective_policy_key(policy),
        policy_key=policy_key,
        parameters=parameters,
    )


def _context(teacher: dict, capability: str, phase: str,
             curriculum_scope: str) -> dict:
    return teacher.get("causal_experiment", {}).get("contexts", {}).get(
        capability + "|" + phase + "|" + curriculum_scope, {})


def _record_rank(item) -> tuple:
    policy_key, record = item
    trials = int(record.get("trials", 0))
    retained = int(record.get("retained", 0))
    mean = float(record.get("reward_sum", 0.)) / trials if trials else -1e9
    return retained, retained / max(1, trials), mean, trials, policy_key


def _best_retained(scope: dict) -> str | None:
    candidates = [item for item in scope.items()
                  if int(item[1].get("retained", 0)) > 0]
    return max(candidates, key=_record_rank)[0] if candidates else None


def _neighbor_value(values, current):
    ordered = tuple(values)
    if current not in ordered:
        return None
    index = ordered.index(current)
    if index + 1 < len(ordered):
        return ordered[index + 1]
    if index > 0:
        return ordered[index - 1]
    return None


def _local_mutations(policy: dict) -> tuple[dict, ...]:
    """Generate one-step valid neighbors without mutating the strategy archive."""
    variants = []
    for field in ("lr", "old", "depth", "contrast", "distill"):
        neighbor = _neighbor_value(KNOBS[field], policy.get(field))
        if neighbor is None:
            continue
        candidate = dict(policy)
        candidate[field] = neighbor
        if candidate.get("old", 0) + candidate.get("preview", 0) > 24:
            continue
        variants.append(candidate)
    return tuple(variants)


def candidate_proposals(teacher: dict, *, capability: str, phase: str,
                        curriculum_scope: str, candidate_steps: int,
                        batch_size: int) -> tuple[dict, ...]:
    """Build a bounded proposal set spanning exploitation and exploration families."""
    strategies = teacher.get("strategies", {})
    if not isinstance(strategies, dict) or not strategies:
        raise ValueError("TEACHER_PROPOSAL_STRATEGIES_MISSING")
    scope = _context(teacher, capability, phase, curriculum_scope)
    proposals = []
    incumbent_key = _best_retained(scope)
    if incumbent_key is not None:
        incumbent = strategies[incumbent_key]
        proposals.append(_policy_action(
            "INCUMBENT_REPLAY", incumbent_key, incumbent,
            candidate_steps=candidate_steps, batch_size=batch_size))
        archive_effective = {effective_policy_key(item) for item in strategies.values()}
        for variant in _local_mutations(incumbent):
            action = _policy_action(
                "LOCAL_INCUMBENT_MUTATION", None, variant,
                candidate_steps=candidate_steps, batch_size=batch_size)
            action["already_in_historical_archive"] = (
                action["effective_policy_key"] in archive_effective)
            proposals.append(action)

    # Transfer a retained policy from the same capability/scope in another phase.
    transfer_candidates = []
    suffix = "|" + curriculum_scope
    prefix = capability + "|"
    for key, other_scope in teacher.get("causal_experiment", {}).get("contexts", {}).items():
        if key == capability + "|" + phase + "|" + curriculum_scope:
            continue
        if not key.startswith(prefix) or not key.endswith(suffix):
            continue
        retained_key = _best_retained(other_scope)
        if retained_key is not None:
            transfer_candidates.append((retained_key, other_scope[retained_key]))
    if transfer_candidates:
        transfer_key, _ = max(transfer_candidates, key=lambda item: _record_rank(item))
        proposals.append(_policy_action(
            "NEIGHBOR_TRANSFER", transfer_key, strategies[transfer_key],
            candidate_steps=candidate_steps, batch_size=batch_size))

    grade = capability.partition(".")[0]
    active, inventory = active_effective_strategy_keys(teacher, grade, scope)
    effective_scope = {}
    for policy_key, record in scope.items():
        if policy_key in strategies:
            effective_scope.setdefault(effective_policy_key(strategies[policy_key]), []).append(record)

    def challenger_rank(effective_key: str):
        records = effective_scope.get(effective_key, ())
        return (
            sum(int(record.get("trials", 0)) for record in records),
            sum(int(record.get("retained", 0)) for record in records),
            effective_key,
        )

    challenger_effective = min(active, key=challenger_rank)
    member_keys = inventory[challenger_effective]
    challenger_key = min(
        member_keys,
        key=lambda key: (
            int(scope.get(key, {}).get("trials", 0)), key))
    proposals.append(_policy_action(
        "GLOBAL_CHALLENGER", challenger_key, strategies[challenger_key],
        candidate_steps=candidate_steps, batch_size=batch_size))

    unique = {}
    for proposal in proposals:
        unique.setdefault(proposal["key"], proposal)
    return tuple(unique.values())


def acquire(teacher: dict, *, region: dict, proposals, rng,
            policy: AcquisitionPolicy = DEFAULT_ACQUISITION_POLICY) -> dict:
    """Thompson-style shadow acquisition across a bounded proposal set."""
    proposals = tuple(proposals)
    if not proposals:
        raise ValueError("TEACHER_ACQUISITION_PROPOSALS_EMPTY")
    rows = []
    for proposal in proposals:
        estimate = predict(teacher, region=region, action=proposal)
        trials = int(estimate["trials"])
        retained = int(estimate["retained"])
        sampled_retention = rng.betavariate(
            retained + 1, trials - retained + 1)
        expected_target = (
            estimate["expected_target_delta"]
            if trials else policy.target_prior_gain)
        expected_target = max(0., expected_target)
        risk = max(0., -estimate["expected_protected_net_delta"]) + float(
            estimate.get("mean_worst_protected_loss", 0.))
        cost = float(estimate["expected_candidate_steps"] or
                     proposal.get("parameters", {}).get("candidate_steps") or 1)
        uncertainty = (
            estimate["retention_interval"][1] -
            estimate["retention_interval"][0])
        score = (
            sampled_retention * expected_target / max(1., cost) -
            policy.protected_risk_weight * risk / max(1., cost) +
            policy.exploration_weight * uncertainty / max(1., cost)
        )
        rows.append({
            "proposal": proposal,
            "prediction": estimate,
            "sampled_retention_probability": sampled_retention,
            "acquisition_score": score,
        })
    ranked = sorted(rows, key=lambda row: (
        row["acquisition_score"],
        row["proposal"]["family"],
        row["proposal"]["key"],
    ), reverse=True)
    return {
        "schema": "bilqis.teacher-proposal-shadow/v1",
        "mode": "SHADOW",
        "policy_version": policy.version,
        "selected": ranked[0],
        "ranked": ranked,
        "actual_authority_changed": False,
    }
