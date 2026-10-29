"""Bounded Teacher vNext selection over the current Factory teacher evidence.

The historical vNext branch maintained a separate outcome model. The Factory replay
does not restore that authority. Instead, it derives the same bounded canary decision
from the current contextual teacher evidence, while #333 remains the canonical
proposal -> delivery -> outcome -> cost record.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
import json
from bilqis_mlx.errors import ErrorBus, SCHOOL

from .teacher_strategy_population import effective_policy_key, BAMF_SUCCESSOR_SELECTION


SCHEMA = "bilqis.teacher-vnext-canary/factory-replay-v1"
SELECTION_POLICY = "bilqis.mlx.teacher-selection/349-replay-v2"
CANARY_EVERY_N_VISITS = 4
MINIMUM_EVIDENCE_OBSERVATIONS = 8
MINIMUM_RETAINED_OBSERVATIONS = 1
EXPLORATION_WEIGHT = .20


def _parse_context(key: str):
    try:
        capability, phase, scope = key.split("|", 2)
    except ValueError:
        return None
    return capability, phase, scope


def _matches(level, *, candidate_capability, candidate_phase,
             target_capability, target_phase):
    candidate_grade = candidate_capability.partition(".")[0]
    target_grade = target_capability.partition(".")[0]
    if level == "EXACT":
        return (candidate_capability == target_capability and
                candidate_phase == target_phase)
    if level == "CAPABILITY":
        return candidate_capability == target_capability
    if level == "GRADE_PHASE":
        return candidate_grade == target_grade and candidate_phase == target_phase
    if level == "GRADE":
        return candidate_grade == target_grade
    return False


def _aggregate(teacher, *, capability, phase, curriculum_scope,
               allowed_effective_policy_keys):
    strategies = teacher.get("strategies", {})
    contexts = teacher.get("causal_experiment", {}).get("contexts", {})
    allowed = set(allowed_effective_policy_keys)
    for level in ("EXACT", "CAPABILITY", "GRADE_PHASE", "GRADE"):
        rows = {}
        for context_key, scope in contexts.items():
            parsed = _parse_context(context_key)
            if parsed is None or not isinstance(scope, dict):
                continue
            candidate_capability, candidate_phase, candidate_scope = parsed
            if candidate_scope != curriculum_scope or not _matches(
                    level, candidate_capability=candidate_capability,
                    candidate_phase=candidate_phase,
                    target_capability=capability, target_phase=phase):
                continue
            for policy_key, record in scope.items():
                policy = strategies.get(policy_key)
                if not isinstance(policy, dict) or not isinstance(record, dict):
                    continue
                effective = effective_policy_key(policy)
                if effective not in allowed:
                    continue
                row = rows.setdefault(effective, {
                    "trials": 0, "retained": 0, "unsafe": 0,
                    "reward_sum": 0., "target_delta_sum": 0.,
                    "protected_net_delta_sum": 0.,
                    "worst_protected_loss_sum": 0.,
                    "attempted_steps_sum": 0., "members": set(),
                })
                trials = int(record.get("trials", 0))
                row["trials"] += trials
                row["retained"] += int(record.get("retained", 0))
                row["unsafe"] += int(record.get("unsafe", 0))
                row["reward_sum"] += float(record.get("reward_sum", 0.))
                row["target_delta_sum"] += float(
                    record.get("target_delta_sum", max(0., float(record.get("reward_sum", 0.)))))
                row["protected_net_delta_sum"] += float(
                    record.get("protected_net_delta_sum", 0.))
                row["worst_protected_loss_sum"] += float(
                    record.get("worst_protected_loss_sum", 0.))
                row["attempted_steps_sum"] += float(
                    record.get("attempted_steps_sum", 16 * trials))
                row["members"].add(policy_key)
        supported = {
            key: value for key, value in rows.items()
            if value["trials"] >= MINIMUM_EVIDENCE_OBSERVATIONS and
            value["retained"] >= MINIMUM_RETAINED_OBSERVATIONS
        }
        if supported:
            return level, supported
    return "PRIOR", {}


def _score(row, rng):
    trials = row["trials"]
    retained = row["retained"]
    sampled_retention = rng.betavariate(retained + 1, trials - retained + 1)
    target = max(0., row["target_delta_sum"] / trials)
    protected_risk = max(0., -row["protected_net_delta_sum"] / trials)
    protected_risk += row["worst_protected_loss_sum"] / trials
    cost = max(1., row["attempted_steps_sum"] / trials)
    uncertainty = 1. / math.sqrt(trials + 1)
    acquisition = (
        sampled_retention * max(.1, target) / cost -
        protected_risk / cost +
        EXPLORATION_WEIGHT * uncertainty / cost)
    return acquisition, sampled_retention


def select_canary(teacher: dict, *, capability: str, phase: str,
                  curriculum_scope: str, candidate_ordinal: int, rng,
                  active_effective_policy_keys, inventory,
                  effective_policy_penalties=None) -> dict:
    """Return an evidence-backed existing policy on the bounded 1-in-4 cadence."""
    scheduled = candidate_ordinal % CANARY_EVERY_N_VISITS == 0
    base = {
        "schema": SCHEMA,
        "policy_version": "teacher-vnext-canary/v1",
        "candidate_ordinal": candidate_ordinal,
        "scheduled": scheduled,
        "actual_authority_changed": False,
    }
    if not scheduled:
        return {**base, "status": "NOT_SCHEDULED", "policy_key": None}
    level, supported = _aggregate(
        teacher, capability=capability, phase=phase,
        curriculum_scope=curriculum_scope,
        allowed_effective_policy_keys=active_effective_policy_keys)
    if not supported:
        return {
            **base, "status": "FALLBACK_UNDERPOWERED", "policy_key": None,
            "evidence_level": level,
        }
    ranked = []
    penalties = effective_policy_penalties or {}
    for effective, evidence in supported.items():
        acquisition, sampled_retention = _score(evidence, rng)
        acquisition -= float(penalties.get(effective, 0.))
        ranked.append((acquisition, sampled_retention, effective, evidence))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    acquisition, sampled_retention, selected_effective, evidence = ranked[0]
    members = tuple(sorted(set(inventory.get(selected_effective, ())) & evidence["members"]))
    if not members:
        members = tuple(sorted(inventory.get(selected_effective, ())))
    if not members:
        return {
            **base, "status": "FALLBACK_UNDERPOWERED", "policy_key": None,
            "evidence_level": level,
        }
    policy_key = max(
        members,
        key=lambda key: (
            int(teacher.get("causal_experiment", {}).get("contexts", {}).get(
                capability + "|" + phase + "|" + curriculum_scope, {}).get(
                    key, {}).get("retained", 0)),
            key,
        ))
    public_evidence = {key: value for key, value in evidence.items() if key != "members"}
    return {
        **base,
        "status": "SELECTED",
        "policy_key": policy_key,
        "selected_effective_policy_key": selected_effective,
        "evidence_level": level,
        "evidence": public_evidence,
        "sampled_retention_probability": sampled_retention,
        "acquisition_score": acquisition,
        "actual_authority_changed": True,
    }




@dataclass(frozen=True)
class TeacherEpoch:
    prior_region: str
    current_region: str
    student_sha256: str
    replay_head: str
    prior_json: str
    current_json: str
    schema: str = "bilqis.bamf.teacher-epoch/v1"

    def teacher(self) -> dict:
        return json.loads(self.current_json)

    def prior_teacher(self) -> dict:
        return json.loads(self.prior_json)


def bind_teacher_successor(prior_teacher, new_student, replay_contract) -> TeacherEpoch:
    """Preserve replay priors while isolating a fresh learner's causal counters."""
    def invalid(reason):
        ErrorBus.raise_(SCHOOL.BAMF_TEACHER.INVALID, reason=reason)
    if not all(isinstance(value, dict) for value in (prior_teacher, new_student, replay_contract)):
        invalid('BINDING_RECORD_REQUIRED')
    if (new_student.get('schema') != 'bilqis.bamf.student-reference/v1' or
            replay_contract.get('schema') != 'bilqis.bamf.teacher-binding/v1'):
        invalid('BINDING_SCHEMA_INVALID')
    student = new_student.get('student_sha256')
    region, prior_region = new_student.get('region'), replay_contract.get('prior_region')
    head = replay_contract.get('source_head')
    if (not isinstance(student, str) or len(student) != 64 or any(c not in '0123456789abcdef' for c in student)
            or not isinstance(region, str) or not region or not isinstance(prior_region, str) or not prior_region
            or region == prior_region or head != 'd21797e72365bf93ea7cad3a4ef9020ec9817f23'
            or not isinstance(prior_teacher.get('strategies'), dict) or not prior_teacher['strategies']):
        invalid('IDENTITY_OR_REPLAY_INVALID')
    try:
        prior_json = json.dumps(prior_teacher, sort_keys=True, allow_nan=False)
        current = json.loads(prior_json)
    except (ValueError, TypeError):
        invalid('TEACHER_NOT_SERIALIZABLE')
    channel = current.get('causal_experiment', {})
    if not isinstance(channel, dict) or not isinstance(channel.get('student_policy_epoch', {}), dict):
        invalid('TEACHER_RECORD_INVALID')
    if any(not isinstance(policy, dict) or not policy for policy in current['strategies'].values()):
        invalid('STRATEGY_RECORD_INVALID')
    for policy in current['strategies'].values():
        try:
            effective_policy_key(policy)
        except (ValueError, TypeError):
            invalid('STRATEGY_RECORD_INVALID')
    prior_checkpoint = channel.get('student_policy_epoch', {}).get('student_sha256')
    if prior_checkpoint == student:
        invalid('SUCCESSOR_MUST_BE_DISTINCT')
    current['selection_contract'] = BAMF_SUCCESSOR_SELECTION
    current['grade_stats'] = {}
    current['causal_experiment'] = {
        'contexts': {}, 'events': 0,
        'student_policy_epoch': {'student_sha256': student, 'contexts': {}, 'unretained_contexts': {}},
    }
    return TeacherEpoch(prior_region, region, student, head, prior_json,
                        json.dumps(current, sort_keys=True, allow_nan=False))
