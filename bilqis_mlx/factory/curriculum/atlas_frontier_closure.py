"""A09.2 deterministic typed prerequisite closure over immutable snapshots."""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
import hashlib

from .atlas_frontier_contracts import CurriculumSnapshot, _bytes, _fail
from .skos_curriculum import SOURCE_FAMILY_ADAPTERS, SourceFamilyAdapter


class ClosureStatus(str, Enum):
    READY = "READY"
    SOURCE_HELD = "SOURCE_HELD"
    IMPLEMENTATION_UNCOVERED = "IMPLEMENTATION_UNCOVERED"
    WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"


@dataclass(frozen=True, order=True)
class ClosureReason:
    code: str
    owner: str
    dependency_id: str = ""


@dataclass(frozen=True, order=True)
class CandidateClosure:
    semantic_id: str
    family_id: str
    source_evidence_sha256: str
    status: ClosureStatus
    prerequisites: tuple[str, ...]
    reasons: tuple[ClosureReason, ...]


@dataclass(frozen=True, order=True)
class SourceHold:
    source_id: str
    reason_code: str
    owner: str
    status: ClosureStatus = ClosureStatus.SOURCE_HELD


@dataclass(frozen=True)
class FrontierClosure:
    snapshot_sha256: str
    rule_families: tuple[str, ...]
    constituent_order: tuple[str, ...]
    candidates: tuple[CandidateClosure, ...]
    source_holds: tuple[SourceHold, ...]
    closure_sha256: str
    schema: str = "bilqis.factory-frontier-closure/v1"

    def expected_digest(self) -> str:
        return hashlib.sha256(_bytes({
            field.name: getattr(self, field.name)
            for field in fields(self) if field.name != "closure_sha256"
        })).hexdigest()

    def verify(self) -> None:
        if self.closure_sha256 != self.expected_digest():
            _fail("BAMF_PLANNER_CLOSURE_DIGEST_MISMATCH")


def _rules(registry: tuple[SourceFamilyAdapter, ...]) -> dict[str, SourceFamilyAdapter]:
    if (type(registry) is not tuple
            or any(type(item) is not SourceFamilyAdapter for item in registry)):
        _fail("BAMF_PLANNER_DOMAIN_RULE_REGISTRY_INVALID")
    result = {item.family_id: item for item in registry}
    if len(result) != len(registry):
        _fail("BAMF_PLANNER_DOMAIN_RULE_REGISTRY_DUPLICATE")
    return result


def _graph(snapshot: CurriculumSnapshot) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    eligible = set(snapshot.source_eligible_concept_ids)
    graph = {item: [] for item in eligible}
    for edge in snapshot.prerequisite_edges:
        if edge.semantic_id not in eligible or edge.prerequisite_semantic_id not in eligible:
            _fail("BAMF_PLANNER_PREREQUISITE_NOT_SOURCE_ELIGIBLE")
        graph[edge.semantic_id].append(edge.prerequisite_semantic_id)
    normalized = {key: tuple(sorted(set(value))) for key, value in graph.items()}
    visiting, visited, order = set(), set(), []

    def visit(identity: str) -> None:
        if identity in visiting:
            _fail("BAMF_PLANNER_PREREQUISITE_CYCLE")
        if identity in visited:
            return
        visiting.add(identity)
        for prerequisite in normalized[identity]:
            visit(prerequisite)
        visiting.remove(identity)
        visited.add(identity)
        order.append(identity)

    for identity in sorted(eligible):
        visit(identity)
    return normalized, tuple(order)


def _source_holds(snapshot: CurriculumSnapshot) -> tuple[SourceHold, ...]:
    return tuple(sorted(SourceHold(
        f"{row.domain}/{row.table}/{row.key}", row.reason_code, row.owner)
        for row in snapshot.source_held_rows))


def _coverage(snapshot: CurriculumSnapshot):
    eligible = set(snapshot.source_eligible_concept_ids)
    families = set(snapshot.required_source_family_ids)
    result = {}
    for row in snapshot.coverage_rows:
        key = (row.semantic_id, row.family_id)
        if (row.semantic_id not in eligible or row.family_id not in families
                or key in result
                or len(row.source_evidence_sha256) != 64
                or any(char not in "0123456789abcdef"
                       for char in row.source_evidence_sha256)):
            _fail("BAMF_PLANNER_COVERAGE_SIGNATURE_INVALID")
        result[key] = row
    if set(snapshot.required_source_family_ids) - {key[1] for key in result}:
        _fail("BAMF_PLANNER_REQUIRED_FAMILY_MISSING")
    return result


def _direct_status(snapshot: CurriculumSnapshot, rules: dict[str, SourceFamilyAdapter]):
    waiting = (set(snapshot.retained_mastery_debt)
               | set(snapshot.unverified_exposed_capability_ids)
               | set(snapshot.unverified_qualified_capability_ids))
    by_candidate = {}
    for row in snapshot.coverage_rows:
        if row.implementation_status == "IMPLEMENTATION_UNCOVERED" or row.family_id not in rules:
            status = ClosureStatus.IMPLEMENTATION_UNCOVERED
        elif row.semantic_id in waiting:
            status = ClosureStatus.WAITING_FOR_EVIDENCE
        else:
            status = ClosureStatus.READY
        by_candidate[(row.semantic_id, row.family_id)] = status
    return by_candidate


def _dependency_status(statuses: tuple[ClosureStatus, ...]) -> ClosureStatus | None:
    if ClosureStatus.IMPLEMENTATION_UNCOVERED in statuses:
        return ClosureStatus.IMPLEMENTATION_UNCOVERED
    if ClosureStatus.WAITING_FOR_EVIDENCE in statuses:
        return ClosureStatus.WAITING_FOR_EVIDENCE
    return None


def _merge_status(current: ClosureStatus, dependency: ClosureStatus) -> ClosureStatus:
    precedence = {
        ClosureStatus.READY: 0,
        ClosureStatus.WAITING_FOR_EVIDENCE: 1,
        ClosureStatus.IMPLEMENTATION_UNCOVERED: 2,
    }
    return max((current, dependency), key=precedence.__getitem__)


def resolve_frontier_closure(
    snapshot: CurriculumSnapshot,
    domain_rule_registry: tuple[SourceFamilyAdapter, ...] = SOURCE_FAMILY_ADAPTERS,
) -> FrontierClosure:
    """Return grade-neutral, constituent-first closure without ranking or admission."""
    if type(snapshot) is not CurriculumSnapshot:
        _fail("BAMF_PLANNER_SNAPSHOT_INPUT_INVALID")
    snapshot.verify()
    rules = _rules(domain_rule_registry)
    graph, order = _graph(snapshot)
    direct = _direct_status(snapshot, rules)
    resolved: dict[str, tuple[ClosureStatus, ...]] = {}
    candidates = []
    rows = _coverage(snapshot)
    for semantic_id in order:
        current = []
        for family_id in sorted(key[1] for key in rows if key[0] == semantic_id):
            row = rows[(semantic_id, family_id)]
            status = direct[(semantic_id, family_id)]
            reasons = []
            if status is ClosureStatus.IMPLEMENTATION_UNCOVERED:
                reasons.append(ClosureReason(
                    "FAMILY_IMPLEMENTATION_UNCOVERED", f"family:{family_id}"))
            elif status is ClosureStatus.WAITING_FOR_EVIDENCE:
                reasons.append(ClosureReason("LEARNING_EVIDENCE_REQUIRED", "learner:evidence"))
            for prerequisite in graph[semantic_id]:
                blocked = _dependency_status(resolved[prerequisite])
                if blocked is not None:
                    status = _merge_status(status, blocked)
                    reasons.append(ClosureReason(
                        "PREREQUISITE_" + blocked.value, "factory:prerequisite", prerequisite))
            candidates.append(CandidateClosure(
                semantic_id, family_id, row.source_evidence_sha256, status,
                graph[semantic_id], tuple(sorted(set(reasons)))))
            current.append(status)
        resolved[semantic_id] = tuple(current)
    provisional = FrontierClosure(
        snapshot.snapshot_sha256, tuple(sorted(rules)), order,
        tuple(sorted(candidates)), _source_holds(snapshot), "0" * 64)
    result = FrontierClosure(
        provisional.snapshot_sha256, provisional.rule_families,
        provisional.constituent_order, provisional.candidates,
        provisional.source_holds, provisional.expected_digest())
    result.verify()
    return result
