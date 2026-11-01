"""A09.3 fail-closed validation for closure and constructive-delta inputs."""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
import hashlib
import json

from .atlas_frontier_closure import (
    CandidateClosure,
    ClosureReason,
    ClosureStatus,
    FrontierClosure,
    SourceHold,
)
from .atlas_frontier_contracts import CurriculumSnapshot, _bytes, _fail
from .executable_release import ExecutableFactoryRelease
from .skos_curriculum import IMPLEMENTATION_UNCOVERED, PROGRAM_BOUND


@dataclass(frozen=True, order=True)
class TargetDeltaProjection:
    """Content-addressed pure forecast of one target's exact constructive shape."""

    semantic_id: str
    obligation_signature: str
    current_release_sha256: str
    current_semantic_catalog_sha256: str
    added_capability_ids: tuple[str, ...]
    introduced_semantic_ids: tuple[str, ...]
    projected_semantic_catalog_sha256: str
    projection_sha256: str

    def __post_init__(self) -> None:
        if (not self.semantic_id
                or not self.added_capability_ids
                or self.added_capability_ids
                   != tuple(sorted(set(self.added_capability_ids)))
                or len(set(self.introduced_semantic_ids))
                   != len(self.introduced_semantic_ids)
                or any(not item for item in self.added_capability_ids)
                or any(not item for item in self.introduced_semantic_ids)
                or any(not _sha(item) for item in (
                    self.obligation_signature, self.current_release_sha256,
                    self.current_semantic_catalog_sha256,
                    self.projected_semantic_catalog_sha256,
                    self.projection_sha256))):
            _fail("BAMF_PLANNER_CONSTRUCTIVE_DELTA_INVALID")

    def expected_digest(self) -> str:
        return hashlib.sha256(_bytes({
            field.name: getattr(self, field.name)
            for field in fields(self) if field.name != "projection_sha256"
        })).hexdigest()

    def verify(self) -> None:
        if self.projection_sha256 != self.expected_digest():
            _fail("BAMF_PLANNER_CONSTRUCTIVE_DELTA_DIGEST_MISMATCH")


def _sha(value: object) -> bool:
    return (type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def catalog_digest(catalog: tuple[str, ...]) -> str:
    return hashlib.sha256(json.dumps(
        catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def obligation_signature(rows) -> str:
    return hashlib.sha256(_bytes(tuple(
        (row.family_id, row.source_evidence_sha256, row.prerequisites)
        for row in rows))).hexdigest()


def snapshot_graph(snapshot: CurriculumSnapshot) -> dict[str, tuple[str, ...]]:
    result = {identity: set() for identity in snapshot.source_eligible_concept_ids}
    for edge in snapshot.prerequisite_edges:
        if edge.semantic_id not in result or edge.prerequisite_semantic_id not in result:
            _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")
        result[edge.semantic_id].add(edge.prerequisite_semantic_id)
    return {key: tuple(sorted(value)) for key, value in result.items()}


def _topological_order(graph: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    visiting, visited, order = set(), set(), []

    def visit(identity: str) -> None:
        if identity in visiting:
            _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")
        if identity in visited:
            return
        visiting.add(identity)
        for prerequisite in graph[identity]:
            visit(prerequisite)
        visiting.remove(identity)
        visited.add(identity)
        order.append(identity)

    for identity in sorted(graph):
        visit(identity)
    return tuple(order)


def _expected_holds(snapshot: CurriculumSnapshot) -> tuple[SourceHold, ...]:
    return tuple(sorted(SourceHold(
        f"{row.domain}/{row.table}/{row.key}", row.reason_code, row.owner)
        for row in snapshot.source_held_rows))


def _direct_status(row, candidate) -> ClosureStatus:
    family_reason = ClosureReason(
        "FAMILY_IMPLEMENTATION_UNCOVERED", f"family:{row.family_id}")
    intrinsic_reasons = tuple(
        reason for reason in candidate.reasons
        if not reason.code.startswith("PREREQUISITE_"))
    if row.implementation_status == IMPLEMENTATION_UNCOVERED:
        if intrinsic_reasons != (family_reason,):
            _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")
        return ClosureStatus.IMPLEMENTATION_UNCOVERED
    if row.implementation_status == PROGRAM_BOUND:
        if intrinsic_reasons:
            _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")
        return ClosureStatus.READY
    _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")


def _validate_candidate_header(row, candidate, prerequisites: tuple[str, ...]) -> None:
    if (candidate.source_evidence_sha256 != row.source_evidence_sha256
            or candidate.prerequisites != prerequisites
            or candidate.status is ClosureStatus.SOURCE_HELD
            or candidate.reasons != tuple(sorted(set(candidate.reasons)))):
        _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")


def _prerequisite_reason_map(candidate, prerequisites: tuple[str, ...]) -> dict[str, ClosureReason]:
    reasons = tuple(
        reason for reason in candidate.reasons
        if reason.code.startswith("PREREQUISITE_"))
    result = {reason.dependency_id: reason for reason in reasons}
    legal_codes = {
        "PREREQUISITE_IMPLEMENTATION_UNCOVERED",
        "PREREQUISITE_WAITING_FOR_EVIDENCE",
    }
    if (len(result) != len(reasons)
            or any(reason.code not in legal_codes
                   or reason.owner != "factory:prerequisite"
                   or reason.dependency_id not in prerequisites
                   for reason in reasons)):
        _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")
    return result


def _dependency_code(
    prerequisite: str,
    statuses: tuple[ClosureStatus, ...],
    reason: ClosureReason | None,
    evidence_wait: dict[str, bool],
) -> str | None:
    if ClosureStatus.IMPLEMENTATION_UNCOVERED in statuses:
        return "PREREQUISITE_IMPLEMENTATION_UNCOVERED"
    if ClosureStatus.WAITING_FOR_EVIDENCE in statuses:
        return "PREREQUISITE_WAITING_FOR_EVIDENCE"
    waiting = reason is not None
    prior = evidence_wait.setdefault(prerequisite, waiting)
    if prior != waiting:
        _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")
    return "PREREQUISITE_WAITING_FOR_EVIDENCE" if waiting else None


def _expected_status(
    direct: ClosureStatus,
    prerequisites: tuple[str, ...],
    prerequisite_reasons: dict[str, ClosureReason],
    grouped_statuses: dict[str, tuple[ClosureStatus, ...]],
    evidence_wait: dict[str, bool],
) -> ClosureStatus:
    expected = direct
    for prerequisite in prerequisites:
        reason = prerequisite_reasons.get(prerequisite)
        code = _dependency_code(
            prerequisite, grouped_statuses[prerequisite], reason, evidence_wait)
        if code is None:
            if reason is not None:
                _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")
            continue
        if reason is None or reason.code != code:
            _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")
        dependency = (ClosureStatus.IMPLEMENTATION_UNCOVERED
                      if code.endswith("IMPLEMENTATION_UNCOVERED")
                      else ClosureStatus.WAITING_FOR_EVIDENCE)
        if dependency is ClosureStatus.IMPLEMENTATION_UNCOVERED:
            expected = dependency
        elif expected is ClosureStatus.READY:
            expected = dependency
    return expected


def validate_closure_structure(snapshot: CurriculumSnapshot, closure: FrontierClosure) -> None:
    """Prove the closure shape is a legal projection of the immutable snapshot."""
    graph = snapshot_graph(snapshot)
    if (closure.constituent_order != _topological_order(graph)
            or closure.source_holds != _expected_holds(snapshot)
            or closure.candidates != tuple(sorted(closure.candidates))
            or closure.source_holds != tuple(sorted(closure.source_holds))):
        _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")

    coverage = {(row.semantic_id, row.family_id): row for row in snapshot.coverage_rows}
    candidates = {(item.semantic_id, item.family_id): item for item in closure.candidates}
    if len(candidates) != len(closure.candidates) or set(candidates) != set(coverage):
        _fail("BAMF_PLANNER_SELECTION_CLOSURE_INCOMPLETE")

    grouped_statuses: dict[str, tuple[ClosureStatus, ...]] = {}
    evidence_wait: dict[str, bool] = {}
    for identity in closure.constituent_order:
        identity_rows = []
        for key in sorted(item for item in coverage if item[0] == identity):
            row, candidate = coverage[key], candidates[key]
            _validate_candidate_header(row, candidate, graph[identity])
            direct = _direct_status(row, candidate)
            prerequisite_reasons = _prerequisite_reason_map(
                candidate, graph[identity])
            expected = _expected_status(
                direct, graph[identity], prerequisite_reasons,
                grouped_statuses, evidence_wait)
            if candidate.status is not expected:
                _fail("BAMF_PLANNER_SELECTION_CLOSURE_INVALID")
            identity_rows.append(candidate.status)
        grouped_statuses[identity] = tuple(identity_rows)


def validate_target_projection(
    current_release: ExecutableFactoryRelease,
    selected_obligations: tuple[CandidateClosure, ...],
    projection: TargetDeltaProjection,
) -> None:
    """Validate one authoritative A09.3 target projection against its release and rows."""
    if (not isinstance(current_release, ExecutableFactoryRelease)
            or type(selected_obligations) is not tuple
            or not selected_obligations
            or any(type(row) is not CandidateClosure for row in selected_obligations)
            or type(projection) is not TargetDeltaProjection
            or any(row.semantic_id != projection.semantic_id
                   for row in selected_obligations)):
        _fail("BAMF_PLANNER_CONSTRUCTIVE_DELTA_INVALID")
    current_release.verify()
    projection.verify()
    expected_catalog = current_release.semantic_catalog + projection.introduced_semantic_ids
    current_capabilities = set(current_release.execution_plan.capability_map)
    current_catalog = set(current_release.semantic_catalog)
    if (projection.obligation_signature != obligation_signature(selected_obligations)
            or projection.current_release_sha256 != current_release.release_sha256
            or projection.current_semantic_catalog_sha256
               != current_release.semantic_catalog_sha256
            or projection.projected_semantic_catalog_sha256
               != catalog_digest(expected_catalog)
            or set(projection.added_capability_ids) & current_capabilities
            or set(projection.introduced_semantic_ids) & current_catalog):
        _fail("BAMF_PLANNER_CONSTRUCTIVE_DELTA_INVALID")


def target_projections(
    closure: FrontierClosure,
    current_release: ExecutableFactoryRelease,
    projections: tuple[TargetDeltaProjection, ...],
) -> dict[str, TargetDeltaProjection]:
    if (type(projections) is not tuple
            or any(type(item) is not TargetDeltaProjection for item in projections)):
        _fail("BAMF_PLANNER_CONSTRUCTIVE_DELTA_INVALID")
    result = {item.semantic_id: item for item in projections}
    groups = {
        identity: tuple(sorted(
            item for item in closure.candidates if item.semantic_id == identity))
        for identity in closure.constituent_order}
    ready = {
        identity for identity, rows in groups.items()
        if rows and all(item.status is ClosureStatus.READY for item in rows)}
    if len(result) != len(projections) or set(result) != ready:
        _fail("BAMF_PLANNER_CONSTRUCTIVE_DELTA_INCOMPLETE")
    for identity, item in result.items():
        validate_target_projection(current_release, groups[identity], item)
    return result
