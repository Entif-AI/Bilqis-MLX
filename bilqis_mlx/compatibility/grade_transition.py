"""Historical numerical transition and admission-readiness contracts."""
from __future__ import annotations

from ..grade_transition import candidate_package_digest, cumulative_exam_digest
from dataclasses import asdict
import hashlib
import json
from typing import Mapping

from bilqis_mlx.curriculum.scheduler import (
    Assessment, SchoolState, append_next_grade,
    verify_state,
)
from ..curriculum import Course
from ..semantics.core import Operation
from ..curriculum_compiler import TypedCandidatePackage, compile_ast
from ..verification.curriculum import candidate_package_problems
from ..verification.expressions import Backend
from ..verification.review_evidence import EvidenceContext


def require_complete_cumulative_prior_exam(
    course: Course, state: SchoolState, assessment: Assessment,
) -> None:
    """Verify one complete, perfect prior-course exam at the current checkpoint."""
    verify_state(course, state)
    required = tuple(cap.id for grade in course.grades for cap in grade.capabilities)
    assessment.verify(state.current_student, course, required)
    expected = {cap: count for grade in course.grades for cap, count in grade.exam_item_counts}
    if (set(assessment.scores) != set(expected) or
            any(score.correct != count or score.total != count
                for cap, count in expected.items()
                for score in (assessment.scores[cap],))):
        raise ValueError("GRADE_ADMISSION_REQUIRES_COMPLETE_PERFECT_CUMULATIVE_EXAM")


def next_grade_readiness(
    previous: Course, successor: Course, state: SchoolState, assessment: Assessment, *,
    parent_release: str, candidate_package: TypedCandidatePackage | None,
    candidate_semantic_release: str | None, semantic_release: str,
    approved_release_receipt: str | None, source_operations: Mapping[str, Operation],
    review_evidence: EvidenceContext | None = None,
    source_backend: Backend | None = None, independent_backend: Backend | None = None,
    cumulative_exam_receipt: str | None = None,
    stage_mastery_receipts: Mapping[str, str] | None = None,
) -> dict:
    """Report a future-grade admission plan without growing or persisting anything.

    A structural review, candidate source package, and independently pinned
    release receipt are separate gates. This never promotes the candidate or
    authorizes neural work.
    """
    blockers = []
    added = successor.grades[-1] if successor.grades else None
    planned_grade = added.id if added else None
    if parent_release != previous.version:
        blockers.append("GRADE_ADMISSION_PARENT_RELEASE_MISMATCH")
    try:
        require_complete_cumulative_prior_exam(previous, state, assessment)
    except (TypeError, ValueError) as exc:
        blockers.append("GRADE_ADMISSION_CUMULATIVE_PROOF_BLOCKED:" + str(exc))
    try:
        append_next_grade(previous, successor, state)
    except (TypeError, ValueError) as exc:
        blockers.append("GRADE_ADMISSION_APPEND_BOUNDARY_BLOCKED:" + str(exc))

    package_digest = None
    if not isinstance(candidate_package, TypedCandidatePackage):
        blockers.append("GRADE_ADMISSION_SOURCE_CANDIDATE_MISSING")
    else:
        blockers.extend(candidate_package_problems(candidate_package, source=source_backend,
                                                    independent=independent_backend))
        if candidate_package.source_status != "SOURCE_ONLY_CANDIDATE":
            blockers.append("GRADE_ADMISSION_SOURCE_CANDIDATE_STATUS_INVALID")
        if candidate_package.coverage_debt:
            blockers.append("GRADE_ADMISSION_CANDIDATE_COVERAGE_DEBT_PRESENT")
        package_digest = candidate_package_digest(candidate_package)
        if candidate_semantic_release != semantic_release:
            blockers.append("GRADE_ADMISSION_SEMANTIC_RELEASE_MISMATCH")
        expected_capabilities = {cap.id for cap in added.capabilities} if added else set()
        package_nodes = {node.id: node for node in candidate_package.ast_nodes}
        expected_nodes = {node.id: node for node in compile_ast(successor).nodes}
        if (set(candidate_package.target_capabilities) != expected_capabilities or
                not expected_capabilities <= package_nodes.keys() or
                set(package_nodes) - expected_nodes.keys()):
            blockers.append("GRADE_ADMISSION_CANDIDATE_CAPABILITIES_MISMATCH")
        elif any(node != expected_nodes[identity] for identity, node in package_nodes.items()):
            blockers.append("GRADE_ADMISSION_CANDIDATE_BINDINGS_MISMATCH")
        if (not candidate_package.lessons or not candidate_package.tests or
                any(not any(item.capability == cap.id for item in candidate_package.lessons) or
                    not any(item.capability == cap.id for item in candidate_package.tests)
                    for cap in added.capabilities)):
            blockers.append("GRADE_ADMISSION_CANDIDATE_SPECIMENS_MISSING")
        package_operations = {operation.symbol: operation
                              for operation in candidate_package.operation_bindings}
        if (not package_operations or any(source_operations.get(symbol) != operation
                                          for symbol, operation in package_operations.items())):
            blockers.append("GRADE_ADMISSION_SOURCE_BINDINGS_MISMATCH")

    review_report = None
    if isinstance(planned_grade, str) and isinstance(previous.version, str):
        try:
            from ..next_grade_review import require_admission_review
            review_report = require_admission_review(
                planned_grade, previous.version, evidence=review_evidence)
        except (TypeError, ValueError) as exc:
            blockers.append("GRADE_ADMISSION_REVIEW_BLOCKED:" + str(exc))
    else:
        blockers.append("GRADE_ADMISSION_PLANNED_GRADE_MISSING")
    if not isinstance(review_report, dict):
        blockers.append("GRADE_ADMISSION_REVIEW_REPORT_MISSING")
    elif review_report.get("semantic_release") != semantic_release:
        blockers.append("GRADE_ADMISSION_REVIEW_SEMANTIC_RELEASE_MISMATCH")
    elif (isinstance(candidate_package, TypedCandidatePackage) and
          candidate_package.ast_version != semantic_release):
        blockers.append("GRADE_ADMISSION_PACKAGE_AST_VERSION_MISMATCH")
    elif review_evidence is None or package_digest is None:
        blockers.append("GRADE_ADMISSION_EXTERNAL_RELEASE_APPROVAL_MISSING")
    else:
        inventory = review_evidence.inspect(
            grade=planned_grade, parent_release=previous.version,
            semantic_release=semantic_release,
            subject_sha256=review_report.get("subject_sha256"))
        expected_claim = "release:" + semantic_release + ":package:" + package_digest + ":APPROVED_FOR_ADMISSION"
        if not inventory.supports([approved_release_receipt], expected_claim):
            blockers.append("GRADE_ADMISSION_EXTERNAL_RELEASE_APPROVAL_MISSING")
        if not inventory.supports([cumulative_exam_receipt],
                                  "cumulative_exam:" + cumulative_exam_digest(assessment)):
            blockers.append("GRADE_ADMISSION_CUMULATIVE_ATTESTATION_MISSING")
        for node in candidate_package.ast_nodes:
            if node.id not in expected_capabilities:
                continue
            for prerequisite in (*node.requires, *node.composed_of):
                if prerequisite not in previous.capability_map:
                    prerequisite_node = package_nodes.get(prerequisite)
                    node_digest = hashlib.sha256(json.dumps(asdict(prerequisite_node),
                        sort_keys=True, separators=(",", ":")).encode()).hexdigest() if prerequisite_node else None
                    claim = ("stage_mastery:" + prerequisite + ":" + str(node_digest) + ":" +
                             state.current_student.sha256 + ":" + str(state.current_student.optimizer_step))
                    if not inventory.supports([(stage_mastery_receipts or {}).get(prerequisite)], claim):
                        blockers.append("GRADE_ADMISSION_EARLIER_STAGE_MASTERY_REQUIRED:" + prerequisite)
    review_binding = ({key: value for key, value in review_report.items()
                       if key in {"schema", "grade", "phase", "status", "subject_sha256",
                                  "evidence_sha256", "evidence_manifest_sha256",
                                  "evidence_receipt_digest", "phase_evidence_sha256",
                                  "semantic_release"}}
                      if isinstance(review_report, dict) else None)
    result = {
        "status": "BLOCKED" if blockers else "READY_FOR_HUMAN_ADMISSION_REVIEW",
        "blockers": list(dict.fromkeys(blockers)),
        "parent_release": parent_release,
        "planned_grade": planned_grade,
        "planned_capabilities": ([cap.id for cap in added.capabilities] if added else []),
        "planned_vocabulary_operations": (sorted(operation.symbol for operation in
                                                   candidate_package.operation_bindings)
                                         if isinstance(candidate_package, TypedCandidatePackage) else []),
        "planned_course_digest": successor.digest() if added else None,
        "semantic_release": semantic_release,
        "candidate_package_sha256": package_digest,
        "actual_neural_updates": 0,
        "training_authorized": False,
        "source_status": "SOURCE_ONLY_CANDIDATE",
        "review_report": review_binding,
    }
    result["planned_admission_event"] = {
        "event": "SCHOOL_NEXT_GRADE_ADMISSION_PLANNED",
        "grade": planned_grade, "parent_release": previous.version,
        "semantic_release": semantic_release, "review": review_binding,
        "actual_neural_updates": 0,
    }
    return result
