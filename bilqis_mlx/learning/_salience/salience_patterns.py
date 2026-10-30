"""Versioned event/cluster/pattern/trend evidence with source-rights precedence."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from ..semantics.domains import contract_digest
from .salience_contracts import AuthoritySnapshot, FactOrigin, Ordinal, _invalid, _name, _sha, _signature, _signing_bytes, _time
from .salience_history import SalienceEvent, SalienceHistory, _partition, completed_windows


@dataclass(frozen=True)
class AggregationPolicy:
    policy_id: str
    version: str
    window_policy_digest: str
    pattern_min_lineages: int
    trend_min_windows: int
    trend_min_new_lineages: int
    issued_at: int
    source_owner: str
    signature_hex: str
    rule_id: str = field(default='COMPLETED_WINDOW_UNION_UNIQUE_LINEAGES/v1', init=False)
    schema_version: str = field(default='bilqis.c06.aggregation-policy/v1', init=False)

    def __post_init__(self):
        if (not all(_name(value) for value in (self.policy_id, self.version, self.source_owner))
                or not _sha(self.window_policy_digest) or not _signature(self.signature_hex)
                or not _time(self.issued_at)
                or any(type(value) is not int or value < minimum for value, minimum in (
                    (self.pattern_min_lineages, 2), (self.trend_min_windows, 2), (self.trend_min_new_lineages, 1)))):
            _invalid('BAMF_SALIENCE_AGGREGATION_POLICY_INVALID')

    def signing_bytes(self):
        return _signing_bytes(self)

    def digest(self):
        return contract_digest(self)


@dataclass(frozen=True)
class ObservationAnnotation:
    annotation_id: str
    event_digest: str
    conjecture_digest: str
    alternative_explanation_digests: tuple[str, ...]
    source_owner: str
    signature_hex: str
    schema_version: str = field(default='bilqis.c06.observation-annotation/v1', init=False)

    def __post_init__(self):
        if (not _name(self.annotation_id) or not _name(self.source_owner)
                or not _sha(self.event_digest) or not _sha(self.conjecture_digest)
                or not _signature(self.signature_hex)
                or not isinstance(self.alternative_explanation_digests, tuple)
                or any(not _sha(value) for value in self.alternative_explanation_digests)
                or self.alternative_explanation_digests != tuple(sorted(set(self.alternative_explanation_digests)))):
            _invalid('BAMF_SALIENCE_ANNOTATION_INVALID')

    def signing_bytes(self):
        return _signing_bytes(self)


@dataclass(frozen=True)
class WindowCluster:
    cluster_id: str
    window_id: str
    partition: tuple
    structure_sha256: str
    defect_sha256: str
    events: tuple[SalienceEvent, ...]
    lineage_ids: tuple[str, ...]
    rule_id: str


@dataclass(frozen=True)
class CandidatePattern:
    pattern_id: str
    rule_id: str
    window_ids: tuple[str, ...]
    events: tuple[SalienceEvent, ...]
    lineage_ids: tuple[str, ...]
    independent_lineages: int
    annotations: tuple[ObservationAnnotation, ...]
    alternative_explanation_digests: tuple[str, ...]
    missing_annotation_event_ids: tuple[str, ...]
    observed_time_bounds: tuple[int, int]
    evidence_digest: str
    status: str = field(default='CONJECTURE', init=False)
    source_gold: bool = field(default=False, init=False)
    qualified_for_teaching: bool = field(default=False, init=False)
    nomination: str = field(default='PROCEDURE_REPAIR_INVESTIGATION', init=False)


@dataclass(frozen=True)
class TrendPoint:
    window_id: str
    new_lineages: int
    cumulative_lineages: int
    lineage_ids: tuple[str, ...]


@dataclass(frozen=True)
class PatternTrend:
    pattern_id: str
    rule_id: str
    points: tuple[TrendPoint, ...]
    supported: bool


@dataclass(frozen=True)
class SalienceAggregation:
    policy_digest: str
    clusters: tuple[WindowCluster, ...]
    patterns: tuple[CandidatePattern, ...]
    trends: tuple[PatternTrend, ...]
    investigation_pattern_ids: tuple[str, ...]
    holds: tuple[tuple[str, str], ...]
    annotations: tuple[ObservationAnnotation, ...]
    schema_version: str = field(default='bilqis.c06.salience-aggregation/v1', init=False)


def _current_authorized(snapshot, historical_registry, owner, kind, key):
    historical = next((item for item in historical_registry.keys if item.owner_id == owner), None)
    current = next((item for item in snapshot.registry.keys if item.owner_id == owner), None)
    return (historical is not None and current is not None
            and historical.public_key_hex == current.public_key_hex
            and any(scope.kind is kind and key.startswith(scope.key_prefix) for scope in current.allowed_scopes))


def _event_current(event, history, snapshot):
    basis = event.evidence.basis
    if (event.observed_at > snapshot.as_of
            or not any(_partition(context) == _partition(basis.context) for context in snapshot.contexts)):
        return False
    claims = [(history.policy.source_owner, DependencyKind.POLICY, 'salience-policy:' + history.policy.policy_id),
              (event.source_owner, DependencyKind.ARTIFACT, 'salience-event:' + event.event_id),
              (basis.policy.source_owner, DependencyKind.POLICY, 'salience-policy:' + basis.policy.policy_id)]
    claims.extend((fact.source_owner, DependencyKind.SOURCE if fact.origin is FactOrigin.SOURCE
                   else DependencyKind.ARTIFACT, 'salience-fact:' + fact.fact_id) for fact in basis.facts)
    return all(_current_authorized(snapshot, basis.snapshot.registry, *claim) for claim in claims)


def aggregate_salience_patterns(history, policy, annotations, authority_snapshot):
    if (not isinstance(history, SalienceHistory) or not isinstance(policy, AggregationPolicy)
            or not isinstance(authority_snapshot, AuthoritySnapshot)
            or not isinstance(annotations, tuple)
            or any(not isinstance(item, ObservationAnnotation) for item in annotations)
            or policy.window_policy_digest != history.policy.digest()
            or policy.issued_at > authority_snapshot.as_of):
        _invalid('BAMF_SALIENCE_AGGREGATION_INPUT_INVALID')
    # Historical corruption is an error. Current revocation is a distinct hold below.
    SalienceHistory(history.policy, history.events)
    authority_snapshot.registry.verify_detached(policy.source_owner,
        DependencyRef(DependencyKind.POLICY, 'salience-policy:' + policy.policy_id),
        policy.signature_hex, policy.signing_bytes())
    event_by_digest = {event.digest(): event for event in history.events}
    by_id = {}
    for annotation in annotations:
        if (annotation.event_digest not in event_by_digest
                or (annotation.annotation_id in by_id and by_id[annotation.annotation_id] != annotation)):
            _invalid('BAMF_SALIENCE_ANNOTATION_REFERENCE_OR_ID_DRIFT')
        authority_snapshot.registry.verify_detached(annotation.source_owner,
            DependencyRef(DependencyKind.ARTIFACT, 'salience-annotation:' + annotation.annotation_id),
            annotation.signature_hex, annotation.signing_bytes())
        by_id[annotation.annotation_id] = annotation
    annotations = tuple(by_id[key] for key in sorted(by_id))
    clusters, grouped = [], defaultdict(list)
    for window in completed_windows(history):
        groups = defaultdict(list)
        for event in window.events:
            if (event.defect_present is True and event.defect_sha256 is not None
                    and event.evidence.impact.ordinal is Ordinal.LOW
                    and event.evidence.exigency.ordinal is Ordinal.LOW):
                groups[(_partition(event.evidence.scope), event.structure_sha256, event.defect_sha256)].append(event)
        for (partition, structure, defect), events in sorted(groups.items()):
            cluster = WindowCluster(contract_digest((policy.digest(), window.window_id, structure, defect)),
                window.window_id, partition, structure, defect, tuple(events),
                tuple(sorted({event.lineage_id for event in events})), policy.rule_id)
            clusters.append(cluster)
            grouped[(partition, structure, defect)].append(cluster)
    patterns, trends, investigation, holds = [], [], [], []
    for key, group in sorted(grouped.items()):
        events = tuple(event for cluster in group for event in cluster.events)
        lineages = tuple(sorted({event.lineage_id for event in events}))
        if len(lineages) < policy.pattern_min_lineages:
            continue
        pattern_id = contract_digest(('bilqis.c06.candidate-pattern/v1', policy.digest(), key))
        digests = {event.digest() for event in events}
        linked = tuple(item for item in annotations if item.event_digest in digests)
        alternatives = tuple(sorted({value for item in linked for value in item.alternative_explanation_digests}))
        annotated = {item.event_digest for item in linked}
        missing = tuple(event.event_id for event in events if event.digest() not in annotated)
        evidence_digest = contract_digest((policy.digest(), tuple(cluster.cluster_id for cluster in group), events, linked))
        patterns.append(CandidatePattern(pattern_id, policy.rule_id, tuple(cluster.window_id for cluster in group),
            events, lineages, len(lineages), linked, alternatives, missing,
            (min(event.observed_at for event in events), max(event.observed_at for event in events)), evidence_digest))
        seen, points = set(), []
        for cluster in group:
            new = set(cluster.lineage_ids) - seen
            seen.update(cluster.lineage_ids)
            points.append(TrendPoint(cluster.window_id, len(new), len(seen), tuple(sorted(seen))))
        trends.append(PatternTrend(pattern_id, policy.rule_id, tuple(points),
            sum(point.new_lineages >= policy.trend_min_new_lineages for point in points) >= policy.trend_min_windows))
        if all(_event_current(event, history, authority_snapshot) for event in events):
            investigation.append(pattern_id)
        else:
            holds.append((pattern_id, 'CURRENT_SOURCE_OR_RIGHTS_HELD'))
    return SalienceAggregation(policy.digest(), tuple(clusters), tuple(patterns), tuple(trends),
                               tuple(investigation), tuple(holds), annotations)
