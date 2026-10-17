"""Opt-in, parent-relative candidate safety and contextual teacher evidence.

Neither historical teacher statistics nor frozen qualification receipts are
rewritten. These experimentally learned outcomes use matched, source-oracled
parent/challenger questions; an approximate failure signature is never gold.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
from typing import Mapping

import numpy as np


VERSION = "bilqis.mlx.causal-teacher-experiment/v1"
MAX_FAILURE_ARCHETYPES = 24


@dataclass(frozen=True)
class Settings:
    """Provisional, operator-selected trial budgets, not graduation criteria."""
    probe_each: int = 6
    mature_max_loss: int = 1
    introduction_extra_loss: int = 2
    protected_cap_limit: int = 8

    def __post_init__(self):
        if (type(self.probe_each) is not int or not 2 <= self.probe_each <= 48
                or type(self.mature_max_loss) is not int or
                not 0 <= self.mature_max_loss < self.probe_each or
                type(self.introduction_extra_loss) is not int or
                not 0 <= self.introduction_extra_loss <= self.probe_each or
                type(self.protected_cap_limit) is not int or
                not 1 <= self.protected_cap_limit <= 128):
            raise ValueError("LEARNING_EXPERIMENT_INVALID_SETTINGS")


def sampled_protection(admitted: set[str], current: str,
                       scores: dict, *, cap_limit: int, rotation: int) -> set[str]:
    """Bound the costly probe executions, preserving grade coverage over time.

    Poorly scoring capabilities are preferred, while rotation occasionally
    samples seemingly safe older capabilities. Scheduled full school exams
    remain the independent cumulative authority.
    """
    if current not in admitted or cap_limit < 1 or rotation < 0:
        raise ValueError("LEARNING_EXPERIMENT_PROBE_SELECTION_INVALID")
    eligible = admitted - {current}
    if len(eligible) <= cap_limit:
        return eligible
    groups = {}
    for cap in sorted(eligible):
        groups.setdefault(cap.partition(".")[0], []).append(cap)

    def weakness(cap):
        value = scores.get(cap) or {}
        correct, total = value.get("correct"), value.get("total")
        return (correct/total if type(correct) is int and type(total) is int
                and 0 <= correct <= total and total else 1.)

    result = set()
    # Coverage slot for each represented grade; oldest severe failures and a
    # moving rotation are both considered, without permanent whitelist tests.
    grade_names = sorted(groups)
    if len(grade_names) > cap_limit:
        shift = rotation % len(grade_names)
        grade_names = (grade_names[shift:] + grade_names[:shift])[:cap_limit]
    for grade in grade_names:
        caps = groups[grade]
        ordered = sorted(caps, key=lambda cap:(weakness(cap), cap))
        chosen = ordered[(rotation // max(1,cap_limit)) % len(ordered)]
        result.add(chosen)
        if len(result) >= cap_limit:
            return result
    # One rotational slot explicitly combats stale, apparently safe skills.
    rotated = sorted(eligible-result)
    if rotated and len(result) < cap_limit:
        result.add(rotated[rotation % len(rotated)])
    rest = sorted(eligible-result, key=lambda cap:(weakness(cap), cap))
    return result | set(rest[:max(0,cap_limit-len(result))])


def paired_outcomes(rows, parent_predictions: Mapping[str, str],
                    candidate_predictions: Mapping[str, str]) -> dict:
    """Scores only paired, stable source-gold rows, per capability."""
    if not rows or any(
            r.get("id") not in parent_predictions or
            r.get("id") not in candidate_predictions or
            not r.get("capability") or not isinstance(r.get("gold"), str)
            for r in rows):
        raise ValueError("LEARNING_EXPERIMENT_INCOMPLETE_PAIRED_COHORT")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("LEARNING_EXPERIMENT_DUPLICATE_ROW")
    counts: dict[str, dict] = {}
    for row in rows:
        entry = counts.setdefault(row["capability"], {"before": 0, "after": 0, "total": 0})
        entry["total"] += 1
        entry["before"] += int(parent_predictions[row["id"]] == row["gold"])
        entry["after"] += int(candidate_predictions[row["id"]] == row["gold"])
    return counts


def _prototype_similarity(delta: dict[str, float], prototypes: list[dict]) -> float | None:
    """Diagnostic cosine against measured protected-loss patterns, not veto."""
    highest = None
    for prototype in prototypes:
        old = prototype.get("delta", {})
        common = set(delta) & set(old)
        if not common:
            continue
        numerator = sum(delta[name] * old[name] for name in common)
        aa = sum(delta[name] ** 2 for name in common)
        bb = sum(old[name] ** 2 for name in common)
        if aa and bb:
            similarity = numerator / math.sqrt(aa * bb)
            highest = similarity if highest is None else max(highest, similarity)
    return None if highest is None else round(highest, 6)


def decide(paired: dict, *, active_capability: str, phase: str,
           protected: set[str], settings: Settings,
           mature_grades: frozenset[str] = frozenset(),
           negative_prototypes: list[dict] | None = None,
           source_cohort_sha256: str | None = None) -> dict:
    """Promote only measured targeted gains, protecting graduated grades.

    The parent/student and native AdamW remain untouched on rejection.
    A MAIN scheduler pass is not equivalent to introduction of a new skill.
    """
    if active_capability not in paired or not phase:
        raise ValueError("LEARNING_EXPERIMENT_MISSING_ACTIVE_CAPABILITY")
    missing = protected - set(paired)
    if missing:
        raise ValueError("LEARNING_EXPERIMENT_PROTECTED_CAPABILITY_NOT_MEASURED")
    deltas = {}
    regressions = {}
    for cap, counts in sorted(paired.items()):
        before, after, total = (counts[k] for k in ("before", "after", "total"))
        if (any(type(v) is not int for v in (before, after, total)) or
                not 0 < total or not 0 <= before <= total or
                not 0 <= after <= total):
            raise ValueError("LEARNING_EXPERIMENT_INVALID_PAIRED_SCORE")
        deltas[cap] = round((after-before)/total, 7)
        if cap in protected and cap != active_capability:
            regressions[cap] = max(0, before-after)
    introduction = phase == "MAIN"
    allowed = settings.mature_max_loss + (settings.introduction_extra_loss if introduction else 0)
    # The extra developmental budget applies only to ungraduated skills.
    # Older A/B champions remain mature even during a C MAIN pass.
    tolerances = {
        cap: (settings.mature_max_loss if cap.partition(".")[0] in mature_grades else allowed)
        for cap in sorted(regressions)
    }
    exceeded = {cap: loss for cap, loss in regressions.items()
                if loss > tolerances[cap]}
    active = paired[active_capability]
    active_gain = active["after"] - active["before"]
    protected_net_gain = sum(paired[cap]["after"] - paired[cap]["before"]
                             for cap in protected if cap != active_capability)
    # Local lesson training reward is not evidence of improved capability.
    # The same, source-oracled parent/challenger probe must improve strictly.
    no_target_gain = active_gain <= 0
    fingerprint = json.dumps(paired, sort_keys=True, separators=(",", ":"))
    if (source_cohort_sha256 is not None and
            (len(source_cohort_sha256) != 64 or
             any(c not in "0123456789abcdef" for c in source_cohort_sha256))):
        raise ValueError("LEARNING_EXPERIMENT_COHORT_DIGEST_INVALID")
    return {
        "version": VERSION,
        "decision": "REJECT" if no_target_gain or exceeded else "PROVISIONAL",
        "reason": ("NO_MEASURABLE_TARGET_GAIN" if no_target_gain else
                   "PROTECTED_CAPABILITY_REGRESSION" if exceeded else
                   "PAIRED_SCREEN_WITHIN_BUDGET"),
        "phase": phase, "active_capability": active_capability,
        "active_probe_before": active["before"],
        "active_probe_after": active["after"],
        "active_probe_total": active["total"],
        "protected_capabilities": sorted(protected),
        "max_tolerated_wrong_answer_delta": allowed,
        "protected_tolerances": tolerances,
        "mature_protected_capabilities": sorted(cap for cap in regressions
                                                 if cap.partition(".")[0] in mature_grades),
        "exceeded": exceeded,
        "worst_protected_loss": max(regressions.values(), default=0),
        "local_correct_delta": active_gain,
        "protected_net_correct_delta": protected_net_gain,
        "paired_scores_sha256": hashlib.sha256(fingerprint.encode()).hexdigest(),
        "source_cohort_sha256": source_cohort_sha256,
        "deltas": deltas,
        "discordance_similarity": _prototype_similarity(deltas, negative_prototypes or []),
        "exact_complete_exam_qualification": False,
    }


def _channel(teacher: dict) -> dict:
    channel = teacher.setdefault("causal_experiment", {
        "version": VERSION, "contexts": {}, "negative_archetypes": [], "events": 0})
    if channel.get("version") != VERSION:
        raise ValueError("LEARNING_EXPERIMENT_CHANNEL_VERSION_DRIFT")
    return channel


def contextual_pick(engine, teacher: dict, capability: str, phase: str, rng,
                    *, curriculum_scope: str = ""):
    """Preserve the inherited bandit's exploration; prefer proven safe context."""
    grade = capability.partition(".")[0]
    original_key, original_policy = engine.pick(teacher, grade, rng)
    channel = _channel(teacher)
    scope = channel["contexts"].get(capability+"|"+phase+"|"+curriculum_scope, {})
    if not scope:
        return original_key, original_policy
    trials = sum(v["trials"] for v in scope.values())
    # Priors stay owned by the inherited bandit. Context decides only when its
    # observed safety preference is demonstrably better than the current pick.
    def score(key):
        record = scope.get(key)
        if not record:
            return float("-inf")
        mean = record["reward_sum"] / record["trials"]
        exploration = math.sqrt(math.log(trials+2)/(record["trials"]+1))
        return mean + exploration
    best = max(scope, key=score)
    if best not in teacher["strategies"]:
        raise ValueError("LEARNING_EXPERIMENT_STRATEGY_ID_DRIFT")
    # Require evidence, but keep inherited exploration alive. The base pick
    # still gets a chance whenever it lacks direct context observations.
    if (scope[best]["trials"] >= 2 and original_key in scope and
            score(best) > score(original_key)):
        return best, teacher["strategies"][best]
    return original_key, original_policy


def observe_context(teacher: dict, *, capability: str, phase: str,
                    policy_key: str, decision: dict, local_gain: float,
                    curriculum_scope: str = "") -> dict:
    """Source-paired trial outcome; never rewrite historical UCB rewards."""
    if (policy_key not in teacher.get("strategies", {}) or
            not math.isfinite(local_gain) or
            decision.get("version") != VERSION or
            decision.get("active_capability") != capability or
            decision.get("phase") != phase):
        raise ValueError("LEARNING_EXPERIMENT_INVALID_CAUSAL_OUTCOME")
    channel = _channel(teacher)
    scope = channel["contexts"].setdefault(capability+"|"+phase+"|"+curriculum_scope, {})
    record = scope.setdefault(policy_key, {"trials": 0, "reward_sum": 0.,
                                            "unsafe": 0, "latest": None})
    # Normalized worst-case retention cost stops many small wins concealing
    # a substantial single-capability loss. Provisional experimental metric.
    relative_loss = max((max(0., -v) for k, v in decision["deltas"].items()
                         if k in decision["protected_capabilities"]), default=0.)
    # Recovery is supposed to retain earlier foundations. Penalize measured
    # interference more heavily there, while introduction can still trade
    # controlled temporary forgetting for acquisition of something new.
    reward = local_gain - relative_loss * (1 if phase == "MAIN" else 2)
    if decision["decision"] == "REJECT":
        reward = min(reward, -relative_loss, -0.05)
    if decision["decision"] == "REJECT" or decision.get("worst_protected_loss", 0) >= 1:
        pattern = {"capability": capability, "phase": phase,
                   "curriculum_scope": curriculum_scope,
                   "policy": policy_key, "delta": decision["deltas"],
                   "paired_scores_sha256": decision["paired_scores_sha256"],
                   "source_cohort_sha256": decision["source_cohort_sha256"],
                   "outcome": ("REJECTED_UPDATE" if decision["decision"] == "REJECT"
                               else "ACCEPTED_WITH_MEASURED_PROTECTED_LOSS")}
        # A provisional regression is observed interference, not proof of
        # durable harm. Keep the distinction in each functional signature.
        entries = channel["negative_archetypes"]
        if not any(item["paired_scores_sha256"] == pattern["paired_scores_sha256"] and
                   item.get("source_cohort_sha256") == pattern["source_cohort_sha256"]
                   for item in entries):
            entries.append(pattern)
            del entries[:-MAX_FAILURE_ARCHETYPES]
    if decision["decision"] == "REJECT":
        record["unsafe"] += 1
    record["trials"] += 1
    record["reward_sum"] += reward
    record["latest"] = reward
    strain = decision.get("matrix_strain") or {}
    if strain.get("status") == "MEASURED":
        # A bounded teacher-observable geometric feature; outcome rewards
        # still come only from actual source-scored capability probes.
        matrices = strain["matrices"]
        record["latest_matrix_strain"] = {
            "best_checkpoint_sha256": strain["best_checkpoint_sha256"],
            "tensor_count": len(matrices),
            "mean_delta_best": sum(item["delta_best_mean_sq"]
                                   for item in matrices.values()) / len(matrices),
            "mean_delta_start": sum(item["delta_start_mean_sq"]
                                    for item in matrices.values()) / len(matrices),
        }
    channel["events"] += 1
    return {"version": VERSION, "teacher_context_reward": reward,
            "legacy_reward_reinterpreted": False,
            "negative_archetype_count": len(channel["negative_archetypes"])}


def fork_student(mx, parameters: dict, optimizer):
    """Copy all FP32 weights and native AdamW to a disposable trial in RAM."""
    import mlx.optimizers as optim
    mx.eval(parameters, optimizer.state)

    def copy_value(value):
        if isinstance(value, mx.array):
            return mx.array(np.asarray(value).copy())
        if isinstance(value, dict):
            return {key: copy_value(item) for key, item in value.items()}
        raise ValueError("LEARNING_EXPERIMENT_UNKNOWN_OPTIMIZER_STATE")

    trial_parameters = copy_value(parameters)
    trial_optimizer = optim.AdamW(
        learning_rate=float(optimizer.learning_rate),
        betas=list(optimizer.betas), eps=optimizer.eps,
        weight_decay=optimizer.weight_decay,
        bias_correction=optimizer.bias_correction)
    trial_optimizer.state = copy_value(optimizer.state)
    mx.eval(trial_parameters, trial_optimizer.state)
    return trial_parameters, trial_optimizer


def commit_trial(parameters: dict, optimizer, trial_parameters: dict, trial_optimizer) -> None:
    """A single caller-owned promotion; rejected trials leave parents intact."""
    if set(parameters) != set(trial_parameters):
        raise ValueError("LEARNING_EXPERIMENT_PARAMETER_IDENTITY_DRIFT")
    if (set(optimizer.state) != set(trial_optimizer.state) or
            int(trial_optimizer.state["step"].item()) <
            int(optimizer.state["step"].item())):
        raise ValueError("LEARNING_EXPERIMENT_ADAMW_DRIFT")
    parameters.update(trial_parameters)
    optimizer.state = trial_optimizer.state
    optimizer.learning_rate = trial_optimizer.learning_rate


def select_typed_lesson(current: list[dict], prior: list[dict], policy: dict,
                        *, seed: int, batch_size: int) -> tuple[list[dict], dict]:
    """Make inherited old/contrast/depth knobs effective on source-valid rows.

    'old' means actual examples originating in already-graduated grades, not
    embedded prerequisites or a source-unverified fixed teaching mix.
    'depth' uses token-count emphasis only when that proxy is named as such.
    Future-grade preview is intentionally inapplicable: never teach new roots.
    """
    if not current or type(batch_size) is not int or batch_size < 2:
        raise ValueError("LEARNING_EXPERIMENT_EMPTY_TYPED_LESSON")
    rng = random.Random(seed)
    requested_old = int(policy.get("old", 0))
    if not 0 <= requested_old <= 32:
        raise ValueError("LEARNING_EXPERIMENT_INVALID_OLD_POLICY")
    old_count = min(batch_size-2, round(requested_old*batch_size/32)) if prior else 0
    present_count = batch_size-old_count

    def choose(source, count):
        if count == 0:
            return []
        if not source:
            raise ValueError("LEARNING_EXPERIMENT_MISSING_SOURCE_ROWS")
        groups = {}
        for row in source:
            groups.setdefault(row.get("source_id", row["id"]), []).append(row)
        chunks = list(groups.values())
        if policy.get("depth", 1) >= 3:
            chunks.sort(key=lambda group: -max(len(row["tokens"]) for row in group))
            # sample primarily from the deeper certified *input tokens*;
            # complexity of the semantic AST is not asserted from token length.
            chunks = chunks[:max(1, (len(chunks)+1)//2)]
        if policy.get("contrast", 0.) >= .5:
            families = {}
            for chunk in chunks:
                key = tuple(sorted(set(row["gold"] for row in chunk)))
                families.setdefault(key, []).append(chunk)
            keys = sorted(families)
            result = []
            while len(result) < count:
                for key in keys:
                    result.extend(rng.choice(families[key]))
                    if len(result) >= count:
                        break
            return result[:count]
        result = []
        while len(result) < count:
            result.extend(rng.choice(chunks))
        return result[:count]

    result = choose(current, present_count) + choose(prior, old_count)
    rng.shuffle(result)
    return ([{**row, "answer_kind": row.get("answer_kind", "binary")}
             for row in result],
            {"effective_old_grade_examples": old_count,
             "requested_old_per_32": requested_old,
             "depth_control": "SOURCE_TOKEN_LENGTH_PROXY" if policy.get("depth", 1) >= 3
                              else "UNBIASED_SOURCE_GROUPS",
             "contrast_control": "SOURCE_GROUP_DIVERSITY" if policy.get("contrast", 0.) >= .5
                                 else "SOURCE_GROUP_RANDOM",
             "preview_control": "NOT_AVAILABLE_UNADMITTED_FUTURE_GRADE"})
