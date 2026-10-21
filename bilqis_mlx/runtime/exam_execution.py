"""Routine, promotion and generalization exam orchestration."""
from __future__ import annotations

import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.diagnostics.exam_events as _diagnostics_exam_events
import bilqis_mlx.factory.assessment as _factory_assessment
import bilqis_mlx.factory.model as _factory_model
import bilqis_mlx.factory.schedule as _factory_schedule
import bilqis_mlx.generated_assessment as _bilqis_mlx_generated_assessment
import bilqis_mlx.learning.champions as _learning_champions
import bilqis_mlx.learning.championship_runtime as _learning_championship_runtime
import bilqis_mlx.learning.epoch_championships as _learning_epoch_championships
import bilqis_mlx.learning.lesson_guidance as _learning_lesson_guidance
import bilqis_mlx.learning.mentor_epoch as _learning_mentor_epoch
import bilqis_mlx.learning.stagnation_control as _learning_stagnation_control
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.learning.teacher_feedback as _learning_teacher_feedback
import bilqis_mlx.learning.whole_student_retention as _learning_whole_student_retention
import bilqis_mlx.runtime.admission as _runtime_admission
import bilqis_mlx.runtime.assessment as _runtime_assessment
import bilqis_mlx.runtime.boundary_commit as _runtime_boundary_commit
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.mlx_checkpoint as _runtime_mlx_checkpoint
import bilqis_mlx.runtime.reconciliation as _runtime_reconciliation
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.source_adapters.school as _source_adapters_school
import dataclasses as _dataclasses


def _score_parent_for_paired_s3(mx, run_dir, receipt, parent, cohort, graph,
                                current_scores):
    """Read-only parent inference on this fresh cohort for S3 comparability."""
    path = run_dir / parent.filename
    try:
        if (path.is_symlink() or path.parent != run_dir / "bundles" or
                not parent.filename.startswith("bundles/")):
            raise ValueError("DIAGNOSTIC_PAIRED_S3_UNSAFE_PARENT")
        weights, own_adamw, meta, loaded_graph = _runtime_mlx_checkpoint.load_semantically_bound_bundle(path)
        if (meta["safetensors_sha256"] != parent.sha256 or
                meta["optimizer_step"] != parent.optimizer_step or
                loaded_graph != graph):
            raise ValueError("DIAGNOSTIC_PAIRED_S3_PARENT_DRIFT")
        del own_adamw
        predictions = _learning_student_ops._predictions(
            mx, weights, tuple(cohort.rows), receipt["config"],
            receipt["answer_ids"])
        measured = _bilqis_mlx_generated_assessment.score(cohort, predictions, _dataclasses.asdict(parent))["scores"]
        del weights
        if set(measured) != set(current_scores):
            raise ValueError("DIAGNOSTIC_PAIRED_S3_SCOPE_DRIFT")
        return measured, None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, str(exc)


def _paired_stagnation_progress(mx, run_dir, receipt, stagnation, cohort, graph,
                                current_checkpoint, current_scores):
    """Compare consecutive assessment checkpoints on this same fresh cohort."""
    pointer = (stagnation or {}).get("progress_checkpoint")
    if pointer is None:
        return (), False
    try:
        previous = _learning_champions.Checkpoint(**pointer)
    except (TypeError, ValueError):
        return (), False
    if (previous.sha256 == current_checkpoint.sha256 and
            previous.optimizer_step == current_checkpoint.optimizer_step):
        return (), True
    previous_scores, issue = _score_parent_for_paired_s3(
        mx, run_dir, receipt, previous, cohort, graph, current_scores)
    if issue is not None or previous_scores is None:
        return (), False
    improved = []
    for capability, current in current_scores.items():
        prior = previous_scores.get(capability)
        if (not isinstance(prior, dict) or
                type(prior.get("correct")) is not int or
                type(prior.get("total")) is not int or
                prior["total"] != current.get("total")):
            return (), False
        if current["correct"] > prior["correct"]:
            improved.append(capability)
    return tuple(improved), True


def _school_result_label(school):
    return (("GRADE_" + school.grade + "_MASTERED_AWAITING_NEXT_GRADE")
            if school.stage == "AWAITING_NEXT_GRADE" else
            ("GRADE_" + school.revalidation_target_grade +
             "_REVALIDATING_" + school.grade)
            if school.revalidation_target_grade else
            "ACTIVE_GRADE_" + school.grade)


def _promotion_due_after_routine(
        before, after, *, complete_assessment: bool = True) -> bool:
    """Whether a perfect routine evaluation would advance the school state.

    An incomplete assessment can legitimately move the scheduler to a new
    grade during a stagnation spiral, but it cannot create a qualification
    instrument. Distinguish *teaching progression* from *graduation authority*.
    """
    return complete_assessment and (
        after.grade != before.grade
        or after.revalidation_target_grade != before.revalidation_target_grade
        or after.stage in {
            "AWAITING_NEXT_GRADE", "AWAITING_TEACHER_SOUP",
            "WHOLE_SCHOOL_MASTERED",
        }
    )


def _assessment_scope_sha256(full_scope, scores) -> str:
    """Bind an assessment scope to the capabilities actually represented."""
    score_ids = set(scores)
    selected = tuple(cap for cap in full_scope if cap in score_ids)
    if not selected or set(selected) != score_ids:
        raise ValueError("HUMAN_TRAINER_EXAM_SCORE_SCOPE_DRIFT")
    return _runtime_state._fingerprint(selected)


def _measure_debt_admission_boundary(mx, run_dir, receipt, manifest, course,
                                     source_root, parameters, graph):
    """Measure the exact complete admitted plan before explicit debt admission."""
    release = _runtime_admission._require_executable_factory_admission(run_dir, receipt, graph)
    program = _factory_schedule.schedule_program_from_executable_release(release)
    school = _runtime_state._state_from_json(receipt["school"], program)
    full_scope = tuple(cap.capability_id for cap in release.execution_plan.capabilities)
    cohort, pointer = _runtime_assessment._routine_executable_cohort(
        run_dir, receipt, manifest, release, _source_adapters_school.live_source_registry(),
        source_root, graph, capabilities=full_scope,
        assessment_epoch=school.grade_exam_epoch, legacy_course=course)
    guesses = _learning_student_ops._predictions(
        mx, parameters, list(cohort.rows), receipt["config"], receipt["answer_ids"])
    measured = _bilqis_mlx_generated_assessment.score(cohort, guesses, _dataclasses.asdict(school.current_student))
    return {**receipt, "debt_admission_boundary_exam": {
        **pointer,
        "schema": "bilqis.mlx.debt-admission-boundary/v2",
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "exam_rubric_sha256": pointer["rubric_sha256"],
        "assessment_scope_sha256": _runtime_state._fingerprint(full_scope),
        "source_exam_plane": "DEBT_ADMISSION_BOUNDARY",
        "scores": measured["scores"],
        "misses_for_teacher": list(measured["misses_for_teacher"]),
    }}


def _take_exam(mx, run_dir, receipt, manifest, course, source_root,
               source_checkpoint, parameters, optimizer, graph, *, reserve_gib,
               scheduler_only: bool = False,
               session_elapsed_seconds=None):
    executable_release = _runtime_admission._read_executable_factory_release_artifact(
        run_dir, receipt)
    program = _factory_schedule.schedule_program_from_executable_release(executable_release)
    school = _runtime_state._state_from_json(receipt["school"], program)
    if not school.stage.startswith("ASSESS_"):
        raise ValueError("HUMAN_TRAINER_EXAM_OUTSIDE_SCHEDULED_BOUNDARY")
    if (receipt.get("championship_school_identity") !=
            _learning_championship_runtime._live_championship_identity(receipt, course, graph, parameters)):
        raise ValueError("CHAMPIONSHIP_SCHOOL_IDENTITY_RESET_REQUIRED")
    stagnation = receipt.get("stagnation_session")
    blocked_before = _learning_stagnation_control.quarantined_capabilities(stagnation)
    full_scope = _curriculum_scheduler.assessment_capabilities(program, school)
    active_scope = tuple(cap for cap in full_scope if cap not in set(blocked_before))
    _runtime_assessment._require_active_stagnation_scope(active_scope)
    parent_checkpoint = school.current_student
    source_registry = _source_adapters_school.live_source_registry()
    routine_cohort, routine_pointer = _runtime_assessment._routine_executable_cohort(
        run_dir, receipt, manifest, executable_release, source_registry,
        source_root, graph, capabilities=active_scope,
        assessment_epoch=school.grade_exam_epoch, legacy_course=course)
    routine_file = routine_pointer["cohort_file"]
    rubric = routine_pointer["rubric_sha256"]
    generator = routine_cohort.generator_version
    routine_rows = list(routine_cohort.rows)
    routine_scope_sha = _assessment_scope_sha256(
        full_scope, {cap: None for cap in active_scope})
    candidate_cohort = None
    candidate_measured = None
    frontier = dict(receipt.get("capability_best", {}))
    roles = ()
    compared = []
    if scheduler_only:
        if int(optimizer.state["step"].item()) != school.current_student.optimizer_step:
            raise ValueError("FLASH_SCHEDULER_EXAM_REQUIRES_CHECKPOINTED_STUDENT")
    else:
        candidate_cohort, _ = _runtime_assessment._candidate_executable_cohort(
            run_dir, receipt, manifest, executable_release, source_registry,
            source_root, graph, capabilities=active_scope,
            legacy_course=course)
        candidate_guesses = _learning_student_ops._predictions(
            mx, parameters, list(candidate_cohort.rows),
            receipt["config"], receipt["answer_ids"])
        school, frontier, roles, compared = _runtime_boundary_commit._commit_scored_student(
            mx, run_dir, receipt, manifest, course, school,
            candidate_cohort, candidate_guesses,
            parameters, optimizer, graph, reserve_gib=reserve_gib,
            allowed_capabilities=active_scope)
        receipt = _learning_championship_runtime._bind_checkpoint_origin(receipt, school.current_student)
        candidate_measured = _bilqis_mlx_generated_assessment.score(
            candidate_cohort, candidate_guesses, _dataclasses.asdict(school.current_student))

    routine_guesses = _learning_student_ops._predictions(
        mx, parameters, routine_rows, receipt["config"], receipt["answer_ids"])
    routine_measured = _bilqis_mlx_generated_assessment.score(
        routine_cohort, routine_guesses, _dataclasses.asdict(school.current_student))
    paired_progressed, paired_progress_usable = _paired_stagnation_progress(
        mx, run_dir, receipt, stagnation, routine_cohort, graph,
        school.current_student, routine_measured["scores"])
    championship_exams = ([] if scheduler_only else [
        (candidate_cohort, candidate_measured, candidate_guesses),
        (routine_cohort, routine_measured, routine_guesses)])
    parent_routine_scores, parent_routine_issue = _score_parent_for_paired_s3(
        mx, run_dir, receipt, parent_checkpoint, routine_cohort, graph,
        routine_measured["scores"])
    routine_assessment = _curriculum_scheduler.Assessment(
        checkpoint_sha256=school.current_student.sha256,
        optimizer_step=school.current_student.optimizer_step,
        course_digest=program.digest(),
        rubric_digest=rubric,
        scores={cap: _curriculum_scheduler.Score(**entry)
                for cap, entry in routine_measured["scores"].items()},
        evaluation_id="source-oracled-routine-cohort/" + routine_cohort.digest + "/" +
                      school.current_student.sha256)
    routine_advanced = (
        _curriculum_scheduler.assess_withheld(program, school, routine_assessment, blocked_before)
        if blocked_before else
        _curriculum_scheduler.assess_flash(program, school, routine_assessment)
        if scheduler_only else
        _curriculum_scheduler.assess(program, school, routine_assessment))

    routine_last_exam = {
        **routine_pointer,
        "assessment_grade": school.grade,
        "grade_exam_epoch": school.grade_exam_epoch,
        "exam_plane": "ROUTINE",
        "grade_test_lifecycle": _bilqis_mlx_generated_assessment.ROUTINE_EVAL_LIFECYCLE,
        "assessment_scope_sha256": routine_scope_sha,
        "evaluation_id": routine_assessment.evaluation_id,
        "exam_rubric_sha256": routine_assessment.rubric_digest,
        "cohort_sha256": routine_cohort.digest,
        "cohort_file": routine_file,
        "cohort_seed": routine_cohort.seed,
        "generator_version": generator,
        "misses_for_teacher": list(routine_measured["misses_for_teacher"]),
        "student_sha256": routine_assessment.checkpoint_sha256,
        "optimizer_step": routine_assessment.optimizer_step,
        "scores": routine_measured["scores"],
    }
    routine_warnings = _diagnostics_exam_events.summarize_completed_exam_safely(
        run_dir, receipt, routine_last_exam)
    routine_warnings = _diagnostics_exam_events.apply_paired_checkpoint_s3(
        routine_warnings,
        parent_scores=parent_routine_scores,
        current_scores=routine_measured["scores"],
        parent_sha256=parent_checkpoint.sha256,
        current_sha256=school.current_student.sha256,
        parent_step=parent_checkpoint.optimizer_step,
        current_step=school.current_student.optimizer_step,
        cohort_sha256=routine_cohort.digest,
        unavailable_reason=parent_routine_issue)
    quarantine_suppressed = _learning_stagnation_control.grace_suppressed_capabilities(
        receipt.get("stagnation_grace"), required_capabilities=full_scope,
        optimizer_step=routine_assessment.optimizer_step)
    stagnation, stagnation_events, routine_advanced, blocked_after = (
        _runtime_reconciliation._advance_stagnation_after_routine(
            program=program,
            school=school,
            routine_assessment=routine_assessment,
            routine_advanced=routine_advanced,
            stagnation=stagnation, blocked_before=blocked_before,
            active_scope=active_scope, routine_measured=routine_measured,
            routine_warnings=routine_warnings,
            generation=receipt["generation"] + 1,
            quarantine_suppressed=quarantine_suppressed,
            session_elapsed_seconds=session_elapsed_seconds,
            paired_progressed=paired_progressed,
            paired_progress_usable=paired_progress_usable,
            progress_checkpoint=_dataclasses.asdict(school.current_student)))

    qualification = None
    generalization = None
    generalization_passed = False
    burned_generalization = list(
        receipt.get("burned_generalization_cohorts_v2", ()))
    exam_plane = "ROUTINE"
    cohort = routine_cohort
    cohort_pointer = routine_pointer
    cohort_file = routine_file
    rows = routine_rows
    guesses = routine_guesses
    measured = routine_measured
    assessment = routine_assessment
    advanced = routine_advanced
    complete_assessment = (
        not blocked_before and not blocked_after and
        tuple(active_scope) == tuple(full_scope))
    if (not scheduler_only and
            _promotion_due_after_routine(
                school, routine_advanced,
                complete_assessment=complete_assessment)):
        promotion_cohort, qualification = _runtime_assessment._promotion_executable_cohort(
            run_dir, receipt, manifest, executable_release, source_registry,
            source_root, graph, capabilities=active_scope,
            assessment_epoch=school.grade_exam_epoch, legacy_course=course)
        promotion_file = qualification["cohort_file"]
        promotion_rows = list(promotion_cohort.rows)
        promotion_guesses = _learning_student_ops._predictions(
            mx, parameters, promotion_rows,
            receipt["config"], receipt["answer_ids"])
        promotion_measured = _bilqis_mlx_generated_assessment.score(
            promotion_cohort, promotion_guesses, _dataclasses.asdict(school.current_student))
        championship_exams.append((promotion_cohort, promotion_measured, promotion_guesses))
        promotion_assessment = _curriculum_scheduler.Assessment(
            checkpoint_sha256=school.current_student.sha256,
            optimizer_step=school.current_student.optimizer_step,
            course_digest=program.digest(),
            rubric_digest=rubric,
            scores={cap: _curriculum_scheduler.Score(**entry)
                    for cap, entry in promotion_measured["scores"].items()},
            evaluation_id="source-oracled-promotion-cohort/" +
                          promotion_cohort.digest + "/" +
                          school.current_student.sha256)
        exam_plane = "PROMOTION"
        cohort = promotion_cohort
        cohort_pointer = qualification
        cohort_file = promotion_file
        rows = promotion_rows
        guesses = promotion_guesses
        measured = promotion_measured
        assessment = promotion_assessment
        promotion_advanced = _curriculum_scheduler.assess(program, school, promotion_assessment)
        advanced = promotion_advanced
        if _promotion_due_after_routine(
                school, promotion_advanced,
                complete_assessment=complete_assessment):
            promotion_evidence = _factory_model.LearningEvidence(
                _factory_model.AssessmentClass.PROMOTION,
                promotion_cohort.digest,
                promotion_assessment.checkpoint_sha256,
                promotion_assessment.optimizer_step,
                True,
            )
            generalization_cohort, generalization = (
                _runtime_assessment._generalization_executable_cohort(
                    run_dir, receipt, manifest, executable_release,
                    source_registry, source_root, graph,
                    capabilities=active_scope,
                    assessment_epoch=school.grade_exam_epoch,
                    promotion_pointer=qualification,
                    exposed_specimen_ids=tuple(
                        row["id"] for row in routine_cohort.rows),
                    legacy_course=course))
            generalization_file = generalization["cohort_file"]
            generalization_rows = list(generalization_cohort.rows)
            generalization_guesses = _learning_student_ops._predictions(
                mx, parameters, generalization_rows,
                receipt["config"], receipt["answer_ids"])
            generalization_measured = _bilqis_mlx_generated_assessment.score(
                generalization_cohort, generalization_guesses,
                _dataclasses.asdict(school.current_student))
            championship_exams.append((generalization_cohort, generalization_measured,
                                        generalization_guesses))
            generalization_assessment = _curriculum_scheduler.Assessment(
                checkpoint_sha256=school.current_student.sha256,
                optimizer_step=school.current_student.optimizer_step,
                course_digest=program.digest(),
                rubric_digest=rubric,
                scores={cap: _curriculum_scheduler.Score(**entry)
                        for cap, entry in generalization_measured["scores"].items()},
                evaluation_id="source-oracled-generalization-cohort/" +
                              generalization_cohort.digest + "/" +
                              school.current_student.sha256)
            exam_plane = "GENERALIZATION"
            cohort = generalization_cohort
            cohort_pointer = generalization
            cohort_file = generalization_file
            rows = generalization_rows
            guesses = generalization_guesses
            measured = generalization_measured
            assessment = generalization_assessment
            advanced = _curriculum_scheduler.assess(program, school, generalization_assessment)
            generalization_evidence = _factory_model.LearningEvidence(
                _factory_model.AssessmentClass.GENERALIZATION,
                generalization_cohort.digest,
                generalization_assessment.checkpoint_sha256,
                generalization_assessment.optimizer_step,
                _promotion_due_after_routine(
                    school, advanced,
                    complete_assessment=complete_assessment),
            )
            generalization_passed = _factory_assessment.qualification_complete(
                promotion_evidence, generalization_evidence)
            burned_generalization.append(generalization)

    scores = {k: {"correct": v.correct, "total": v.total}
              for k, v in assessment.scores.items()}
    final_scope_sha = _assessment_scope_sha256(full_scope, scores)
    epoch = receipt.get("mentor_epoch")
    championship_decisions = ()
    graduation_roles = ()
    championship_roles = ()
    if epoch is None and not scheduler_only:
        epoch = _learning_mentor_epoch.begin_initial_epoch(
            student=_dataclasses.asdict(school.current_student), introduced_grade=school.grade,
            source_graph_sha256=_runtime_state._fingerprint(graph),
            frontier=receipt.get("graduation_perfect", {}),
            soups=receipt.get("grade_soups", {}))
        epoch["settled_matchups"] = {}
        epoch["championship_school_identity"] = receipt["championship_school_identity"]
    if scheduler_only:
        perfect = receipt.get("graduation_perfect", {})
        frozen_soups = receipt.get("grade_soups", {})
        soup_changes = ()
    else:
        epoch = _learning_championship_runtime._hydrate_championship_witnesses(mx, run_dir, receipt, epoch, graph)
        changed_roles, decisions = set(), []
        for examined, result, predicted in championship_exams:
            epoch, changed, verdicts = _learning_championship_runtime._advance_exam_championships(
                mx, run_dir, receipt, epoch, course, school,
                examined, result, predicted, parameters, graph)
            changed_roles.update(changed)
            decisions.extend(verdicts)
        championship_roles = tuple(sorted(changed_roles))
        championship_decisions = tuple(decisions)
        new_soups, soup_changes = _learning_lesson_guidance._cook_new_grade_soups(
            mx, run_dir, receipt, _learning_epoch_championships.active_frontier(epoch), course, graph,
            existing=epoch.get("active_grade_soups", {}), reserve_gib=reserve_gib)
        epoch["active_grade_soups"] = new_soups
        # Keep all original champion/grade-soup evidence immutable in the
        # archival state fields. Only the epoch earns new active roles.
        perfect = receipt.get("graduation_perfect", {})
        frozen_soups = receipt.get("grade_soups", {})
    last_exam = {
        "assessment_grade": school.grade,
        "grade_exam_epoch": school.grade_exam_epoch,
        "exam_plane": exam_plane,
        "grade_test_lifecycle": (
            _bilqis_mlx_generated_assessment.GENERALIZATION_LIFECYCLE if generalization is not None else
            _bilqis_mlx_generated_assessment.PROMOTION_ATTEMPT_LIFECYCLE if qualification is not None else
            _bilqis_mlx_generated_assessment.ROUTINE_EVAL_LIFECYCLE),
        "assessment_scope_sha256": final_scope_sha,
        "evaluation_id": assessment.evaluation_id,
        "exam_rubric_sha256": assessment.rubric_digest,
        "cohort_sha256": cohort.digest,
        "cohort_file": cohort_file,
        "cohort_seed": cohort.seed,
        "factory_release_sha256": cohort_pointer["factory_release_sha256"],
        "capabilities": list(cohort_pointer["capabilities"]),
        "rubric_sha256": cohort_pointer["rubric_sha256"],
        "source_sha256": cohort_pointer["source_sha256"],
        "routine_cohort_sha256": routine_cohort.digest,
        "routine_cohort_file": routine_file,
        "routine_cohort_seed": routine_cohort.seed,
        "routine_scores": routine_measured["scores"],
        "graduation_perfect_roles": list(graduation_roles),
        "championship_roles": list(championship_roles),
        "grade_soups_refreshed": list(soup_changes),
        "championship_decisions": list(championship_decisions),
        "generator_version": generator,
        "incumbent_comparisons": compared,
        "misses_for_teacher": list(measured["misses_for_teacher"]),
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "scores": scores,
        "withheld_capabilities": list(blocked_before),
        "stagnation_quarantined": list(blocked_after),
        "routine_learning_diagnostics": routine_warnings,
        "flash_scheduler_only": scheduler_only,
    }
    if candidate_cohort is not None:
        last_exam["candidate_cohort_sha256"] = candidate_cohort.digest
    if qualification is not None:
        last_exam["promotion_cohort_sha256"] = qualification["cohort_sha256"]
    if generalization is not None:
        last_exam["generalization_cohort_sha256"] = generalization["cohort_sha256"]
        last_exam["generalization_passed"] = generalization_passed
    peaks, retention_status = _learning_whole_student_retention.advance_peaks(
        receipt.get("whole_student_peaks", []),
        curriculum_mode=receipt["curriculum_mode"],
        numeric_maximum=receipt.get("numeric_maximum"),
        rubric_sha256=assessment.rubric_digest,
        cohort_sha256=cohort.digest,
        assessment_scope_sha256=last_exam["assessment_scope_sha256"],
        scores=scores, checkpoint=_dataclasses.asdict(school.current_student))
    last_exam["whole_student_retention"] = retention_status
    pending = (*receipt.get("_pending_visit_events", ()), *stagnation_events)
    exam_warnings = _diagnostics_exam_events.summarize_completed_exam_safely(run_dir, receipt, last_exam)
    if cohort.digest == routine_cohort.digest:
        paired_parent_scores = parent_routine_scores
        paired_parent_issue = parent_routine_issue
    else:
        paired_parent_scores, paired_parent_issue = _score_parent_for_paired_s3(
            mx, run_dir, receipt, parent_checkpoint, cohort, graph, scores)
    exam_warnings = _diagnostics_exam_events.apply_paired_checkpoint_s3(
        exam_warnings,
        parent_scores=paired_parent_scores,
        current_scores=scores,
        parent_sha256=parent_checkpoint.sha256,
        current_sha256=school.current_student.sha256,
        parent_step=parent_checkpoint.optimizer_step,
        current_step=school.current_student.optimizer_step,
        cohort_sha256=cohort.digest,
        unavailable_reason=paired_parent_issue)
    last_exam["learning_diagnostics"] = exam_warnings
    teacher_outcomes = _learning_teacher_feedback.summarize_teacher_outcomes(receipt.get("last_exam"), last_exam, pending)
    last_exam["teacher_outcomes"] = teacher_outcomes
    # Exam golds become eligible *after* the complete examination. Retain
    # tokens and source provenance so the next weakest-three visits can train
    # directly on missed semantics, with no answer leakage during scoring.
    priority = _learning_teacher_feedback.reconcile_unresolved_misses(
        receipt.get("teacher_misses", ()), rows, guesses)
    if blocked_after:
        blocked_set = set(blocked_after)
        priority = [row for row in priority if row["capability"] not in blocked_set]
    unresolved_ids = {row["id"] for row in priority}
    miss_exposures = {
        identity: count for identity, count in
        receipt.get("teacher_miss_exposures", {}).items()
        if identity in unresolved_ids and type(count) is int and count >= 0
    }
    for identity in unresolved_ids:
        miss_exposures.setdefault(identity, 0)
    migrated_receipt = {**receipt, "teacher_misses": priority,
                        "whole_student_peaks": peaks,
                        "graduation_perfect": perfect,
                        "grade_soups": frozen_soups,
                        "teacher_miss_exposures": miss_exposures,
                        "legacy_frontier_pending_replay": False,
                        "live_rubric_sha256": assessment.rubric_digest}
    if stagnation is not None:
        migrated_receipt["stagnation_session"] = stagnation
    if qualification is not None and not generalization_passed:
        # A failed fixed promotion cohort remains the same classroom criterion,
        # including while fresh-generalization misses are taught afterward.
        migrated_receipt["qualification_cohort_v2"] = qualification
        migrated_receipt.pop("qualification_cohort", None)
    elif generalization_passed:
        migrated_receipt.pop("qualification_cohort_v2", None)
        migrated_receipt.pop("qualification_cohort", None)
    if burned_generalization:
        migrated_receipt["burned_generalization_cohorts_v2"] = burned_generalization
        migrated_receipt.pop("burned_generalization_cohorts", None)
    if generalization is not None:
        migrated_receipt["last_generalization_cohort_v2"] = generalization
        migrated_receipt.pop("last_generalization_cohort", None)
    if epoch is not None:
        migrated_receipt["mentor_epoch"] = epoch
    migrated_receipt.pop("teacher_miss_cursor", None)
    result = _runtime_checkpoints._advance(
        run_dir, migrated_receipt, advanced, frontier=frontier,
        model_bundle=school.current_student.filename, last_exam=last_exam,
        result=_school_result_label(advanced), persist=False)
    exam_event = {
        "event": ("SCHOOL_FLASH_ROUTINE_EXAM_COMMITTED" if scheduler_only
                  else "SCHOOL_LIVE_EXAM_COMMITTED"),
        "grade": school.grade, "generation": result["generation"],
        "grade_exam_epoch": school.grade_exam_epoch,
        "exam_plane": exam_plane,
        "grade_test_lifecycle": last_exam["grade_test_lifecycle"],
        "assessment_scope_sha256": last_exam["assessment_scope_sha256"],
        "introduction_stage": school.introduction_stage,
        "scores": scores, "phase": advanced.stage,
        "student_sha256": assessment.checkpoint_sha256,
        "optimizer_step": assessment.optimizer_step,
        "rubric": assessment.rubric_digest,
        "cohort_sha256": cohort.digest, "generator_version": generator,
        "cohort_seed": cohort.seed, "cohort_file": last_exam["cohort_file"],
        "routine_cohort_sha256": routine_cohort.digest,
        "incumbent_comparisons": compared,
        "teacher_miss_count": len(priority),
        "learning_diagnostics": exam_warnings,
        "teacher_outcomes": teacher_outcomes,
        "whole_student_retention": retention_status,
        "flash_scheduler_only": scheduler_only,
        "withheld_capabilities": list(blocked_before),
        "qualification_authority_changed": False if scheduler_only else None,
        "champions_changed": False if scheduler_only else None,
    }
    if qualification is not None:
        exam_event["qualification_cohort_sha256"] = qualification["cohort_sha256"]
    if epoch is not None:
        exam_event["championship_epoch"] = {
            "baseline_sha256": epoch["baseline"]["sha256"],
            "earned_roles": [] if scheduler_only else list(championship_roles),
            "active_role_count": len(epoch.get("active_roles", {})),
            "active_soup_grades": sorted(epoch.get("active_grade_soups", {})),
            "cross_origin_decisions": [] if scheduler_only else list(championship_decisions),
        }
    result = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(
        result, _runtime_checkpoints._boundary_delivery_events(result, pending, roles, exam_event)))
    _runtime_checkpoints._publish_boundary(run_dir, result, pending, roles, exam_event=exam_event)
    return result
