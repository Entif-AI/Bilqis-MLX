"""Championship, retention, and publication finalization for exams."""
from __future__ import annotations

import dataclasses as _dataclasses
from types import SimpleNamespace

import bilqis_mlx.diagnostics.exam_events as _diagnostics_exam_events
import bilqis_mlx.generated_assessment as _bilqis_mlx_generated_assessment
import bilqis_mlx.learning.championship_runtime as _learning_championship_runtime
import bilqis_mlx.learning.epoch_championships as _learning_epoch_championships
import bilqis_mlx.learning._lesson_guidance.soups as _learning_lesson_guidance
import bilqis_mlx.learning.mentor_epoch as _learning_mentor_epoch
import bilqis_mlx.learning.teacher_feedback as _learning_teacher_feedback
import bilqis_mlx.learning.whole_student_retention as _learning_whole_student_retention
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.state as _runtime_state
from . import exam_execution_support as _support


def _championship_state(state: dict) -> dict:
    s = SimpleNamespace(**state)
    scores = {key: {"correct": value.correct, "total": value.total}
              for key, value in s.assessment.scores.items()}
    epoch = s.receipt.get("mentor_epoch")
    championship_decisions = ()
    graduation_roles = ()
    championship_roles = ()
    if epoch is None and not s.scheduler_only:
        epoch = _learning_mentor_epoch.begin_initial_epoch(
            student=_dataclasses.asdict(s.school.current_student),
            introduced_grade=s.school.grade,
            source_graph_sha256=_runtime_state._fingerprint(s.graph),
            frontier=s.receipt.get("graduation_perfect", {}),
            soups=s.receipt.get("grade_soups", {}))
        epoch["settled_matchups"] = {}
        epoch["championship_school_identity"] = s.receipt["championship_school_identity"]
    if s.scheduler_only:
        perfect = s.receipt.get("graduation_perfect", {})
        frozen_soups = s.receipt.get("grade_soups", {})
        soup_changes = ()
    else:
        epoch = _learning_championship_runtime._hydrate_championship_witnesses(
            s.mx, s.run_dir, s.receipt, epoch, s.graph)
        changed_roles, decisions = set(), []
        for examined, result, predicted in s.championship_exams:
            epoch, changed, verdicts = _learning_championship_runtime._advance_exam_championships(
                s.mx, s.run_dir, s.receipt, epoch, s.course, s.school,
                examined, result, predicted, s.parameters, s.graph)
            changed_roles.update(changed)
            decisions.extend(verdicts)
        championship_roles = tuple(sorted(changed_roles))
        championship_decisions = tuple(decisions)
        new_soups, soup_changes = _learning_lesson_guidance._cook_new_grade_soups(
            s.mx, s.run_dir, s.receipt,
            _learning_epoch_championships.active_frontier(epoch), s.course, s.graph,
            existing=epoch.get("active_grade_soups", {}), reserve_gib=s.reserve_gib)
        epoch["active_grade_soups"] = new_soups
        perfect = s.receipt.get("graduation_perfect", {})
        frozen_soups = s.receipt.get("grade_soups", {})
    return {
        "scores": scores,
        "final_scope_sha": _support._assessment_scope_sha256(s.full_scope, scores),
        "epoch": epoch,
        "championship_decisions": championship_decisions,
        "graduation_roles": graduation_roles,
        "championship_roles": championship_roles,
        "perfect": perfect,
        "frozen_soups": frozen_soups,
        "soup_changes": soup_changes,
    }


def _exam_record(state: dict, championship: dict) -> dict:
    s = SimpleNamespace(**state)
    c = SimpleNamespace(**championship)
    last_exam = {
        **s.cohort_pointer,
        "assessment_grade": s.school.grade,
        "grade_exam_epoch": s.school.grade_exam_epoch,
        "exam_plane": s.exam_plane,
        "grade_test_lifecycle": (
            _bilqis_mlx_generated_assessment.PROMOTION_ATTEMPT_LIFECYCLE
            if s.qualification is not None
            else _bilqis_mlx_generated_assessment.ROUTINE_EVAL_LIFECYCLE),
        "assessment_scope_sha256": c.final_scope_sha,
        "evaluation_id": s.assessment.evaluation_id,
        "exam_rubric_sha256": s.assessment.rubric_digest,
        "cohort_sha256": s.cohort.digest,
        "cohort_file": s.cohort_file,
        "cohort_seed": s.cohort.seed,
        "routine_cohort_sha256": s.routine_cohort.digest,
        "routine_cohort_file": s.routine_file,
        "routine_cohort_seed": s.routine_cohort.seed,
        "routine_scores": s.routine_measured["scores"],
        "graduation_perfect_roles": list(c.graduation_roles),
        "championship_roles": list(c.championship_roles),
        "grade_soups_refreshed": list(c.soup_changes),
        "championship_decisions": list(c.championship_decisions),
        "generator_version": s.generator,
        "incumbent_comparisons": s.compared,
        "misses_for_teacher": list(s.measured["misses_for_teacher"]),
        "student_sha256": s.assessment.checkpoint_sha256,
        "optimizer_step": s.assessment.optimizer_step,
        "scores": c.scores,
        "withheld_capabilities": list(s.blocked_before),
        "stagnation_quarantined": list(s.blocked_after),
        "routine_learning_diagnostics": s.routine_warnings,
        "flash_scheduler_only": s.scheduler_only,
    }
    if s.candidate_cohort is not None:
        last_exam["candidate_cohort_sha256"] = s.candidate_cohort.digest
    if s.qualification is not None:
        last_exam["promotion_cohort_sha256"] = s.qualification["cohort_sha256"]
    peaks, retention_status = _learning_whole_student_retention.advance_peaks(
        s.receipt.get("whole_student_peaks", []),
        curriculum_mode=s.receipt["curriculum_mode"],
        numeric_maximum=s.receipt.get("numeric_maximum"),
        rubric_sha256=s.assessment.rubric_digest,
        cohort_sha256=s.cohort.digest,
        assessment_scope_sha256=last_exam["assessment_scope_sha256"],
        scores=c.scores, checkpoint=_dataclasses.asdict(s.school.current_student))
    last_exam["whole_student_retention"] = retention_status
    pending = (*s.receipt.get("_pending_visit_events", ()), *s.stagnation_events)
    _runtime_checkpoints._notify_viewer(
        {"_runtime_phase": "DIAGNOSTICS", "_dashboard_redraw": True})
    exam_warnings = _diagnostics_exam_events.summarize_completed_exam_safely(
        s.run_dir, s.receipt, last_exam)
    if s.cohort.digest == s.routine_cohort.digest:
        paired_parent_scores = s.parent_routine_scores
        paired_parent_issue = s.parent_routine_issue
    else:
        paired_parent_scores, paired_parent_issue = _support._score_parent_for_paired_s3(
            s.mx, s.run_dir, s.receipt, s.parent_checkpoint, s.cohort, s.graph, c.scores)
    exam_warnings = _diagnostics_exam_events.apply_paired_checkpoint_s3(
        exam_warnings,
        parent_scores=paired_parent_scores,
        current_scores=c.scores,
        parent_sha256=s.parent_checkpoint.sha256,
        current_sha256=s.school.current_student.sha256,
        parent_step=s.parent_checkpoint.optimizer_step,
        current_step=s.school.current_student.optimizer_step,
        cohort_sha256=s.cohort.digest,
        unavailable_reason=paired_parent_issue)
    last_exam["learning_diagnostics"] = exam_warnings
    teacher_outcomes = _learning_teacher_feedback.summarize_teacher_outcomes(
        s.receipt.get("last_exam"), last_exam, pending)
    last_exam["teacher_outcomes"] = teacher_outcomes
    return {
        "last_exam": last_exam,
        "peaks": peaks,
        "retention_status": retention_status,
        "pending": pending,
        "exam_warnings": exam_warnings,
        "teacher_outcomes": teacher_outcomes,
    }



from .exam_execution_publication import _persist_exam


def _finalize_exam(state: dict):
    championship = _championship_state(state)
    record = _exam_record(state, championship)
    return _persist_exam(state, championship, record)
