"""Default-on parent-relative candidate safety and contextual teacher evidence.

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

from bilqis_mlx.learning.teacher_feedback import (
    WeaknessTargetError, WeaknessTargetRequest, select_weakness_targets,
)


VERSION = "bilqis.mlx.causal-teacher-experiment/v1"
MAX_FAILURE_ARCHETYPES = 24
TEACHER_UCB_EXPLORATION_WEIGHT = 0.6


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


def whole_grade_protection(admitted: set[str], current: str,
                           scores: dict, *, cap_limit: int, rotation: int) -> set[str]:
    """Always measure every admitted peer in the target grade.

    Same-grade completeness is mandatory, not constrained by the unrelated
    budget for optional rotating cross-grade sentinels. Keep two sentinel
    slots when other grades exist, even for a large target grade, so the work
    scales with the *target grade*, not the cumulative school.
    """
    own = {cap for cap in admitted if cap.partition(".")[0] ==
           current.partition(".")[0]}
    peers, other = own - {current}, admitted - own
    if current not in own or cap_limit < 1:
        raise ValueError("LEARNING_EXPERIMENT_FULL_GRADE_PROBE_SCOPE_INVALID")
    remaining = max(min(2, cap_limit), cap_limit-len(peers)) if other else 0
    sampled = (sampled_protection(other | {current}, current, scores,
                                 cap_limit=remaining, rotation=rotation)
               if remaining and other else set())
    return peers | sampled


def missing_grade_capabilities(grade_capabilities, scored_capabilities):
    """Return only unscored peers for a single candidate's qualification.

    The caller owns checkpoint and source-cohort provenance. A different
    checkpoint's scores must never be passed in as if they were cached.
    """
    grade = tuple(grade_capabilities)
    if (not grade or len(grade) != len(set(grade)) or
            any(not isinstance(cap, str) or not cap for cap in grade) or
            not isinstance(scored_capabilities, dict)):
        raise ValueError("LEARNING_EXPERIMENT_INVALID_GRADE_COMPLETION_SCOPE")
    return tuple(cap for cap in grade if cap not in scored_capabilities)


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


def _same_grade_retention_evidence(paired, active_capability,
                                   same_grade_capabilities, fixed_grade_replay):
    grade = active_capability.partition(".")[0]
    required = (set(same_grade_capabilities) if same_grade_capabilities is not None
                else {cap for cap in paired if cap.partition(".")[0] == grade})
    if (not required or active_capability not in required or
            any(cap.partition(".")[0] != grade for cap in required) or
            not required <= set(paired) or
            (same_grade_capabilities is not None and
             len(set(same_grade_capabilities)) != len(same_grade_capabilities))):
        raise ValueError("LEARNING_EXPERIMENT_INCOMPLETE_SAME_GRADE_PROBE")
    net = sum(paired[cap]["after"] - paired[cap]["before"] for cap in required)
    fixed = fixed_grade_replay or {
        "status": "NOT_MEASURED",
        "reason": "NO_COMPARABLE_COMPLETE_GRADE_EXAM",
    }
    if fixed.get("status") == "MEASURED":
        before_grade, after_grade, total = (
            fixed.get(name) for name in ("before", "after", "total"))
        sha = fixed.get("cohort_sha256")
        if (fixed.get("grade") != grade or
                any(type(n) is not int for n in
                    (before_grade, after_grade, total)) or
                not 0 < total or not 0 <= before_grade <= total or
                not 0 <= after_grade <= total or
                not isinstance(sha, str) or len(sha) != 64 or
                any(c not in "0123456789abcdef" for c in sha)):
            raise ValueError("LEARNING_EXPERIMENT_INVALID_FIXED_GRADE_COHORT")
        fixed = {**fixed, "net_correct_delta": after_grade-before_grade}
    elif fixed.get("status") != "NOT_MEASURED":
        raise ValueError("LEARNING_EXPERIMENT_INVALID_FIXED_GRADE_STATUS")
    return required, net, fixed


def _paired_screen(paired, protected, active_capability):
    if protected - set(paired):
        raise ValueError("LEARNING_EXPERIMENT_PROTECTED_CAPABILITY_NOT_MEASURED")
    deltas, regressions = {}, {}
    for cap, counts in sorted(paired.items()):
        before, after, total = (counts[k] for k in ("before", "after", "total"))
        if (any(type(v) is not int for v in (before, after, total)) or
                not 0 < total or not 0 <= before <= total or
                not 0 <= after <= total):
            raise ValueError("LEARNING_EXPERIMENT_INVALID_PAIRED_SCORE")
        deltas[cap] = round((after-before)/total, 7)
        if cap in protected and cap != active_capability:
            regressions[cap] = max(0, before-after)
    return deltas, regressions


def _fixed_frontier_retention_evidence(value, protected_frontier_grade):
    frontier = value or {
        "status": "NOT_MEASURED",
        "reason": "NO_FIXED_WHOLE_SCHOOL_FRONTIER",
    }
    status = frontier.get("status")
    if status not in ("MEASURED", "NOT_MEASURED"):
        raise ValueError("LEARNING_EXPERIMENT_INVALID_FIXED_FRONTIER_STATUS")
    if status == "NOT_MEASURED":
        return frontier, False, False, None
    before, after, total = (
        frontier.get("before_correct"), frontier.get("after_correct"),
        frontier.get("rows"))
    regressions = frontier.get("regressions")
    repaired = frontier.get("repaired")
    if (any(type(number) is not int for number in (before, after, total)) or
            not 0 < total or not 0 <= before <= total or
            not 0 <= after <= total or
            not isinstance(regressions, list) or
            not isinstance(repaired, list)):
        raise ValueError("LEARNING_EXPERIMENT_INVALID_FIXED_FRONTIER_SCORE")
    active_grade_regression = False
    if protected_frontier_grade is not None:
        grades = frontier.get("grades")
        invalid = not isinstance(grades, dict)
        grade = None if invalid else grades.get(protected_frontier_grade)
        if grade is not None:
            invalid = (
                not isinstance(grade, dict) or
                any(type(grade.get(name)) is not int
                    for name in ("before", "after", "total")) or
                not 0 < grade["total"] or
                not 0 <= grade["before"] <= grade["total"] or
                not 0 <= grade["after"] <= grade["total"])
        if invalid:
            raise ValueError(
                "LEARNING_EXPERIMENT_INVALID_ACTIVE_GRADE_FRONTIER")
        if grade is not None:
            active_grade_regression = grade["after"] < grade["before"]
    return frontier, after < before, active_grade_regression, after - before


def _retention_reason(*, no_target_gain, same_grade_net_gain,
                      fixed_grade_regression, active_grade_regression,
                      whole_school_regression, frontier_measured,
                      fragile_losses, exceeded):
    if no_target_gain:
        return "NO_MEASURABLE_TARGET_GAIN"
    if not frontier_measured and fragile_losses:
        return "FRAGILE_COMPOSITION_REPLAY_REGRESSION"
    if exceeded:
        return "PROTECTED_CAPABILITY_REGRESSION"
    if not frontier_measured:
        if same_grade_net_gain < 0:
            return "SAME_GRADE_NET_REGRESSION"
        if same_grade_net_gain == 0:
            return "NO_POSITIVE_SAME_GRADE_GAIN"
        if fixed_grade_regression:
            return "FIXED_GRADE_COHORT_REGRESSION"
        return "PAIRED_SCREEN_WITHIN_BUDGET"
    if same_grade_net_gain < 0:
        return "SAME_GRADE_NET_REGRESSION"
    if fixed_grade_regression:
        return "FIXED_LESSON_GRADE_REGRESSION"
    if active_grade_regression:
        return "ACTIVE_SCHOOL_GRADE_REGRESSION"
    if whole_school_regression:
        return "WHOLE_SCHOOL_NET_REGRESSION"
    return "PAIRED_SCREEN_WITHIN_BUDGET"


def _protected_diagnostics(paired, protected, active_capability, phase,
                           settings, mature_grades):
    deltas, regressions = _paired_screen(
        paired, protected, active_capability)
    introduction = phase == "MAIN"
    allowed = settings.mature_max_loss + (
        settings.introduction_extra_loss if introduction else 0)
    reference_losses = {
        cap: (settings.mature_max_loss
              if cap.partition(".")[0] in mature_grades else allowed)
        for cap in sorted(regressions)
    }
    # Loss budgets are rates expressed against the configured reference probe,
    # not absolute answer counts. Preserve the original 1/6 (or MAIN 3/6)
    # risk appetite when a capability is measured on a larger paired panel.
    tolerances = {
        cap: min(
            paired[cap]["total"],
            paired[cap]["total"] * reference_losses[cap] // settings.probe_each)
        for cap in sorted(regressions)
    }
    exceeded = {
        cap: loss for cap, loss in regressions.items()
        if loss > tolerances[cap]
    }
    protected_net_gain = sum(
        paired[cap]["after"] - paired[cap]["before"]
        for cap in protected if cap != active_capability)
    return (deltas, regressions, allowed, tolerances, exceeded,
            protected_net_gain)


def _validate_source_cohort_sha256(value):
    if (value is not None and
            (len(value) != 64 or
             any(char not in "0123456789abcdef" for char in value))):
        raise ValueError("LEARNING_EXPERIMENT_COHORT_DIGEST_INVALID")


def decide(paired: dict, *, active_capability: str, phase: str,
           protected: set[str], settings: Settings,
           mature_grades: frozenset[str] = frozenset(),
           negative_prototypes: list[dict] | None = None,
           source_cohort_sha256: str | None = None,
           fragile_replay: dict | None = None,
           same_grade_capabilities: tuple[str, ...] | None = None,
           fixed_grade_replay: dict | None = None,
           fixed_frontier_replay: dict | None = None,
           protected_frontier_grade: str | None = None) -> dict:
    """Retain only target gains that do not sacrifice their own grade.

    The parent/student and native AdamW remain untouched on rejection.
    A MAIN scheduler pass is not equivalent to introduction of a new skill.
    """
    if active_capability not in paired or not phase:
        raise ValueError("LEARNING_EXPERIMENT_MISSING_ACTIVE_CAPABILITY")
    (deltas, regressions, allowed, tolerances, exceeded,
     protected_net_gain) = _protected_diagnostics(
         paired, protected, active_capability, phase, settings,
         mature_grades)
    active = paired[active_capability]
    active_gain = active["after"] - active["before"]
    required, same_grade_net_gain, fixed = _same_grade_retention_evidence(
        paired, active_capability, same_grade_capabilities, fixed_grade_replay)
    # Local lesson training reward is not evidence of improved capability.
    # The same, source-oracled parent/challenger probe must improve strictly.
    no_target_gain = active_gain <= 0
    frontier, whole_school_regression, active_grade_regression, frontier_net = (
        _fixed_frontier_retention_evidence(
            fixed_frontier_replay, protected_frontier_grade))
    frontier_measured = frontier.get("status") == "MEASURED"
    protected_frontier_delta = None
    if frontier_measured and protected_frontier_grade is not None:
        grades = frontier.get("grades")
        grade = (grades.get(protected_frontier_grade)
                 if isinstance(grades, dict) else None)
        if isinstance(grade, dict):
            protected_frontier_delta = grade["after"] - grade["before"]
    fixed_grade_regression = (
        fixed.get("status") == "MEASURED" and
        fixed["net_correct_delta"] < 0)
    fragile_losses = bool(
        fragile_replay and fragile_replay.get("regressions"))
    if fragile_replay is not None and fragile_replay.get("status") not in (
            "MEASURED", "NOT_MEASURED"):
        raise ValueError("LEARNING_EXPERIMENT_INVALID_FRAGILE_REPLAY")
    fingerprint = json.dumps(paired, sort_keys=True, separators=(",", ":"))
    _validate_source_cohort_sha256(source_cohort_sha256)
    reason = _retention_reason(
        no_target_gain=no_target_gain,
        same_grade_net_gain=same_grade_net_gain,
        fixed_grade_regression=fixed_grade_regression,
        active_grade_regression=active_grade_regression,
        whole_school_regression=whole_school_regression,
        frontier_measured=frontier_measured,
        fragile_losses=fragile_losses,
        exceeded=exceeded)
    return {
        "version": VERSION,
        "decision": ("REJECT" if reason != "PAIRED_SCREEN_WITHIN_BUDGET"
                     else "PROVISIONAL"),
        "reason": reason,
        "fragile_replay": fragile_replay,
        "fixed_grade_replay": fixed,
        "fixed_frontier_replay": frontier,
        "fixed_whole_school_net_correct_delta": frontier_net,
        "protected_frontier_grade": protected_frontier_grade,
        "protected_frontier_grade_net_correct_delta": protected_frontier_delta,
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
        "same_grade_net_correct_delta": same_grade_net_gain,
        "same_grade_probed_capabilities": sorted(required),
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


def _stagnation_key(capability: str, curriculum_scope: str) -> str:
    return capability+"|"+curriculum_scope


def _shared_no_gain_streak(channel: dict, capability: str,
                           curriculum_scope: str, policy_key: str) -> int:
    return int(channel.get("stagnation", {})
                      .get(_stagnation_key(capability, curriculum_scope), {})
                      .get(policy_key, {})
                      .get("no_target_gain_streak", 0))


def _shared_stagnation_record(channel: dict, capability: str,
                              curriculum_scope: str, policy_key: str) -> dict:
    scope = channel.setdefault("stagnation", {}).setdefault(
        _stagnation_key(capability, curriculum_scope), {})
    return scope.setdefault(policy_key, {"no_target_gain_streak": 0})


def _capability_stagnation(channel: dict, capability: str,
                           curriculum_scope: str) -> dict:
    return channel.get("capability_stagnation", {}).get(
        _stagnation_key(capability, curriculum_scope), {})


def _capability_stagnation_record(channel: dict, capability: str,
                                  curriculum_scope: str) -> dict:
    return channel.setdefault("capability_stagnation", {}).setdefault(
        _stagnation_key(capability, curriculum_scope), {
            "rejection_streak": 0,
            "no_target_gain_streak": 0,
            "attempts_since_retained": 0,
            "total_rejections": 0,
            "total_retained": 0,
        })


def _inherited_exploration(teacher: dict, grade: str, policy_key: str) -> float:
    local = teacher.get("grade_stats", {}).get(str(grade), {})
    info = local.get(policy_key) or teacher.get("global_stats", {}).get(policy_key)
    if not info or not info.get("trials"):
        return 0.
    total = int(teacher.get("events", 0)) + 1
    return TEACHER_UCB_EXPLORATION_WEIGHT * math.sqrt(
        math.log(total+2)/(1+info["trials"]))


_CONTEXT_INEFFECTIVE_POLICY_FIELDS = frozenset({"preview"})


def _effective_policy_key(policy: dict) -> str:
    """Identity for knobs that actually change the current source lesson.

    Future-grade preview is deliberately unavailable in the admitted-source
    trainer, so preview-only legacy variants are one effective contextual
    strategy even though their historical policy IDs remain distinct.
    """
    if not isinstance(policy, dict):
        raise ValueError("LEARNING_EXPERIMENT_POLICY_INVALID")
    effective = {
        key: value for key, value in sorted(policy.items())
        if key not in _CONTEXT_INEFFECTIVE_POLICY_FIELDS
    }
    return hashlib.sha256(
        json.dumps(effective, sort_keys=True).encode()).hexdigest()[:12]


def _effective_context_scope(teacher: dict, scope: dict) -> dict:
    """Aggregate contextual evidence across behaviorally identical policies."""
    groups = {}
    strategies = teacher.get("strategies", {})
    for policy_key, record in scope.items():
        policy = strategies.get(policy_key)
        if policy is None:
            raise ValueError("LEARNING_EXPERIMENT_STRATEGY_ID_DRIFT")
        effective_key = _effective_policy_key(policy)
        group = groups.setdefault(effective_key, {
            "trials": 0,
            "reward_sum": 0.,
            "unsafe": 0,
            "retained": 0,
            "no_target_gain_streak": 0,
            "members": [],
        })
        group["trials"] += int(record.get("trials", 0))
        group["reward_sum"] += float(record.get("reward_sum", 0.))
        group["unsafe"] += int(record.get("unsafe", 0))
        group["retained"] += int(record.get("retained", 0))
        group["no_target_gain_streak"] += int(
            record.get("no_target_gain_streak", 0))
        group["members"].append(policy_key)
    return groups


def contextual_pick(engine, teacher: dict, capability: str, phase: str, rng,
                    *, curriculum_scope: str = ""):
    """Preserve the inherited bandit's exploration; prefer proven safe context."""
    grade = capability.partition(".")[0]
    original_key, original_policy = engine.pick(teacher, grade, rng)
    channel = _channel(teacher)
    scope = channel["contexts"].get(capability+"|"+phase+"|"+curriculum_scope, {})
    if not scope:
        return original_key, original_policy
    effective_scope = _effective_context_scope(teacher, scope)
    trials = sum(v["trials"] for v in effective_scope.values())
    capability_stagnation = _capability_stagnation(
        channel, capability, curriculum_scope)
    rejection_pressure = int(capability_stagnation.get("rejection_streak", 0))
    # Priors stay owned by the inherited bandit. Context decides only when its
    # observed safety preference is demonstrably better than the current pick.
    def score_effective(key):
        record = effective_scope.get(key)
        if not record:
            return float("-inf")
        mean = record["reward_sum"] / record["trials"]
        exploration = (TEACHER_UCB_EXPLORATION_WEIGHT *
                       math.sqrt(math.log(trials+2)/(record["trials"]+1)))
        stagnation = record["no_target_gain_streak"]
        return mean + exploration/(1+stagnation+rejection_pressure)
    best_effective = max(effective_scope, key=score_effective)
    best_record = effective_scope[best_effective]

    def member_rank(key):
        record = scope[key]
        mean = record["reward_sum"] / record["trials"]
        return (record.get("retained", 0), mean, record["trials"], key)

    best = max(best_record["members"], key=member_rank)
    original_effective = _effective_policy_key(original_policy)
    if original_effective == best_effective:
        return original_key, original_policy
    # Require evidence, but keep inherited exploration alive. The base pick
    # still gets a chance whenever it lacks direct context observations.
    proven_retained = best_record.get("retained", 0) > 0
    if (proven_retained and rejection_pressure > 0 and
            (original_effective not in effective_scope or
             score_effective(best_effective) >
             score_effective(original_effective))):
        return best, teacher["strategies"][best]
    if ((best_record["trials"] >= 2 or proven_retained) and
            original_effective in effective_scope and
            score_effective(best_effective) > score_effective(original_effective)):
        return best, teacher["strategies"][best]
    return original_key, original_policy


def _stagnation_feedback(teacher: dict, capability: str, policy_key: str,
                         decision: dict, reward: float, record: dict,
                         shared_stagnation: dict) -> tuple[float, float]:
    no_target_gain = decision.get("reason") == "NO_MEASURABLE_TARGET_GAIN"
    inherited_exploration = _inherited_exploration(
        teacher, capability.partition(".")[0], policy_key)
    selection_reward = reward
    repayment = 0.-inherited_exploration
    if no_target_gain and repayment < selection_reward:
        selection_reward = repayment
    if no_target_gain:
        record["no_target_gain_streak"] += 1
        shared_stagnation["no_target_gain_streak"] += 1
    else:
        record["no_target_gain_streak"] = 0
        shared_stagnation["no_target_gain_streak"] = 0
    return inherited_exploration, selection_reward


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
    no_target_gain = decision.get("reason") == "NO_MEASURABLE_TARGET_GAIN"
    channel = _channel(teacher)
    scope = channel["contexts"].setdefault(capability+"|"+phase+"|"+curriculum_scope, {})
    record = scope.setdefault(policy_key, {"trials": 0, "reward_sum": 0.,
                                            "unsafe": 0, "retained": 0,
                                            "latest": None,
                                            "no_target_gain_streak": 0})
    record.setdefault("no_target_gain_streak", 0)
    record.setdefault("retained", 0)
    shared_stagnation = _shared_stagnation_record(
        channel, capability, curriculum_scope, policy_key)
    capability_stagnation = _capability_stagnation_record(
        channel, capability, curriculum_scope)
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
        capability_stagnation["rejection_streak"] += 1
        capability_stagnation["attempts_since_retained"] += 1
        capability_stagnation["total_rejections"] += 1
    else:
        record["retained"] += 1
        capability_stagnation["rejection_streak"] = 0
        capability_stagnation["attempts_since_retained"] = 0
        capability_stagnation["total_retained"] += 1
    if no_target_gain:
        capability_stagnation["no_target_gain_streak"] += 1
    else:
        capability_stagnation["no_target_gain_streak"] = 0
    inherited_exploration, selection_reward = _stagnation_feedback(
        teacher, capability, policy_key, decision, reward, record,
        shared_stagnation)
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
    replay = decision.get("fragile_replay") or {}
    if replay.get("status") == "MEASURED":
        record["latest_fragile_replay"] = {
            "cohort_sha256": replay["cohort_sha256"],
            "rows": replay["rows"],
            "regressions": len(replay["regressions"]),
            "repaired": replay["repaired"],
        }
    channel["events"] += 1
    return {"version": VERSION, "teacher_context_reward": reward,
            "no_target_gain_streak": record["no_target_gain_streak"],
            "shared_no_target_gain_streak":
                shared_stagnation["no_target_gain_streak"],
            "capability_rejection_streak":
                capability_stagnation["rejection_streak"],
            "capability_no_target_gain_streak":
                capability_stagnation["no_target_gain_streak"],
            "attempts_since_retained":
                capability_stagnation["attempts_since_retained"],
            "inherited_exploration_credit": inherited_exploration,
            "teacher_selection_reward": selection_reward,
            "legacy_reward_reinterpreted": False,
            "negative_archetype_count": len(channel["negative_archetypes"])}


def selection_credit(lesson_reward: float, retention: dict | None,
                     contextual: dict | None) -> float:
    """Use source-paired admission feedback for forward-only bandit learning.

    The old lesson delta still describes retained student accuracy. Under
    retention it is zero on rejection, which must not mean a neutral teacher
    experiment. The context channel has already scored that same attempt.
    """
    if retention is None:
        return lesson_reward
    reward = contextual.get("teacher_selection_reward") if isinstance(contextual, dict) else None
    if reward is None and isinstance(contextual, dict):
        reward = contextual.get("teacher_context_reward")
    if (not isinstance(reward, (float, int)) or not math.isfinite(reward) or
            (retention.get("decision") == "REJECT" and reward >= 0)):
        raise ValueError("LEARNING_EXPERIMENT_INVALID_SELECTION_CREDIT")
    return float(reward)


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


def earlier_grade_capabilities(program, graduated_grades, target: str, *,
                               carried_mastery_debt=()) -> tuple[str, ...]:
    """Earlier graduated skills and explicitly carried debt supply old lessons.

    A champion for the active grade does not make its own rows earlier-grade
    rehearsal; future grades must not leak into the pool during recovery.
    """
    from bilqis_mlx.factory.schedule import ScheduleProgram
    if not isinstance(program, ScheduleProgram):
        raise TypeError("LEARNING_EXPERIMENT_SCHEDULE_PROGRAM_REQUIRED")
    target_index = next((
        index for index, grade in enumerate(program.grades)
        if target in {capability.id for capability in grade.capabilities}
    ), None)
    if target_index is None:
        raise ValueError("LEARNING_EXPERIMENT_UNKNOWN_TARGET_GRADE")
    graduated = set(graduated_grades)
    debt = set(carried_mastery_debt)
    return tuple(sorted(
        capability.id
        for grade in program.grades[:target_index]
        for capability in grade.capabilities
        if grade.id in graduated or capability.id in debt))


def _choose_binary_rows(source, count, policy, rng):
    if count == 0:
        return []
    if not source:
        raise ValueError("LEARNING_EXPERIMENT_MISSING_SOURCE_ROWS")
    groups = {}
    for row in source:
        groups.setdefault(tuple(row["operand_truths"]), []).append(row)
    if count < len(groups):
        raise ValueError("LEARNING_EXPERIMENT_BINARY_PATTERN_CAPACITY")
    chosen = []
    for pattern in sorted(groups):
        options = list(groups[pattern])
        if policy.get("depth", 1) >= 3:
            options.sort(key=lambda row: (-len(row["tokens"]), row["id"]))
            chosen.append(options[0])
        else:
            chosen.append(rng.choice(options))

    remaining = count-len(chosen)
    pools = {gold: [row for row in source if row["gold"] == gold]
             for gold in ("FALSE", "TRUE")}
    if any(not pool for pool in pools.values()):
        raise ValueError("LEARNING_EXPERIMENT_BINARY_CLASS_MISSING")
    if policy.get("depth", 1) >= 3:
        for pool in pools.values():
            pool.sort(key=lambda row: (-len(row["tokens"]), row["id"]))
    else:
        for pool in pools.values():
            rng.shuffle(pool)
    used = {row["id"] for row in chosen}
    counts = {gold: sum(row["gold"] == gold for row in chosen)
              for gold in pools}
    while remaining:
        gold = min(pools, key=lambda item: (counts[item], item))
        options = [row for row in pools[gold] if row["id"] not in used]
        if not options:
            options = pools[gold]
        row = options[0] if policy.get("depth", 1) >= 3 else rng.choice(options)
        chosen.append(row)
        used.add(row["id"])
        counts[gold] += 1
        remaining -= 1
    rng.shuffle(chosen)
    return chosen


def _choose_typed_rows(source, count, policy, rng):
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
        # Sample certified input-token depth; this does not claim AST depth.
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


def reserve_weakness_targets(chosen: list[dict],
                             targets: list[dict]) -> tuple[list[dict], tuple[dict, ...]]:
    """Replace generic current rows with weak semantics without changing batch size."""
    result = list(chosen)
    consumed = set()
    delivered = []
    for target in targets:
        existing = next((
            index for index, row in enumerate(result)
            if index not in consumed and row["id"] == target["id"]
        ), None)
        if existing is not None:
            consumed.add(existing)
            delivered.append(target)
            continue

        pattern = target.get("operand_truths")
        answer_kind = target.get("answer_kind", "binary")
        replacement = None
        if isinstance(pattern, list):
            replacement = next((
                index for index, row in enumerate(result)
                if index not in consumed and row.get("operand_truths") == pattern
            ), None)
        if replacement is None and answer_kind == "binary":
            replacement = next((
                index for index, row in enumerate(result)
                if index not in consumed and row.get("gold") == target.get("gold")
            ), None)
        if replacement is None:
            replacement = next((
                index for index, row in enumerate(result)
                if index not in consumed and
                row.get("answer_kind", "binary") == answer_kind
            ), None)
        if replacement is None:
            replacement = next((
                index for index in range(len(result)) if index not in consumed
            ), None)
        if replacement is None:
            raise ValueError(WeaknessTargetError.LEARNING_EXPERIMENT_WEAKNESS_TARGET_CAPACITY_DRIFT.value)
        result[replacement] = target
        consumed.add(replacement)
        delivered.append(target)
    return result, tuple(delivered)


def select_source_lesson(current: list[dict], prior: list[dict], policy: dict,
                         *, seed: int, batch_size: int,
                         targets: list[dict] | tuple[dict, ...] = (),
                         target_exposures: Mapping[str, int] | None = None,
                         reserved_support_slots: int = 0
                         ) -> tuple[list[dict], dict]:
    """Make inherited old/contrast/depth knobs effective for every answer type.

    'old' means actual examples originating in already-graduated grades, not
    embedded prerequisites or a source-unverified fixed teaching mix.
    'depth' uses token-count emphasis only when that proxy is named as such.
    Future-grade preview is intentionally inapplicable: never teach new roots.
    """
    if not current or type(batch_size) is not int or batch_size < 2:
        raise ValueError("LEARNING_EXPERIMENT_EMPTY_TYPED_LESSON")
    if (type(reserved_support_slots) is not int or
            not 0 <= reserved_support_slots <= batch_size):
        raise ValueError(WeaknessTargetError.LEARNING_EXPERIMENT_SUPPORT_CAPACITY_INVALID.value)
    rng = random.Random(seed)
    requested_old = int(policy.get("old", 0))
    if not 0 <= requested_old <= 32:
        raise ValueError("LEARNING_EXPERIMENT_INVALID_OLD_POLICY")
    semantic_patterns = sorted({
        tuple(row["operand_truths"]) for row in current
        if isinstance(row.get("operand_truths"), list)
    })
    structured_binary = bool(semantic_patterns) and all(
        isinstance(row.get("operand_truths"), list) for row in current)
    minimum_current = len(semantic_patterns) if structured_binary else 2
    old_count = min(batch_size-minimum_current,
                    round(requested_old*batch_size/32)) if prior else 0
    present_count = batch_size-old_count
    choose_current = _choose_binary_rows if structured_binary else _choose_typed_rows
    current_ids = {row["id"] for row in current}
    if any(row.get("id") not in current_ids for row in targets):
        raise ValueError(WeaknessTargetError.LEARNING_EXPERIMENT_WEAKNESS_TARGET_OUTSIDE_CURRENT.value)
    target_capacity = max(
        0, present_count - min(reserved_support_slots, present_count))
    if targets and not target_capacity:
        target_capacity = 1
    selected_targets = select_weakness_targets(
        targets,
        WeaknessTargetRequest(
            exposures=dict(target_exposures or {}),
            capacity=target_capacity,
        ))
    current_rows = choose_current(current, present_count, policy, rng)
    current_rows, delivered_targets = reserve_weakness_targets(
        current_rows, selected_targets)
    result = current_rows + _choose_typed_rows(prior, old_count, policy, rng)
    rng.shuffle(result)
    delivered_patterns = ({tuple(row["operand_truths"]) for row in result
                           if isinstance(row.get("operand_truths"), list)}
                          if structured_binary else set())
    return ([{**row, "answer_kind": row.get("answer_kind", "binary")}
             for row in result],
            {"effective_old_grade_examples": old_count,
             "requested_old_per_32": requested_old,
             "weakness_targets_available": len(targets),
             "weakness_targets_requested": len(selected_targets),
             "weakness_targets_delivered": len(delivered_targets),
             "weakness_target_ids": [row["id"] for row in delivered_targets],
             "reserved_support_slots": reserved_support_slots,
             "current_semantic_patterns_required": len(semantic_patterns),
             "current_semantic_patterns_delivered": len(delivered_patterns),
             "depth_control": "SOURCE_TOKEN_LENGTH_PROXY" if policy.get("depth", 1) >= 3
                              else "UNBIASED_SOURCE_GROUPS",
             "contrast_control": "SOURCE_GROUP_DIVERSITY" if policy.get("contrast", 0.) >= .5
                                 else "SOURCE_GROUP_RANDOM",
             "preview_control": "NOT_AVAILABLE_UNADMITTED_FUTURE_GRADE"})
