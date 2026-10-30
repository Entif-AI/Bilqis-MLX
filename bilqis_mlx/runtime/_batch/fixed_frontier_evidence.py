"""Pinned exam and fixed-frontier evidence for candidate retention."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SOURCE
from .capability_authority import evaluate_progression_authority
from .capability_retention import (
    candidate_work_disposition, configuration_outcome, retain_candidate,
)

import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.fixed_frontier as _bilqis_mlx_fixed_frontier
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.learning.plasticity_escape as _learning_plasticity_escape
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.profiles.retention as _profiles_retention
import bilqis_mlx.runtime.assessment as _runtime_assessment
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state


def _fixed_same_grade_rows(run_dir, receipt, course, school, capability, settings):
    """Reuse the last independently scored full-grade cohort, if available.

    No new test rows are generated here. The persisted cohort, rubric and
    content hash must all verify before the parent/challenger screen can
    claim a fixed-exam grade comparison.
    """
    own_grade = capability.partition(".")[0]
    exam = receipt.get("last_exam") or {}
    if (exam.get("assessment_grade") != own_grade or
            exam.get("grade_exam_epoch") != school.grade_exam_epoch):
        return ()
    required = {cap for cap in _curriculum_scheduler.assessment_capabilities(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school)
                if cap.partition(".")[0] == own_grade}
    exam_scores = exam.get("scores") or {}
    if not required <= set(exam_scores):
        return ()
    cohort = _runtime_assessment._verify_saved_cohort(run_dir, receipt, course)
    if cohort is None:
        raise ValueError("LEARNING_EXPERIMENT_FIXED_GRADE_COHORT_MISSING")
    rows = tuple(r for r in cohort.rows if r["capability"] in required)
    if (len(rows) != len({r["id"] for r in rows}) or
            len(rows) > len(required) * 48 or
            any(type(exam_scores[cap].get("total")) is not int or
                exam_scores[cap]["total"] < 1 or
                sum(row["capability"] == cap for row in rows) !=
                exam_scores[cap]["total"] for cap in required)):
        raise ValueError("LEARNING_EXPERIMENT_FIXED_GRADE_COHORT_INCOMPLETE")
    return rows


def _reusable_exam_identity(receipt, school, *, rubric_sha256,
                            assessment_scope_sha256):
    """Return the exact already-scored exam identity for an unchanged student."""
    exam = receipt.get("last_exam") or {}
    student = school.current_student
    if (exam.get("assessment_grade") != school.grade or
            exam.get("grade_exam_epoch") != school.grade_exam_epoch or
            exam.get("student_sha256") != student.sha256 or
            exam.get("optimizer_step") != student.optimizer_step or
            exam.get("exam_rubric_sha256") != rubric_sha256 or
            exam.get("assessment_scope_sha256") != assessment_scope_sha256):
        return None
    cohort_sha = exam.get("cohort_sha256")
    if (not isinstance(cohort_sha, str) or len(cohort_sha) != 64 or
            any(c not in "0123456789abcdef" for c in cohort_sha)):
        raise ValueError("HUMAN_TRAINER_REUSABLE_EXAM_COHORT_IDENTITY_INVALID")
    return (student.sha256, student.optimizer_step, cohort_sha,
            rubric_sha256, assessment_scope_sha256)


def _frontier_fixed_evidence(
        mx, run_dir, receipt, school, capability, parent, candidate,
        config, answer_ids):
    fixed = {"status": "NOT_MEASURED",
             "reason": "NO_COMPARABLE_COMPLETE_GRADE_EXAM"}
    frontier = {"status": "NOT_MEASURED",
                "reason": "NO_FIXED_WHOLE_SCHOOL_FRONTIER"}
    frontier_parent = frontier_candidate = {}
    from bilqis_mlx.fixed_frontier import load_frontier, screen_frontier, frontier_exam
    exam = frontier_exam(receipt)
    frontier_rows, frontier_parent = load_frontier(
        run_dir, receipt, parent_sha256=exam.get("student_sha256"),
        parent_optimizer_step=exam.get("optimizer_step"))
    if frontier_rows and (exam.get("student_sha256") != school.current_student.sha256 or
                          exam.get("optimizer_step") != school.current_student.optimizer_step):
        if (type(exam.get("optimizer_step")) is not int or
                school.current_student.optimizer_step <= exam["optimizer_step"]):
            raise ValueError("FIXED_FRONTIER_PARENT_IDENTITY_DRIFT")
        frontier_parent = _learning_student_ops._predictions(
            mx, parent, list(frontier_rows), config, answer_ids)
    if frontier_rows:
        grade = capability.partition(".")[0]
        grade_rows = tuple(
            row for row in frontier_rows
            if row["capability"].partition(".")[0] == grade)
        if grade_rows:
            grade_parent = {
                row["id"]: frontier_parent[row["id"]] for row in grade_rows}
            grade_candidate = _learning_student_ops._predictions(
                mx, candidate, list(grade_rows), config, answer_ids)
            grade_scores = _learning_learning_experiment.paired_outcomes(
                grade_rows, grade_parent, grade_candidate)
            fixed = {
                "status": "MEASURED", "grade": grade,
                "cohort_sha256": exam["cohort_sha256"],
                "before": sum(value["before"] for value in grade_scores.values()),
                "after": sum(value["after"] for value in grade_scores.values()),
                "total": sum(value["total"] for value in grade_scores.values()),
                "capabilities": grade_scores,
            }
            frontier_candidate = dict(grade_candidate)
        else:
            fixed = {
                "status": "NOT_MEASURED",
                "reason": "ACTIVE_GRADE_ABSENT_FROM_FIXED_FRONTIER",
            }
        other_rows = tuple(
            row for row in frontier_rows if row not in grade_rows)
        if other_rows:
            frontier_candidate.update(_learning_student_ops._predictions(
                mx, candidate, list(other_rows), config, answer_ids))
        frontier = screen_frontier(
            frontier_rows, frontier_parent, frontier_candidate,
            frontier_exam(receipt)["cohort_sha256"])
    return frontier_rows, fixed, frontier, frontier_parent, frontier_candidate


def _fragile_replay_evidence(
        mx, run_dir, receipt, parent, candidate, config, answer_ids,
        frontier_parent, frontier_candidate):
    from bilqis_mlx.learning.fragile_replay import load_replay_rows, screen_replay
    policy = _profiles_retention.fragile_preservation_policy()
    replay_rows = load_replay_rows(
        run_dir, receipt,
        capabilities=policy.capabilities)
    if not replay_rows:
        return {
            "status": "NOT_MEASURED",
            "reason": "FRAGILE_PRESERVATION_EXAM_NOT_YET_ADMITTED",
        }
    ids = {row["id"] for row in replay_rows}
    replay_parent = (
        {rid: frontier_parent[rid] for rid in ids}
        if ids <= frontier_parent.keys() else
        _learning_student_ops._predictions(mx, parent, list(replay_rows), config, answer_ids))
    replay_candidate = (
        {rid: frontier_candidate[rid] for rid in ids}
        if ids <= frontier_candidate.keys() else
        _learning_student_ops._predictions(mx, candidate, list(replay_rows), config, answer_ids))
    return screen_replay(
        replay_rows, replay_parent, replay_candidate,
        _bilqis_mlx_fixed_frontier.frontier_exam(receipt)["cohort_sha256"])
