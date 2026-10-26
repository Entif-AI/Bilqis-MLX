"""Shadow learned proposal distribution over productive teacher interventions."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

from bilqis_mlx.compatibility.historical_teacher_policy import KNOBS
from bilqis_mlx.learning.teacher_outcomes import MODEL_SCHEMA, proposed_action


@dataclass(frozen=True)
class DistributionPolicy:
    version: str
    minimum_observations: int
    minimum_retained: int
    samples: int
    log_lr_jitter: float

    def __post_init__(self) -> None:
        if (not self.version or type(self.minimum_observations) is not int or
                type(self.minimum_retained) is not int or type(self.samples) is not int or
                self.minimum_observations < 1 or self.minimum_retained < 1 or
                self.samples < 1 or
                not isinstance(self.log_lr_jitter, (int, float)) or
                not math.isfinite(self.log_lr_jitter) or self.log_lr_jitter < 0):
            raise ValueError("TEACHER_DISTRIBUTION_POLICY_INVALID")


DEFAULT_DISTRIBUTION_POLICY = DistributionPolicy(
    version="teacher-learned-distribution/v1",
    minimum_observations=16,
    minimum_retained=3,
    samples=4,
    log_lr_jitter=.12,
)


def _region_records(teacher: dict, region: dict) -> tuple[dict, ...]:
    model = teacher.get("outcome_model")
    if not isinstance(model, dict) or model.get("schema") != MODEL_SCHEMA:
        return ()
    key = region.get("key")
    if not isinstance(key, str):
        raise ValueError("TEACHER_DISTRIBUTION_REGION_INVALID")
    return tuple(
        record for record in model.get("contexts", {}).values()
        if isinstance(record, dict) and
        isinstance(record.get("region"), dict) and
        record["region"].get("key") == key and
        int(record.get("trials", 0)) > 0
    )


def _utility(record: dict) -> float:
    trials = int(record["trials"])
    retained = int(record["retained"])
    retention = (retained + 1) / (trials + 2)
    target = max(0., float(record["target_delta_sum"]) / trials)
    risk = max(0., -float(record["protected_net_delta_sum"]) / trials)
    risk += float(record["worst_protected_loss_sum"]) / trials
    cost = max(1., float(record["attempted_steps_sum"]) / trials)
    return max(1e-9, retention * max(.1, target) / cost / (1 + risk))


def _weighted_mean(rows, field: str, transform=lambda value: value) -> float | None:
    values = []
    for record in rows:
        value = (record.get("action", {}).get("parameters") or {}).get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        values.append((_utility(record), transform(float(value))))
    if not values:
        return None
    total = sum(weight for weight, _ in values)
    return sum(weight * value for weight, value in values) / total


def _weighted_mode(rows, field: str):
    weights = {}
    for record in rows:
        value = (record.get("action", {}).get("parameters") or {}).get(field)
        if value is None:
            continue
        weights[value] = weights.get(value, 0.) + _utility(record)
    return max(weights, key=lambda value: (weights[value], str(value))) if weights else None


def _clamp(value: float, choices) -> float:
    return max(min(choices), min(max(choices), value))


def _nearest(value: float, choices):
    return min(choices, key=lambda candidate: (abs(float(candidate) - value), candidate))


def _effective_identity(parameters: dict) -> str:
    return hashlib.sha256(json.dumps(
        parameters, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()[:12]


def learned_proposals(teacher: dict, *, region: dict, rng,
                      policy: DistributionPolicy = DEFAULT_DISTRIBUTION_POLICY,
                      candidate_steps: int, batch_size: int) -> dict:
    """Fit a bounded local distribution and sample shadow-only interventions."""
    rows = _region_records(teacher, region)
    observations = sum(int(record["trials"]) for record in rows)
    retained = sum(int(record["retained"]) for record in rows)
    qualified = (
        observations >= policy.minimum_observations and
        retained >= policy.minimum_retained)
    result = {
        "schema": "bilqis.teacher-learned-distribution/v1",
        "mode": "SHADOW",
        "policy_version": policy.version,
        "observations": observations,
        "retained": retained,
        "status": "QUALIFIED" if qualified else "NOT_QUALIFIED",
        "proposals": [],
        "actual_authority_changed": False,
    }
    if not qualified:
        return result

    mean_log_lr = _weighted_mean(rows, "lr", math.log)
    mean_old = _weighted_mean(rows, "old")
    mean_distill = _weighted_mean(rows, "distill")
    depth = _weighted_mode(rows, "depth")
    contrast = _weighted_mode(rows, "contrast")
    if mean_log_lr is None:
        return result
    old = _nearest(mean_old if mean_old is not None else 8, KNOBS["old"])
    distill = _clamp(mean_distill if mean_distill is not None else 0., KNOBS["distill"])
    depth = depth if depth in {"SHALLOW", "DEEP"} else "SHALLOW"
    contrast = contrast if contrast in {"RANDOM", "DIVERSE"} else "RANDOM"
    for _ in range(policy.samples):
        learning_rate = _clamp(
            math.exp(rng.gauss(mean_log_lr, policy.log_lr_jitter)),
            KNOBS["lr"])
        parameters = {
            "lr": learning_rate,
            "old": old,
            "depth": depth,
            "contrast": contrast,
            "distill": distill,
            "candidate_steps": candidate_steps,
            "batch_size": batch_size,
        }
        result["proposals"].append(proposed_action(
            family="LEARNED_LOCAL_DISTRIBUTION",
            effective_policy_key=_effective_identity(parameters),
            parameters=parameters))
    return result
