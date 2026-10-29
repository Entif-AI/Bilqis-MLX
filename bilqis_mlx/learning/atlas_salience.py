"""Verified independent ordinal salience, pure attention order and B01 heads."""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum

from ..runtime.model_topology_v2 import expected_bamf_shapes
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from ..semantics.domains import contract_digest
from .salience_contracts import (
    ActionKind, AttentionOption, AuthoritySnapshot, FactOrigin, Metric, NoveltyState,
    ObservationState, Ordinal, SalienceContext, SaliencePolicy, Signal, SignedFact, _invalid,
)


def _verify_inputs(facts, policy, snapshot, context):
    if (not isinstance(facts, tuple) or len(facts) > len(Metric)
            or any(not isinstance(fact, SignedFact) for fact in facts)
            or len({fact.fact_id for fact in facts}) != len(facts)
            or len({fact.metric for fact in facts}) != len(facts)
            or not isinstance(policy, SaliencePolicy) or not isinstance(snapshot, AuthoritySnapshot)
            or not isinstance(context, SalienceContext) or context not in snapshot.contexts
            or policy.semantic_release != context.semantic_release or policy.issued_at > snapshot.as_of):
        _invalid("BAMF_SALIENCE_INPUT_CONTEXT_OR_POLICY_INVALID")
    snapshot.registry.verify_detached(
        policy.source_owner, DependencyRef(DependencyKind.POLICY, "salience-policy:" + policy.policy_id),
        policy.signature_hex, policy.signing_bytes())
    for fact in facts:
        if (fact.context != context or fact.policy_digest != policy.digest()
                or fact.recorded_at > snapshot.as_of or fact.effective_time > snapshot.as_of
                or fact.recorded_at < policy.issued_at):
            _invalid("BAMF_SALIENCE_FACT_CONTEXT_OR_VISIBILITY_DRIFT")
        kind = DependencyKind.SOURCE if fact.origin is FactOrigin.SOURCE else DependencyKind.ARTIFACT
        snapshot.registry.verify_detached(
            fact.source_owner, DependencyRef(kind, "salience-fact:" + fact.fact_id),
            fact.signature_hex, fact.signing_bytes())
        if fact.metric is Metric.NOVELTY_COMPARISON:
            comparison = fact.value
            if (comparison.established_at > fact.observed_at
                    or (comparison.state is ObservationState.EXPECTED_MISSING
                        and (fact.observed_at < comparison.expected_until
                             or snapshot.as_of < comparison.expected_until
                             or (comparison.expected_structure_sha256 is None
                                 and comparison.expected_outcome_sha256 is None)))):
                _invalid("BAMF_SALIENCE_EXPECTATION_CAUSALITY_INVALID")


@dataclass(frozen=True)
class VerifiedSalienceInputs:
    facts: tuple[SignedFact, ...]
    policy: SaliencePolicy
    snapshot: AuthoritySnapshot
    context: SalienceContext

    def __post_init__(self):
        _verify_inputs(self.facts, self.policy, self.snapshot, self.context)

    def digest(self):
        return contract_digest({"schema": "bilqis.c06.verified-inputs/v1", "facts": self.facts,
                                "policy": self.policy.digest(), "context": self.context,
                                "as_of": self.snapshot.as_of, "authority": self.snapshot.registry})


def verify_salience_inputs(raw_facts, policy, authority_snapshot, context) -> VerifiedSalienceInputs:
    return VerifiedSalienceInputs(raw_facts, policy, authority_snapshot, context)


@dataclass(frozen=True)
class MetricEvidence:
    ordinal: Ordinal
    supervised_label: int | None
    origin: FactOrigin | None
    rule_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SalienceEvidence:
    impact: MetricEvidence
    exigency: MetricEvidence
    novelty: MetricEvidence
    basis: VerifiedSalienceInputs
    scope: SalienceContext
    schema_version: str = "bilqis.c06.salience-evidence/v1"


def _novelty_states(comparison):
    if (comparison.state is ObservationState.NOT_REPORTED
            or (comparison.expected_structure_sha256 is None
                and comparison.expected_outcome_sha256 is None)):
        return ()
    if comparison.state is ObservationState.EXPECTED_MISSING:
        return (NoveltyState.EXPECTED_MISSING,)
    if comparison.state is ObservationState.REPORTED_NEGATIVE:
        return (NoveltyState.REPORTED_NEGATIVE,)
    pairs = ((comparison.expected_structure_sha256, comparison.observed_structure_sha256,
              NoveltyState.STRUCTURE_CHANGED),
             (comparison.expected_outcome_sha256, comparison.observed_outcome_sha256,
              NoveltyState.OUTCOME_CHANGED))
    changed = tuple(state for expected, observed, state in pairs
                    if expected is not None and observed is not None and expected != observed)
    if changed:
        return changed
    if (not any(expected is not None for expected, _, _ in pairs)
            or any(expected is not None and observed is None for expected, observed, _ in pairs)):
        return ()
    return (NoveltyState.MATCHED,)


def derive_salience(verified: VerifiedSalienceInputs) -> SalienceEvidence:
    if not isinstance(verified, VerifiedSalienceInputs):
        _invalid("BAMF_SALIENCE_VERIFIED_INPUTS_REQUIRED")
    policy = verified.policy
    by_metric = {fact.metric: fact for fact in verified.facts}
    rules = {rule.metric: rule for rule in policy.numeric_rules}
    def derive(signal):
        facts = tuple(fact for fact in verified.facts if fact.metric.signal is signal)
        fact_ids = tuple(fact.fact_id for fact in facts)
        def unknown(reason):
            explicit = tuple(fact for fact in facts if fact.metric.explicit_unknown)
            return MetricEvidence(Ordinal.UNKNOWN, 0 if explicit else None,
                                  FactOrigin.SOURCE if explicit else None,
                                  ("bilqis.c06.explicit-unknown/v1",) if explicit else (), fact_ids, reason)
        if verified.context.source_family_id not in policy.source_family_ids:
            return MetricEvidence(Ordinal.UNKNOWN, None, None, (), fact_ids, "UNSUPPORTED_SOURCE_FAMILY")
        required = dict(policy.required_metrics)[signal]
        if not set(required) <= set(by_metric):
            return unknown("MISSING_REQUIRED_FACTS")
        values, rule_ids, origins = [], [], []
        unsupported = set()
        for fact in facts:
            if fact.metric.explicit_unknown:
                continue
            if fact.metric is Metric.NOVELTY_COMPARISON:
                states = _novelty_states(fact.value)
                if not states:
                    unsupported.add(fact.metric)
                    continue
                values.extend(dict(policy.novelty_rules)[state] for state in states)
                rule_ids.extend(policy.policy_id + "/" + policy.version + ":novelty:" + state.value
                                for state in states)
            elif fact.metric not in rules:
                unsupported.add(fact.metric)
                continue
            else:
                rule = rules[fact.metric]
                value = fact.value - verified.snapshot.as_of if fact.metric is Metric.DEADLINE_AT else fact.value
                values.append(rule.ordinals[bisect_right(rule.cut_points, value)])
                rule_ids.append(rule.rule_id)
            origins.append(fact.origin)
        if unsupported & set(required) or not values:
            return unknown("UNSUPPORTED_REQUIRED_EVIDENCE")
        ordinal = max(values)
        if ordinal is not Ordinal.UNKNOWN and any(fact.metric.explicit_unknown for fact in facts):
            _invalid("BAMF_SALIENCE_CONTRADICTORY_UNKNOWN_DECLARATION")
        origin = FactOrigin.OUTCOME if FactOrigin.OUTCOME in origins else FactOrigin.SOURCE
        return MetricEvidence(ordinal, int(ordinal), origin, tuple(rule_ids), fact_ids, "VERIFIED_RULE_MAX")
    return SalienceEvidence(derive(Signal.IMPACT), derive(Signal.EXIGENCY), derive(Signal.NOVELTY),
                            verified, verified.context)


@dataclass(frozen=True)
class SalienceLogits:
    impact: object
    exigency: object
    novelty: object


def project_salience_heads(parameters, hidden, topology, extents, *, array_api) -> SalienceLogits:
    specs = tuple(spec for spec in expected_bamf_shapes(topology, extents)
                  if spec.name.startswith(("readout.salience.", "readout.salience_bias.")))
    if (not isinstance(parameters, Mapping) or not hasattr(array_api, "float32")
            or not hasattr(hidden, "shape") or not hidden.shape
            or hidden.shape[-1] != topology.width or getattr(hidden, "dtype", None) != array_api.float32):
        _invalid("BAMF_SALIENCE_HEAD_INPUT_INVALID")
    for spec in specs:
        value = parameters.get(spec.name)
        if (value is None or not hasattr(value, "shape") or tuple(value.shape) != spec.shape
                or getattr(value, "dtype", None) != array_api.float32):
            _invalid("BAMF_SALIENCE_HEAD_PARAMETER_INVALID")
    logits = tuple(hidden @ parameters["readout.salience." + signal.value].T
                   + parameters["readout.salience_bias." + signal.value] for signal in Signal)
    return SalienceLogits(*logits)


class DispatchTier(IntEnum):
    CORRECTION = 0
    URGENT_RELEVANT = 1
    DOWNSTREAM_UNLOCK = 2
    NOVEL_EXPLORATION = 3
    FAIR_ROTATION = 4


@dataclass(frozen=True)
class RankedOptions:
    ordered: tuple[AttentionOption, ...]
    tiers: tuple[tuple[str, DispatchTier], ...]
    held: tuple[tuple[str, str], ...]
    schema_version: str = "bilqis.c06.ranked-options/v1"


def rank_attention_options(options, evidence_by_id, snapshot) -> RankedOptions:
    if (not isinstance(options, tuple) or any(not isinstance(option, AttentionOption) for option in options)
            or len({option.stable_id for option in options}) != len(options)
            or not isinstance(evidence_by_id, Mapping) or not isinstance(snapshot, AuthoritySnapshot)):
        _invalid("BAMF_SALIENCE_ATTENTION_INPUT_INVALID")
    ranked, held = [], []
    for option in options:
        evidence = evidence_by_id.get(option.stable_id)
        if (not isinstance(evidence, SalienceEvidence) or evidence.scope != option.context
                or evidence.basis.snapshot != snapshot or option.context not in snapshot.contexts
                or evidence.basis.digest() != option.salience_inputs_digest
                or derive_salience(evidence.basis) != evidence or option.eligible_since > snapshot.as_of):
            _invalid("BAMF_SALIENCE_ATTENTION_EVIDENCE_DRIFT")
        snapshot.registry.verify_detached(
            option.source_owner, DependencyRef(DependencyKind.ARTIFACT, "salience-option:" + option.stable_id),
            option.signature_hex, option.signing_bytes())
        if option.action_kind in (ActionKind.TEACHING, ActionKind.EXPLORATION):
            if not option.admissible or not option.rights_eligible or not option.ready:
                held.append((option.stable_id, "SOURCE_RIGHTS_OR_PREREQUISITE_HELD"))
                continue
            if option.action_kind is ActionKind.EXPLORATION and not option.exploration_admitted:
                held.append((option.stable_id, "EXPLORATION_NOT_ADMITTED"))
                continue
        if option.required_correction:
            tier = DispatchTier.CORRECTION
        elif option.relevant and evidence.exigency.ordinal >= Ordinal.HIGH:
            tier = DispatchTier.URGENT_RELEVANT
        elif option.ready and option.downstream_unlocks > 0:
            tier = DispatchTier.DOWNSTREAM_UNLOCK
        elif (option.action_kind is ActionKind.EXPLORATION and option.exploration_admitted
              and evidence.novelty.ordinal >= Ordinal.MODERATE):
            tier = DispatchTier.NOVEL_EXPLORATION
        else:
            tier = DispatchTier.FAIR_ROTATION
        ranked.append((tier, option.eligible_since, option.stable_id, option))
    ranked.sort(key=lambda item: item[:3])
    return RankedOptions(tuple(item[3] for item in ranked),
                         tuple((item[2], item[0]) for item in ranked), tuple(sorted(held)))


def salience_priority_features(evidence, capability, scope, teacher_epoch_digest):
    if (not isinstance(evidence, SalienceEvidence)
            or evidence.scope.capability_id != capability or evidence.scope.scope != scope
            or evidence.scope.teacher_epoch_digest != teacher_epoch_digest):
        _invalid("BAMF_SALIENCE_TEACHER_CONTEXT_DRIFT")
    basis = evidence.basis
    verified = verify_salience_inputs(basis.facts, basis.policy, basis.snapshot, basis.context)
    if derive_salience(verified) != evidence:
        _invalid("BAMF_SALIENCE_TEACHER_EVIDENCE_DRIFT")
    metrics = (evidence.impact, evidence.exigency, evidence.novelty)
    return {"schema": "bilqis.c06.teacher-priority-features/v1",
            "policy_digest": basis.policy.digest(),
            "ordinals": [int(metric.ordinal) for metric in metrics],
            "known": [metric.supervised_label is not None for metric in metrics]}



def propose_attention_options(frontier, history):
    from .salience_teacher import propose_attention_options as propose
    return propose(frontier, history)
