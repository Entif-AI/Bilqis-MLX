"""Persistence and publication boundary for completed developmental exams."""
from __future__ import annotations

from types import SimpleNamespace

import bilqis_mlx.learning.teacher_feedback as _learning_teacher_feedback
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
from . import exam_execution_support as _support


def _exam_event(s, c, r, result, priority):
    event = {
        "event": ("SCHOOL_FLASH_ROUTINE_EXAM_COMMITTED" if s.scheduler_only
                  else "SCHOOL_LIVE_EXAM_COMMITTED"),
        "grade": s.school.grade, "generation": result["generation"],
        "grade_exam_epoch": s.school.grade_exam_epoch, "exam_plane": s.exam_plane,
        "grade_test_lifecycle": r.last_exam["grade_test_lifecycle"],
        "assessment_scope_sha256": r.last_exam["assessment_scope_sha256"],
        "introduction_stage": s.school.introduction_stage, "scores": c.scores,
        "phase": s.advanced.stage, "student_sha256": s.assessment.checkpoint_sha256,
        "optimizer_step": s.assessment.optimizer_step, "rubric": s.assessment.rubric_digest,
        "cohort_sha256": s.cohort.digest, "generator_version": s.generator,
        "cohort_seed": s.cohort.seed, "cohort_file": r.last_exam["cohort_file"],
        "routine_cohort_sha256": s.routine_cohort.digest,
        "incumbent_comparisons": s.compared, "teacher_miss_count": len(priority),
        "learning_diagnostics": r.exam_warnings, "teacher_outcomes": r.teacher_outcomes,
        "whole_student_retention": r.retention_status, "flash_scheduler_only": s.scheduler_only,
        "withheld_capabilities": list(s.blocked_before),
        "qualification_authority_changed": False if s.scheduler_only else None,
        "champions_changed": False if s.scheduler_only else None,
    }
    if s.qualification is not None:
        event["qualification_cohort_sha256"] = s.qualification["cohort_sha256"]
    if c.epoch is not None:
        event["championship_epoch"] = {
            "baseline_sha256": c.epoch["baseline"]["sha256"],
            "earned_roles": [] if s.scheduler_only else list(c.championship_roles),
            "active_role_count": len(c.epoch.get("active_roles", {})),
            "active_soup_grades": sorted(c.epoch.get("active_grade_soups", {})),
            "cross_origin_decisions": [] if s.scheduler_only else list(c.championship_decisions),
        }
    return event


def _persist_exam(state: dict, championship: dict, record: dict):
    s, c, r = (SimpleNamespace(**item) for item in (state, championship, record))
    priority = _learning_teacher_feedback.reconcile_unresolved_misses(
        s.receipt.get("teacher_misses", ()), s.rows, s.guesses)
    if s.blocked_after:
        blocked_set = set(s.blocked_after)
        priority = [row for row in priority if row["capability"] not in blocked_set]
    unresolved_ids = {row["id"] for row in priority}
    miss_exposures = {identity: count for identity, count in
        s.receipt.get("teacher_miss_exposures", {}).items()
        if identity in unresolved_ids and type(count) is int and count >= 0}
    for identity in unresolved_ids:
        miss_exposures.setdefault(identity, 0)
    migrated = {**s.receipt, "teacher_misses": priority, "whole_student_peaks": r.peaks,
        "graduation_perfect": c.perfect, "grade_soups": c.frozen_soups,
        "teacher_miss_exposures": miss_exposures, "legacy_frontier_pending_replay": False,
        "live_rubric_sha256": s.assessment.rubric_digest}
    if s.stagnation is not None:
        migrated["stagnation_session"] = s.stagnation
    if s.qualification is not None and not s.promotion_passed:
        migrated["qualification_cohort_v2"] = s.qualification
        migrated.pop("qualification_cohort", None)
    elif s.promotion_passed:
        migrated.pop("qualification_cohort_v2", None)
        migrated.pop("qualification_cohort", None)
    if c.epoch is not None:
        migrated["mentor_epoch"] = c.epoch
    migrated.pop("teacher_miss_cursor", None)
    result = _runtime_checkpoints._advance(
        s.run_dir, migrated, s.advanced, frontier=s.frontier,
        model_bundle=s.school.current_student.filename, last_exam=r.last_exam,
        result=_support._school_result_label(s.advanced), persist=False)
    event = _exam_event(s, c, r, result, priority)
    result = _runtime_checkpoints._persist(s.run_dir, _runtime_checkpoints._with_delivery_outbox(
        result, _runtime_checkpoints._boundary_delivery_events(result, r.pending, s.roles, event)))
    _runtime_checkpoints._publish_boundary(s.run_dir, result, r.pending, s.roles, exam_event=event)
    return result
