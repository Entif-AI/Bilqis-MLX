"""Structural extraction from reconciliation.py; behavior preserved."""
from __future__ import annotations
import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.learning.stagnation_control as _learning_stagnation_control
import bilqis_mlx.learning.whole_student_retention as _learning_whole_student_retention
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import dataclasses as _dataclasses
from .championship_source_repair import (_affected_championship_source_context, _invalidate_championship_source_context, _repair_championship_source_context, _require_championship_source_context_custody)
from .resume_metadata import (_reconcile_learning_settings, _reconcile_vocabulary_metadata)

def _seed_saved_whole_student_peak(run_dir, receipt, course, optimizer):
    """Protect the already saved live exam before the next neural visit.

    Only an exam belonging to the current, fully durable checkpoint qualifies.
    Earlier rubric scores, orphan bundles and mismatched AdamW cannot seed it.
    """
    if receipt.get("whole_student_peaks"):
        return receipt
    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    checkpoint = _dataclasses.asdict(school.current_student)
    prior = receipt.get("last_exam") or {}
    if (not prior.get("scores") or
            prior.get("student_sha256") != checkpoint["sha256"] or
            prior.get("optimizer_step") != checkpoint["optimizer_step"]):
        return receipt
    if int(optimizer.state["step"].item()) != checkpoint["optimizer_step"]:
        raise ValueError("WHOLE_STUDENT_PEAK_SEED_ADAMW_DRIFT")
    peaks, outcome = _learning_whole_student_retention.advance_peaks(
        [], curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=prior["exam_rubric_sha256"],
        cohort_sha256=prior["cohort_sha256"],
        assessment_scope_sha256=prior["assessment_scope_sha256"],
        scores=prior["scores"], checkpoint=checkpoint)
    candidate = _runtime_checkpoints._advance(run_dir, {**receipt, "whole_student_peaks": peaks},
                         school, persist=False)
    event = {"event": "SCHOOL_EXISTING_WHOLE_STUDENT_PEAK_PRESERVED",
             "generation": candidate["generation"],
             "optimizer_step": checkpoint["optimizer_step"],
             "student_sha256": checkpoint["sha256"],
             "exam_correct": outcome["best_correct"],
             "exam_total": outcome["best_total"],
             "source_cohort_sha256": prior["cohort_sha256"],
             "model_and_optimizer_unchanged": True}
    result = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(candidate, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, result)
    return result

def _rehabilitate_sole_grade_debt(
        program, school, stagnation, debt, *, generation):
    """Keep training when containment debt is the only work left in one grade."""
    if (stagnation is None or school.stage != "DEFERRED_STAGNATION" or
            not debt):
        return stagnation, school, ()
    grades = {capability.partition(".")[0] for capability in debt}
    if len(grades) != 1:
        return stagnation, school, ()
    stagnation, event = _learning_stagnation_control.activate_sole_grade_rehabilitation(
        stagnation, capabilities=tuple(debt), generation=generation)
    school = _curriculum_scheduler.reactivate_stagnation_debt(program, school, tuple(debt))
    return stagnation, school, (event,)

def _reconcile_stagnation_scope(run_dir, receipt, course, school):
    """Keep command-local stagnation state aligned with the live scheduler scope."""
    control = receipt.get("stagnation_session")
    if control is None:
        return receipt
    required = _curriculum_scheduler.assessment_capabilities(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school)
    updated, event = _learning_stagnation_control.reconcile_required_scope(
        control, required_capabilities=required,
        generation=receipt["generation"] + 1)
    if event is None:
        return receipt

    history = list(receipt.get("stagnation_scope_history", ()))
    history.append({
        "session_id": control["session_id"],
        "generation": receipt["generation"],
        "reconciled_at_grade": school.grade,
        "required_capabilities": list(control["required_capabilities"]),
        "quarantined": list(_learning_stagnation_control.quarantined_capabilities(control)),
    })
    migrated = {
        **receipt,
        "stagnation_session": updated,
        "stagnation_scope_history": history[-32:],
    }
    record = _runtime_checkpoints._advance(
        run_dir, migrated, school, result=receipt.get("result"),
        persist=False)
    if record["generation"] != event["generation"]:
        raise ValueError("STAGNATION_SCOPE_RECONCILIATION_GENERATION_DRIFT")
    event = {**event, "grade": school.grade}
    record = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(record, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
    return record

def _advance_stagnation_after_routine(
        *, program, school, routine_assessment, routine_advanced,
        stagnation, blocked_before, active_scope, routine_measured,
        routine_warnings, generation, quarantine_suppressed=(),
        session_elapsed_seconds=None, paired_progressed=(),
        paired_progress_usable=None, progress_checkpoint=None):
    """Apply one completed routine boundary to the current session containment."""
    events = ()
    if stagnation is None:
        return stagnation, events, routine_advanced, ()
    if (session_elapsed_seconds is not None and
            paired_progress_usable is not None and
            progress_checkpoint is not None):
        stagnation = _learning_stagnation_control.observe_paired_progress(
            stagnation,
            measured_capabilities=tuple(routine_measured["scores"]),
            improved_capabilities=tuple(paired_progressed),
            measurement_usable=paired_progress_usable,
            elapsed_seconds=session_elapsed_seconds,
            progress_checkpoint=progress_checkpoint)
    if (school.stage == "ASSESS_MAIN" and
            routine_advanced.stage == "RECOVERY_1"):
        stagnation = _learning_stagnation_control.begin_recovery_cycle(
            stagnation, first_recovery=routine_advanced.first_recovery)
    elif school.stage == "ASSESS_RECOVERY_2":
        tail = _curriculum_scheduler.weakest_three(routine_assessment.scores, active_scope)
        stagnation, events = _learning_stagnation_control.complete_recovery_cycle(
            stagnation, weakest_tail=tail,
            scores=routine_measured["scores"],
            generation=generation,
            active_warnings=tuple(routine_warnings.get("active_warnings", ())),
            quarantine_suppressed=tuple(quarantine_suppressed),
            **({"elapsed_seconds": session_elapsed_seconds}
               if session_elapsed_seconds is not None else {}))
        blocked_after = _learning_stagnation_control.quarantined_capabilities(stagnation)
        if set(blocked_after) != set(blocked_before):
            retained_scores = {
                cap: score for cap, score in routine_assessment.scores.items()
                if cap not in set(blocked_after)}
            if not retained_scores:
                routine_advanced = _dataclasses.replace(
                    school, stage="DEFERRED_STAGNATION", queue=(),
                    first_recovery=(),
                    latest_rubric_digest=routine_assessment.rubric_digest)
            else:
                reduced = _curriculum_scheduler.Assessment(
                    checkpoint_sha256=routine_assessment.checkpoint_sha256,
                    optimizer_step=routine_assessment.optimizer_step,
                    course_digest=routine_assessment.course_digest,
                    rubric_digest=routine_assessment.rubric_digest,
                    scores=retained_scores,
                    evaluation_id=routine_assessment.evaluation_id +
                                  "/post-stagnation-filter")
                routine_advanced = _curriculum_scheduler.assess_withheld(
                    program, school, reduced, blocked_after,
                    rubric_capabilities=active_scope)
    if routine_advanced.stage == "DEFERRED_STAGNATION":
        stagnation, routine_advanced, rehabilitation_events = (
            _rehabilitate_sole_grade_debt(
                program, routine_advanced, stagnation,
                _learning_stagnation_control.quarantined_capabilities(stagnation),
                generation=generation))
        events = (*events, *rehabilitation_events)
    return (
        stagnation, events, routine_advanced,
        _learning_stagnation_control.quarantined_capabilities(stagnation))
