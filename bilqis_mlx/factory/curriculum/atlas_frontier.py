"""A09.1a immutable, source-replayed Factory planning snapshot.

This is a pure planning proposal. It does not qualify learning, admit
a staged release, create a source grant or mutate a student.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib

from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import ContextPolicy, SourceFrontier

from .atlas_frontier_contracts import (
    CurriculumSnapshot,
    PlannerBudget,
    PrerequisiteEdge,
    _bytes,
    _fail,
)
from .model import AdmissionReceipt, FactoryRelease, LearningEvidence
from .skos_curriculum import (
    CurriculumCandidateSet,
    LearnedFrontier,
    assert_curriculum_candidate_current,
)


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


def _build_snapshot(
    candidate: CurriculumCandidateSet, frontier: SourceFrontier,
    policy: ContextPolicy, *, budget: PlannerBudget,
    staged_release_sha256s: tuple[str, ...] = (),
    admitted_release_sha256: str | None = None,
    admission_receipt_sha256: str | None = None,
    retained_evidence: tuple[LearningEvidence, ...] = (),
    retained_mastery_debt: tuple[str, ...] = (),
    retained_debt_source_sha256: str | None = None,
    teacher_epoch: int = 0, grade_labels: tuple[str, ...] = (),
) -> CurriculumSnapshot:
    """Pure source ledger construction; no authority is conferred."""
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
            or type(teacher_epoch) is not int or teacher_epoch < 0):
        _fail("BAMF_PLANNER_SNAPSHOT_INPUT_INVALID")
    census = candidate.census
    row_key = lambda row: (
        row.domain, row.table, row.key, row.semantic_id or "",
        row.source_disposition, row.reason_code, row.owner)
    claims = {
        "exposed": candidate.unverified_exposure_claims,
        "qualified": candidate.unverified_qualification_claims,
    }
    initial = CurriculumSnapshot(
        census.semantic_release, census.atlas_bundle_id,
        census.source_bundle_id, census.source_coverage_sha256,
        census.digest,
        tuple(sorted(census.source_eligible_concept_ids)),
        tuple(sorted(census.required_source_family_ids)),
        tuple(sorted(census.obligations,
                     key=lambda row: (row.semantic_id, row.family_id))),
        tuple(sorted(census.source_held, key=row_key)),
        tuple(sorted(census.source_ir_only, key=row_key)),
        tuple(sorted(census.source_nonconcept,
                     key=lambda pair: row_key(pair[0]))),
        _source_edges(candidate), tuple(sorted(staged_release_sha256s)),
        admitted_release_sha256, admission_receipt_sha256,
        tuple(sorted(retained_evidence, key=lambda item: (
            item.checkpoint_sha256, item.cohort_sha256,
            item.optimizer_step, item.assessment_class.value))),
        tuple(sorted(retained_mastery_debt)), retained_debt_source_sha256,
        hashlib.sha256(_bytes(claims)).hexdigest(),
        frontier.rights_epoch, frontier.correction_generation,
        policy.policy_epoch, teacher_epoch, 0, budget,
        tuple(sorted(grade_labels)), 0, 0, None, "0" * 64,
    )
    result = replace(initial, snapshot_sha256=initial.expected_digest())
    result.verify()
    return result


def build_curriculum_snapshot(
    candidate: CurriculumCandidateSet, atlas: AtlasArtifactSelection,
    learned_frontier: LearnedFrontier, source_frontier: SourceFrontier,
    policy: ContextPolicy, *, budget: PlannerBudget,
    staged_releases: tuple[FactoryRelease, ...] = (),
    admitted_release: FactoryRelease | None = None,
    admission_receipt: AdmissionReceipt | None = None,
    retained_evidence: tuple[LearningEvidence, ...] = (),
    retained_mastery_debt: tuple[str, ...] = (),
    retained_debt_source_sha256: str | None = None,
    teacher_epoch: int = 0, grade_labels: tuple[str, ...] = (),
) -> CurriculumSnapshot:
    """Recheck the independently pinned A01/A08 proposal at consumption."""
    assert_curriculum_candidate_current(candidate, atlas, learned_frontier)
    if (type(staged_releases) is not tuple
            or any(type(item) is not FactoryRelease for item in staged_releases)
            or (admitted_release is None) != (admission_receipt is None)):
        _fail("BAMF_PLANNER_RELEASE_INPUT_INVALID")
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
        staged_release_sha256s=tuple(
            item.release_sha256 for item in staged_releases),
        admitted_release_sha256=admitted_sha,
        admission_receipt_sha256=receipt_sha,
        retained_evidence=retained_evidence,
        retained_mastery_debt=retained_mastery_debt,
        retained_debt_source_sha256=retained_debt_source_sha256,
        teacher_epoch=teacher_epoch,
        grade_labels=grade_labels)


def assert_initial_snapshot_current(
    snapshot: CurriculumSnapshot,
    candidate: CurriculumCandidateSet, atlas: AtlasArtifactSelection,
    learned_frontier: LearnedFrontier, source_frontier: SourceFrontier,
    policy: ContextPolicy, *, budget: PlannerBudget,
    staged_releases: tuple[FactoryRelease, ...] = (),
    admitted_release: FactoryRelease | None = None,
    admission_receipt: AdmissionReceipt | None = None,
    retained_evidence: tuple[LearningEvidence, ...] = (),
    retained_mastery_debt: tuple[str, ...] = (),
    retained_debt_source_sha256: str | None = None,
    teacher_epoch: int = 0, grade_labels: tuple[str, ...] = (),
) -> None:
    """Rebuild from the A01 pin; a digest alone never grants planning authority."""
    if type(snapshot) is not CurriculumSnapshot:
        _fail("BAMF_PLANNER_SNAPSHOT_INPUT_INVALID")
    snapshot.verify()
    current = build_curriculum_snapshot(
        candidate, atlas, learned_frontier, source_frontier, policy,
        budget=budget, staged_releases=staged_releases,
        admitted_release=admitted_release,
        admission_receipt=admission_receipt,
        retained_evidence=retained_evidence,
        retained_mastery_debt=retained_mastery_debt,
        retained_debt_source_sha256=retained_debt_source_sha256,
        teacher_epoch=teacher_epoch,
        grade_labels=grade_labels)
    if snapshot.canonical_bytes() != current.canonical_bytes():
        _fail("BAMF_PLANNER_SNAPSHOT_SOURCE_DRIFT")
