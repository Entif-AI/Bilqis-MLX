"""Atomic numerical transition plus neural-inert generic admission readiness."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass, replace
from enum import Enum
import hashlib
import json
from typing import Mapping

from .live_grade_c import RELEASE, answer_heads, constructor_digest, expanded_graph
from .boolean_identification import answer_heads as boolean_identification_answer_heads
from .live_curriculum import numeric_maximum
from bilqis_mlx.curriculum.scheduler import Assessment, SchoolState, append_next_grade, verify_state
from .curriculum import Course
from .semantics.core import Operation
from .curriculum_compiler import TypedCandidatePackage, compile_ast
from .verification.curriculum import candidate_package_problems
from .verification.expressions import Backend
from .verification.review_evidence import EvidenceContext
from .vocabulary_growth import extend_mlx_student


def candidate_package_digest(package: TypedCandidatePackage) -> str:
    """Digest the complete immutable source-only output approved by a receipt."""
    if not isinstance(package, TypedCandidatePackage):
        raise ValueError("GRADE_ADMISSION_INVALID_CANDIDATE_PACKAGE")

    def default(value):
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value):
            return asdict(value)
        raise TypeError(type(value).__name__)

    payload = json.dumps(asdict(package), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, default=default)
    return hashlib.sha256(payload.encode()).hexdigest()


def cumulative_exam_digest(assessment: Assessment) -> str:
    """Bind independent exam attestation to scores and one complete checkpoint."""
    return hashlib.sha256(json.dumps(asdict(assessment), sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


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
            from .next_grade_review import require_admission_review
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


def activate_numeric_grade(mx, run_dir, receipt, previous, successor,
                           parameters, optimizer, graph, *, reserve_gib):
    # Import the existing custody writer at use time; it owns all state/outbox I/O.
    from .trainer import (_advance, _bundle_pointer, _factory_admission,
        _fingerprint, _persist, _reconcile_delivery_outbox, _state_from_json,
        _with_delivery_outbox)
    school = _state_from_json(receipt["school"], previous)
    exam = receipt.get("last_exam") or {}
    counts = {cap: count for grade in previous.grades for cap, count in grade.exam_item_counts}
    if (successor.version != RELEASE or school.grade != "B" or
            school.revalidation_target_grade is not None or
            exam.get("student_sha256") != school.current_student.sha256 or
            exam.get("optimizer_step") != school.current_student.optimizer_step or
            exam.get("scores") != {cap: {"correct": count, "total": count} for cap,count in counts.items()}):
        raise ValueError("GRADE_C_REQUIRES_ONE_COMPLETE_CUMULATIVE_A_B_PASS")
    next_state = append_next_grade(previous, successor, school)
    grown_graph = expanded_graph(graph)
    grown, own_optimizer, growth = extend_mlx_student(parameters, optimizer, graph, grown_graph)
    import uuid
    pointer = _bundle_pointer(run_dir, "numeric-admission-"+uuid.uuid4().hex[:12],
        grown, own_optimizer, grown_graph, reserve_gib=reserve_gib)
    from bilqis_mlx.learning.mentor_epoch import begin_epoch
    previous_caps = tuple(cap.id for grade in previous.grades
                          for cap in grade.capabilities)
    next_epoch = begin_epoch(
        previous_graduate=asdict(school.current_student),
        admitted_baseline=asdict(pointer), introduced_grade="C",
        source_graph_sha256=_fingerprint(grown_graph),
        previous_capabilities=previous_caps,
        previous_graduation_exam={
            "checkpoint_sha256": exam.get("student_sha256"),
            "cohort_sha256": exam.get("cohort_sha256"),
            "rubric_sha256": exam.get("exam_rubric_sha256"),
            "scores": exam.get("scores"),
        })
    epoch_history = list(receipt.get("championship_epoch_history", ()))
    if receipt.get("mentor_epoch") is not None:
        epoch_history.append(receipt["mentor_epoch"])
    next_state = replace(next_state, current_student=pointer)
    maximum = numeric_maximum(successor)
    release, release_file, admission = _factory_admission(
        run_dir, successor, pointer, _fingerprint(grown_graph))
    from bilqis_mlx.learning.championship_identity import build_school_identity
    parameter_shapes = {name: list(value.shape) for name,value in grown.items()}
    championship_identity = build_school_identity(
        course_sha256=successor.digest(),
        semantic_graph_sha256=_fingerprint(grown_graph),
        parameter_shapes=parameter_shapes,
        factory_release_sha256=release.release_sha256)
    next_epoch["settled_matchups"] = deepcopy(
        (receipt.get("mentor_epoch") or {}).get("settled_matchups", {}))
    next_epoch["championship_school_identity"] = championship_identity
    heads = answer_heads(grown_graph, maximum)
    if "boolean_operator" in receipt["config"].get("answer_heads", {}):
        heads["boolean_operator"] = boolean_identification_answer_heads(grown_graph)[
            "boolean_operator"]
    updated = {**receipt, "curriculum_mode": RELEASE,
        "grade_c_parent_course_digest": previous.digest(),
        "numeric_maximum": maximum, "grade_c_code_sha256": constructor_digest(),
        "semantic_graph_sha256": _fingerprint(grown_graph),
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_admission": asdict(admission),
        "parameter_shapes": parameter_shapes,
        "championship_school_identity": championship_identity,
        "config": {**receipt["config"], "vocab_size": len(grown_graph["tokens"]),
                   "answer_heads": heads},
        "live_rubric_sha256": successor.grades[-1].assessment_sha256}
    updated["mentor_epoch"] = next_epoch
    updated["championship_epoch_history"] = epoch_history
    record = _advance(run_dir, updated, next_state, model_bundle=pointer.filename,
                       result="ACTIVE_GRADE_C", persist=False)
    event = {"event": "SCHOOL_COURSE_ADMITTED", "grade": "C",
        "generation": record["generation"], "student_sha256": pointer.sha256,
        "optimizer_step": pointer.optimizer_step, "growth": growth,
        "previous_student_sha256": school.current_student.sha256,
        "championship_baseline_sha256": pointer.sha256,
        "factory_release_sha256": release.release_sha256,
        "archived_championship_epochs": len(epoch_history),
        "teacher_events": receipt["teacher"]["events"],
        "rubric": successor.grades[-1].assessment_sha256,
        "actual_neural_updates": 0}
    record = _persist(run_dir, _with_delivery_outbox(record, (event,)))
    _reconcile_delivery_outbox(run_dir, record)
    return grown, own_optimizer, grown_graph, record
