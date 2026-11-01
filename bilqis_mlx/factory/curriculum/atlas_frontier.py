"""A09.1a immutable, source-replayed Factory planning snapshot.

This is a pure planning proposal. It does not qualify learning, admit
a staged release, create a source grant or mutate a student.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib

from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import ContextPolicy, SourceFrontier

from bilqis_mlx.factory.candidate_frontier import CandidateFrontierRelease
from .atlas_frontier_contracts import (
    CurriculumSnapshot,
    PlannerBudget,
    PrerequisiteEdge,
    _bytes,
    _evidence_key,
    _fail,
)
from .model import AdmissionReceipt, FactoryRelease, LearningEvidence
from .skos_curriculum import (
    CurriculumCandidateSet,
    LearnedFrontier,
    assert_curriculum_candidate_current,
)

_SHA256_HEX_LENGTH = 64


def _source_edges(candidate: CurriculumCandidateSet) -> tuple[PrerequisiteEdge, ...]:
    eligible = set(candidate.source_eligible_concept_ids)
    if any(
            prerequisite not in eligible
            for lesson in candidate.source_lessons
            for prerequisite in lesson.prerequisite_closure):
        _fail("BAMF_PLANNER_PREREQUISITE_NOT_SOURCE_ELIGIBLE")
    edges = {
        PrerequisiteEdge(
            lesson.semantic_id, prerequisite, lesson.source_evidence_sha256)
        for lesson in candidate.source_lessons
        for prerequisite in lesson.prerequisite_closure
        if prerequisite != lesson.semantic_id
    }
    ordered = tuple(sorted(edges))
    graph = {}
    for edge in ordered:
        graph.setdefault(edge.semantic_id, set()).add(
            edge.prerequisite_semantic_id)
    visited, visiting = set(), set()

    def visit(node: str) -> None:
        if node in visiting:
            _fail("BAMF_PLANNER_PREREQUISITE_CYCLE")
        if node in visited:
            return
        visiting.add(node)
        for parent in sorted(graph.get(node, ())):
            visit(parent)
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return ordered


def _validate_snapshot_inputs(
    candidate: CurriculumCandidateSet, frontier: SourceFrontier,
    policy: ContextPolicy, *, budget: PlannerBudget,
    candidate_frontier_sha256: str = "0" * 64,
    ready_candidate_ids: tuple[str, ...] = (),
    retained_evidence: tuple[LearningEvidence, ...] = (),
    retained_mastery_debt: tuple[str, ...] = (),
    teacher_epoch: int = 0, qualification_epoch: int = 0,
    grade_labels: tuple[str, ...] = (),
) -> None:
    if (type(candidate) is not CurriculumCandidateSet
            or type(frontier) is not SourceFrontier
            or type(policy) is not ContextPolicy
            or type(budget) is not PlannerBudget
            or frontier.rights_epoch != policy.rights_epoch
            or type(retained_evidence) is not tuple
            or any(type(item) is not LearningEvidence
                   for item in retained_evidence)
            or type(retained_mastery_debt) is not tuple
            or any(type(item) is not str or not item
                   for item in retained_mastery_debt)
            or type(grade_labels) is not tuple
            or any(type(item) is not str for item in grade_labels)
            or type(ready_candidate_ids) is not tuple
            or any(type(item) is not str or not item for item in ready_candidate_ids)
            or type(candidate_frontier_sha256) is not str
            or len(candidate_frontier_sha256) != _SHA256_HEX_LENGTH
            or any(char not in "0123456789abcdef" for char in candidate_frontier_sha256)
            or type(teacher_epoch) is not int or teacher_epoch < 0
            or type(qualification_epoch) is not int or qualification_epoch < 0):
        _fail("BAMF_PLANNER_SNAPSHOT_INPUT_INVALID")


def _row_key(row) -> tuple:
    return (
        row.domain, row.table, row.key, row.semantic_id or "",
        row.source_disposition, row.reason_code, row.owner,
    )


def _initial_snapshot(
    candidate: CurriculumCandidateSet, frontier: SourceFrontier,
    policy: ContextPolicy, *, budget: PlannerBudget,
    candidate_frontier_sha256: str, ready_candidate_ids: tuple[str, ...],
    staged_release_sha256s: tuple[str, ...],
    admitted_release_sha256: str | None, admission_receipt_sha256: str | None,
    retained_evidence: tuple[LearningEvidence, ...],
    retained_mastery_debt: tuple[str, ...],
    retained_debt_source_sha256: str | None, teacher_epoch: int,
    qualification_epoch: int, grade_labels: tuple[str, ...],
) -> CurriculumSnapshot:
    census = candidate.census
    claims = {
        "exposed": candidate.unverified_exposure_claims,
        "qualified": candidate.unverified_qualification_claims,
    }
    initial = CurriculumSnapshot(
        semantic_release=census.semantic_release,
        atlas_bundle_id=census.atlas_bundle_id,
        source_bundle_id=census.source_bundle_id,
        source_coverage_sha256=census.source_coverage_sha256,
        frozen_census_sha256=census.digest,
        source_eligible_concept_ids=tuple(sorted(census.source_eligible_concept_ids)),
        required_source_family_ids=tuple(sorted(census.required_source_family_ids)),
        coverage_rows=tuple(sorted(
            census.obligations, key=lambda row: (row.semantic_id, row.family_id))),
        source_held_rows=tuple(sorted(census.source_held, key=_row_key)),
        source_ir_only_rows=tuple(sorted(census.source_ir_only, key=_row_key)),
        pending_nonconcept_rows=tuple(sorted(
            census.source_nonconcept, key=lambda pair: _row_key(pair[0]))),
        prerequisite_edges=_source_edges(candidate),
        candidate_frontier_sha256=candidate_frontier_sha256,
        ready_candidate_ids=tuple(sorted(set(ready_candidate_ids))),
        staged_factory_release_sha256s=tuple(sorted(staged_release_sha256s)),
        admitted_factory_release_sha256=admitted_release_sha256,
        admission_receipt_sha256=admission_receipt_sha256,
        unverified_exposed_capability_ids=tuple(sorted(
            candidate.unverified_exposure_claims)),
        unverified_qualified_capability_ids=tuple(sorted(
            candidate.unverified_qualification_claims)),
        retained_evidence=tuple(sorted(retained_evidence, key=_evidence_key)),
        retained_mastery_debt=tuple(sorted(retained_mastery_debt)),
        retained_debt_source_sha256=retained_debt_source_sha256,
        unverified_learning_claims_sha256=hashlib.sha256(_bytes(claims)).hexdigest(),
        rights_epoch=frontier.rights_epoch,
        correction_generation=frontier.correction_generation,
        policy_epoch=policy.policy_epoch,
        teacher_epoch=teacher_epoch,
        qualification_epoch=qualification_epoch,
        budget=budget,
        grade_labels=tuple(sorted(grade_labels)),
        cursor=0,
        event_generation=0,
        predecessor_sha256=None,
        snapshot_sha256="0" * 64,
    )
    return initial


def _build_snapshot(
    candidate: CurriculumCandidateSet, frontier: SourceFrontier,
    policy: ContextPolicy, *, budget: PlannerBudget,
    candidate_frontier_sha256: str = "0" * 64,
    ready_candidate_ids: tuple[str, ...] = (),
    staged_release_sha256s: tuple[str, ...] = (),
    admitted_release_sha256: str | None = None,
    admission_receipt_sha256: str | None = None,
    retained_evidence: tuple[LearningEvidence, ...] = (),
    retained_mastery_debt: tuple[str, ...] = (),
    retained_debt_source_sha256: str | None = None,
    teacher_epoch: int = 0, qualification_epoch: int = 0,
    grade_labels: tuple[str, ...] = (),
) -> CurriculumSnapshot:
    """Pure source ledger construction; no authority is conferred."""
    _validate_snapshot_inputs(
        candidate, frontier, policy, budget=budget,
        candidate_frontier_sha256=candidate_frontier_sha256,
        ready_candidate_ids=ready_candidate_ids, retained_evidence=retained_evidence,
        retained_mastery_debt=retained_mastery_debt, teacher_epoch=teacher_epoch,
        qualification_epoch=qualification_epoch, grade_labels=grade_labels)
    initial = _initial_snapshot(
        candidate, frontier, policy, budget=budget,
        candidate_frontier_sha256=candidate_frontier_sha256,
        ready_candidate_ids=ready_candidate_ids,
        staged_release_sha256s=staged_release_sha256s,
        admitted_release_sha256=admitted_release_sha256,
        admission_receipt_sha256=admission_receipt_sha256,
        retained_evidence=retained_evidence,
        retained_mastery_debt=retained_mastery_debt,
        retained_debt_source_sha256=retained_debt_source_sha256,
        teacher_epoch=teacher_epoch, qualification_epoch=qualification_epoch,
        grade_labels=grade_labels)
    result = replace(initial, snapshot_sha256=initial.expected_digest())
    result.verify()
    return result


def build_curriculum_snapshot(
    candidate: CurriculumCandidateSet, atlas: AtlasArtifactSelection,
    learned_frontier: LearnedFrontier, source_frontier: SourceFrontier,
    policy: ContextPolicy, candidate_frontier: CandidateFrontierRelease, *,
    budget: PlannerBudget, ready_candidate_ids: tuple[str, ...] = (),
    staged_releases: tuple[FactoryRelease, ...] = (),
    admitted_release: FactoryRelease | None = None,
    admission_receipt: AdmissionReceipt | None = None,
    retained_evidence: tuple[LearningEvidence, ...] = (),
    retained_mastery_debt: tuple[str, ...] = (),
    retained_debt_source_sha256: str | None = None,
    teacher_epoch: int = 0, qualification_epoch: int = 0,
    grade_labels: tuple[str, ...] = (),
) -> CurriculumSnapshot:
    """Recheck the independently pinned A01/A08 proposal at consumption."""
    assert_curriculum_candidate_current(candidate, atlas, learned_frontier)
    if (type(candidate_frontier) is not CandidateFrontierRelease
            or type(staged_releases) is not tuple
            or any(type(item) is not FactoryRelease for item in staged_releases)
            or (admitted_release is None) != (admission_receipt is None)):
        _fail("BAMF_PLANNER_RELEASE_INPUT_INVALID")
    candidate_frontier.verify()
    known_candidates = {item.candidate_id for item in candidate_frontier.candidates}
    if (type(ready_candidate_ids) is not tuple
            or any(type(item) is not str or item not in known_candidates
                   for item in ready_candidate_ids)
            or len(set(ready_candidate_ids)) != len(ready_candidate_ids)):
        _fail("BAMF_PLANNER_FRONTIER_STATE_INVALID")
    for release in staged_releases:
        release.verify()
    admitted_sha = None
    receipt_sha = None
    if admitted_release is not None:
        admitted_release.verify()
        admission_receipt.verify(admitted_release)
        admitted_sha = admitted_release.release_sha256
        receipt_sha = hashlib.sha256(_bytes(admission_receipt)).hexdigest()
    return _build_snapshot(
        candidate, source_frontier, policy, budget=budget,
        candidate_frontier_sha256=candidate_frontier.release_sha256,
        ready_candidate_ids=ready_candidate_ids,
        staged_release_sha256s=tuple(
            item.release_sha256 for item in staged_releases),
        admitted_release_sha256=admitted_sha,
        admission_receipt_sha256=receipt_sha,
        retained_evidence=retained_evidence,
        retained_mastery_debt=retained_mastery_debt,
        retained_debt_source_sha256=retained_debt_source_sha256,
        teacher_epoch=teacher_epoch,
        qualification_epoch=qualification_epoch,
        grade_labels=grade_labels)


def assert_initial_snapshot_current(
    snapshot: CurriculumSnapshot,
    candidate: CurriculumCandidateSet, atlas: AtlasArtifactSelection,
    learned_frontier: LearnedFrontier, source_frontier: SourceFrontier,
    policy: ContextPolicy, candidate_frontier: CandidateFrontierRelease, *,
    budget: PlannerBudget, ready_candidate_ids: tuple[str, ...] = (),
    staged_releases: tuple[FactoryRelease, ...] = (),
    admitted_release: FactoryRelease | None = None,
    admission_receipt: AdmissionReceipt | None = None,
    retained_evidence: tuple[LearningEvidence, ...] = (),
    retained_mastery_debt: tuple[str, ...] = (),
    retained_debt_source_sha256: str | None = None,
    teacher_epoch: int = 0, qualification_epoch: int = 0,
    grade_labels: tuple[str, ...] = (),
) -> None:
    """Rebuild from the A01 pin; a digest alone never grants planning authority."""
    if type(snapshot) is not CurriculumSnapshot:
        _fail("BAMF_PLANNER_SNAPSHOT_INPUT_INVALID")
    snapshot.verify()
    current = build_curriculum_snapshot(
        candidate, atlas, learned_frontier, source_frontier, policy,
        candidate_frontier, budget=budget, ready_candidate_ids=ready_candidate_ids,
        staged_releases=staged_releases,
        admitted_release=admitted_release,
        admission_receipt=admission_receipt,
        retained_evidence=retained_evidence,
        retained_mastery_debt=retained_mastery_debt,
        retained_debt_source_sha256=retained_debt_source_sha256,
        teacher_epoch=teacher_epoch,
        qualification_epoch=qualification_epoch,
        grade_labels=grade_labels)
    if snapshot.canonical_bytes() != current.canonical_bytes():
        _fail("BAMF_PLANNER_SNAPSHOT_SOURCE_DRIFT")
