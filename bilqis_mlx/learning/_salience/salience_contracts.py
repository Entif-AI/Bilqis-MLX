"""Immutable C06 evidence, policy and attention-option boundaries."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum, IntEnum
import hashlib
import json
import re

from ..errors import ErrorBus, SCHOOL
from ..runtime.atlas_revalidation import SourceAuthorityRegistry


def _invalid(reason):
    ErrorBus.raise_(SCHOOL.BAMF_SALIENCE.INVALID, reason=reason)


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _name(value):
    return isinstance(value, str) and bool(value)


def _time(value):
    return type(value) is int and value >= 0


def _signature(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{128}", value) is not None


def _signing_bytes(record):
    payload = asdict(record)
    del payload["signature_hex"]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


class Ordinal(IntEnum):
    UNKNOWN = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    CRITICAL = 4


class Signal(str, Enum):
    IMPACT = "impact"
    EXIGENCY = "exigency"
    NOVELTY = "novelty"


class FactOrigin(str, Enum):
    SOURCE = "SOURCE"
    OUTCOME = "OUTCOME"


class Metric(str, Enum):
    DECLARED_IMPACT = "impact.declared"
    DOWNSTREAM_COUNT = "impact.downstream"
    COVERAGE_COUNT = "impact.coverage"
    DEADLINE_AT = "exigency.deadline"
    BLOCKED_COUNT = "exigency.blocked"
    REPAIR_COUNT = "exigency.repair"
    NOVELTY_COMPARISON = "novelty.comparison"
    IMPACT_UNKNOWN = "impact.unknown"
    EXIGENCY_UNKNOWN = "exigency.unknown"
    NOVELTY_UNKNOWN = "novelty.unknown"

    @property
    def signal(self):
        return Signal(self.value.partition(".")[0])

    @property
    def explicit_unknown(self):
        return self in (Metric.IMPACT_UNKNOWN, Metric.EXIGENCY_UNKNOWN, Metric.NOVELTY_UNKNOWN)


class ObservationState(str, Enum):
    NOT_REPORTED = "NOT_REPORTED"
    OBSERVED = "OBSERVED"
    EXPECTED_MISSING = "EXPECTED_MISSING"
    REPORTED_NEGATIVE = "REPORTED_NEGATIVE"


class NoveltyState(str, Enum):
    MATCHED = "MATCHED"
    STRUCTURE_CHANGED = "STRUCTURE_CHANGED"
    OUTCOME_CHANGED = "OUTCOME_CHANGED"
    EXPECTED_MISSING = "EXPECTED_MISSING"
    REPORTED_NEGATIVE = "REPORTED_NEGATIVE"


@dataclass(frozen=True)
class SalienceContext:
    semantic_release: str
    source_binding_digest: str
    rights_epoch: int
    correction_generation: int
    capability_id: str
    capability_epoch: str
    scope: str
    source_family_id: str
    generation_digest: str
    teacher_epoch_digest: str

    def __post_init__(self):
        if (not all(_sha(value) for value in (
                self.semantic_release, self.source_binding_digest, self.capability_epoch,
                self.generation_digest, self.teacher_epoch_digest))
                or not all(_name(value) for value in (
                    self.capability_id, self.scope, self.source_family_id))
                or not all(_time(value) for value in (self.rights_epoch, self.correction_generation))):
            _invalid("BAMF_SALIENCE_CONTEXT_INVALID")


@dataclass(frozen=True)
class NoveltyComparison:
    """A source expectation window ends at expected_until (exclusive)."""
    expectation_id: str
    expected_structure_sha256: str | None
    expected_outcome_sha256: str | None
    established_at: int
    expected_until: int
    observed_event_id: str | None
    observed_structure_sha256: str | None
    observed_outcome_sha256: str | None
    state: ObservationState

    def __post_init__(self):
        if (not _name(self.expectation_id)
                or not isinstance(self.state, ObservationState)
                or not _time(self.established_at) or not _time(self.expected_until)
                or self.expected_until < self.established_at
                or any(value is not None and not _sha(value) for value in (
                    self.expected_structure_sha256, self.expected_outcome_sha256,
                    self.observed_structure_sha256, self.observed_outcome_sha256))
                or (self.observed_event_id is not None and not _name(self.observed_event_id))
                or (self.state in (ObservationState.OBSERVED, ObservationState.REPORTED_NEGATIVE)
                    and self.observed_event_id is None)
                or (self.state in (ObservationState.NOT_REPORTED, ObservationState.EXPECTED_MISSING)
                    and any(value is not None for value in (
                        self.observed_event_id, self.observed_structure_sha256, self.observed_outcome_sha256)))):
            _invalid("BAMF_SALIENCE_EXPECTATION_INVALID")


@dataclass(frozen=True)
class MetricRule:
    metric: Metric
    units: str
    cut_points: tuple[int, ...]
    ordinals: tuple[Ordinal, ...]
    rule_id: str

    def __post_init__(self):
        if (not isinstance(self.metric, Metric) or self.metric.explicit_unknown
                or self.metric is Metric.NOVELTY_COMPARISON or not _name(self.rule_id)
                or not isinstance(self.cut_points, tuple)
                or any(type(value) is not int for value in self.cut_points)
                or self.cut_points != tuple(sorted(set(self.cut_points)))
                or not isinstance(self.ordinals, tuple)
                or len(self.ordinals) != len(self.cut_points) + 1
                or any(not isinstance(value, Ordinal) for value in self.ordinals)):
            _invalid("BAMF_SALIENCE_RULE_INVALID")
        expected_unit = ("ordinal-index" if self.metric is Metric.DECLARED_IMPACT
                         else "seconds-until-deadline" if self.metric is Metric.DEADLINE_AT else "count")
        if (self.units != expected_unit
                or (self.metric is Metric.DECLARED_IMPACT
                    and (self.cut_points != (1, 2, 3, 4) or self.ordinals != tuple(Ordinal)))
                or (self.metric is not Metric.DECLARED_IMPACT and Ordinal.UNKNOWN in self.ordinals)):
            _invalid("BAMF_SALIENCE_RULE_UNITS_OR_UNKNOWN_INVALID")


@dataclass(frozen=True)
class SaliencePolicy:
    policy_id: str
    version: str
    semantic_release: str
    source_family_ids: tuple[str, ...]
    numeric_rules: tuple[MetricRule, ...]
    novelty_rules: tuple[tuple[NoveltyState, Ordinal], ...]
    required_metrics: tuple[tuple[Signal, tuple[Metric, ...]], ...]
    issued_at: int
    source_owner: str
    signature_hex: str
    schema_version: str = "bilqis.c06.salience-policy/v1"

    def __post_init__(self):
        if (not all(_name(value) for value in (self.policy_id, self.version, self.source_owner))
                or not _sha(self.semantic_release) or not _time(self.issued_at)
                or not _signature(self.signature_hex)
                or not isinstance(self.source_family_ids, tuple) or not self.source_family_ids
                or any(not _name(value) for value in self.source_family_ids)
                or len(set(self.source_family_ids)) != len(self.source_family_ids)
                or not isinstance(self.numeric_rules, tuple)
                or any(not isinstance(rule, MetricRule) for rule in self.numeric_rules)
                or len({rule.metric for rule in self.numeric_rules}) != len(self.numeric_rules)
                or len({rule.rule_id for rule in self.numeric_rules}) != len(self.numeric_rules)
                or not isinstance(self.novelty_rules, tuple)
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or not isinstance(pair[0], NoveltyState) or not isinstance(pair[1], Ordinal)
                       or pair[1] is Ordinal.UNKNOWN for pair in self.novelty_rules)
                or len(self.novelty_rules) != len(NoveltyState)
                or set(dict(self.novelty_rules)) != set(NoveltyState)
                or not isinstance(self.required_metrics, tuple)
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or not isinstance(pair[0], Signal) or not isinstance(pair[1], tuple)
                       or not pair[1] or len(set(pair[1])) != len(pair[1])
                       or any(not isinstance(metric, Metric) or metric.signal is not pair[0]
                              or metric.explicit_unknown for metric in pair[1])
                       for pair in self.required_metrics)
                or len(self.required_metrics) != len(Signal)
                or set(dict(self.required_metrics)) != set(Signal)
                or self.schema_version != "bilqis.c06.salience-policy/v1"):
            _invalid("BAMF_SALIENCE_POLICY_INVALID")

    def signing_bytes(self):
        return _signing_bytes(self)

    def digest(self):
        return hashlib.sha256(self.signing_bytes()).hexdigest()


@dataclass(frozen=True)
class SignedFact:
    fact_id: str
    metric: Metric
    value: int | NoveltyComparison
    origin: FactOrigin
    context: SalienceContext
    policy_digest: str
    source_receipt_sha256: str
    source_time: int
    effective_time: int
    observed_at: int
    recorded_at: int
    source_owner: str
    signature_hex: str
    schema_version: str = "bilqis.c06.salience-fact/v1"

    def __post_init__(self):
        if (not _name(self.fact_id) or not isinstance(self.metric, Metric)
                or not isinstance(self.origin, FactOrigin) or not isinstance(self.context, SalienceContext)
                or not _sha(self.policy_digest) or not _sha(self.source_receipt_sha256)
                or not all(_time(value) for value in (
                    self.source_time, self.effective_time, self.observed_at, self.recorded_at))
                or not self.source_time <= self.observed_at <= self.recorded_at
                or not _name(self.source_owner) or not _signature(self.signature_hex)
                or self.schema_version != "bilqis.c06.salience-fact/v1"):
            _invalid("BAMF_SALIENCE_FACT_INVALID")
        if self.metric is Metric.NOVELTY_COMPARISON:
            valid = isinstance(self.value, NoveltyComparison)
        else:
            valid = type(self.value) is int and self.value >= 0
            if self.metric is Metric.DECLARED_IMPACT:
                valid = valid and self.value <= 4 and self.origin is FactOrigin.SOURCE
            elif self.metric.explicit_unknown:
                valid = valid and self.value == 0 and self.origin is FactOrigin.SOURCE
        if not valid:
            _invalid("BAMF_SALIENCE_FACT_VALUE_INVALID")

    def signing_bytes(self):
        return _signing_bytes(self)


@dataclass(frozen=True)
class AuthoritySnapshot:
    contexts: tuple[SalienceContext, ...]
    as_of: int
    registry: SourceAuthorityRegistry

    def __post_init__(self):
        if (not isinstance(self.contexts, tuple) or not self.contexts
                or any(not isinstance(context, SalienceContext) for context in self.contexts)
                or len({(context.capability_id, context.scope) for context in self.contexts}) != len(self.contexts)
                or not _time(self.as_of) or not isinstance(self.registry, SourceAuthorityRegistry)):
            _invalid("BAMF_SALIENCE_AUTHORITY_SNAPSHOT_INVALID")


class ActionKind(str, Enum):
    TEACHING = "TEACHING"
    EXPLORATION = "EXPLORATION"
    CORRECTION = "CORRECTION"
    PROCEDURE_REPAIR = "PROCEDURE_REPAIR"


@dataclass(frozen=True)
class AttentionOption:
    stable_id: str
    context: SalienceContext
    salience_inputs_digest: str
    action_kind: ActionKind
    eligible_since: int
    admissible: bool
    rights_eligible: bool
    ready: bool
    relevant: bool
    downstream_unlocks: int
    required_correction: bool
    exploration_admitted: bool
    source_owner: str
    signature_hex: str
    schema_version: str = "bilqis.c06.attention-option/v1"

    def __post_init__(self):
        if (not _name(self.stable_id) or not isinstance(self.context, SalienceContext)
                or not _sha(self.salience_inputs_digest) or not isinstance(self.action_kind, ActionKind)
                or not _time(self.eligible_since) or not _time(self.downstream_unlocks)
                or any(type(value) is not bool for value in (
                    self.admissible, self.rights_eligible, self.ready, self.relevant,
                    self.required_correction, self.exploration_admitted))
                or (self.required_correction and self.action_kind not in (
                    ActionKind.CORRECTION, ActionKind.PROCEDURE_REPAIR))
                or not _name(self.source_owner) or not _signature(self.signature_hex)
                or self.schema_version != "bilqis.c06.attention-option/v1"):
            _invalid("BAMF_SALIENCE_ATTENTION_OPTION_INVALID")

    def signing_bytes(self):
        return _signing_bytes(self)
