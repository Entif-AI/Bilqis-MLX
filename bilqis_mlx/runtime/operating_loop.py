"""Serialized operator session and school phase dispatch."""
from __future__ import annotations

from bilqis_mlx import paths as _paths

import bilqis_mlx.compatibility.executable_projection as _compatibility_executable_projection
import bilqis_mlx.compatibility.live_releases as _compatibility_live_releases
import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.factory.schedule as _factory_schedule
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.learning.stagnation_control as _learning_stagnation_control
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.operator_vocabulary as _bilqis_mlx_operator_vocabulary
import bilqis_mlx.profiles.catalog as _profiles_catalog
import bilqis_mlx.profiles.school as _profiles_school
import bilqis_mlx.runtime.admission as _runtime_admission
import bilqis_mlx.runtime.boundary_commit as _runtime_boundary_commit
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.disk as _runtime_disk
import bilqis_mlx.runtime.exam_execution as _runtime_exam_execution
import bilqis_mlx.runtime.experiment_runs as _runtime_experiment_runs
import bilqis_mlx.runtime.frontier_refresh as _runtime_frontier_refresh
import bilqis_mlx.runtime.reconciliation as _runtime_reconciliation
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.session as _runtime_session
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.runtime.timing_trace as _runtime_timing_trace
import bilqis_mlx.runtime.visits as _runtime_visits
import contextlib as _contextlib
import dataclasses as _dataclasses
import json as _json
import pathlib as _pathlib
import time as _time
import uuid as _uuid


def operate(run_dir: _pathlib.Path, source_root: _pathlib.Path, source_checkpoint: _pathlib.Path,
            manifest_path: _pathlib.Path, *, resume: bool = False, minutes: int = 90,
            max_visits: int = 0, steps_per_visit: int = 16,
            batch_size: int = 32, reserve_gib: float = 100.,
            numeric_staircase: bool = False,
            boolean_composite: bool = False,
            boolean_idboolops: bool = False,
            full_grade_b: bool = False,
            retention_enabled: bool = True,
            experiment_probe_each: int = 6,
            experiment_mature_max_loss: int = 1,
            experiment_introduction_extra_loss: int = 2,
            experiment_protected_cap_limit: int = 8,
            stagnation_grace_grade: str | None = None,
            stagnation_grace_steps: int = 0,
            admit_next_grade_with_debt: bool = False,
            source_prefetch_workers: int = 2,
            flash_mode: bool = False,
            boolean_association_bridge: bool = False,
            autonomous_curriculum: bool = False,
            experiment_budget: _runtime_experiment_runs.ExperimentRunBudget | None = None) -> dict:
    """ENTRYPOINT FOR THE HUMAN'S SHELL ONLY. Never call in agent tests."""
    _runtime_timing_trace.trace_mark(
        "OPERATE_START", resume=resume, max_visits=max_visits,
        steps_per_visit=steps_per_visit, batch_size=batch_size,
        source_prefetch_workers=source_prefetch_workers,
        flash_mode=flash_mode,
        boolean_association_bridge=boolean_association_bridge,
        autonomous_curriculum=autonomous_curriculum,
        boolean_composite=boolean_composite,
        boolean_idboolops=boolean_idboolops,
        admit_next_grade_with_debt=admit_next_grade_with_debt,
        full_grade_b=full_grade_b)
    if (type(minutes) is not int or not 1 <= minutes <= 1440 or
            type(steps_per_visit) is not int or not 1 <= steps_per_visit <= 2048 or
            type(max_visits) is not int or max_visits < 0 or
            type(batch_size) is not int or batch_size < 2 or batch_size % 2 or
            type(source_prefetch_workers) is not int or
            not 0 <= source_prefetch_workers <= 2):
        raise ValueError("HUMAN_TRAINER_INVALID_OPERATOR_LIMITS")
    grace_requested = stagnation_grace_grade is not None or stagnation_grace_steps != 0
    if grace_requested and (
            not resume or not isinstance(stagnation_grace_grade, str) or
            not stagnation_grace_grade or type(stagnation_grace_steps) is not int or
            stagnation_grace_steps <= 0):
        raise ValueError("STAGNATION_GRACE_REQUIRES_EXPLICIT_RESUME_REQUEST")
    if flash_mode and not resume:
        raise ValueError("FLASH_MODE_REQUIRES_RESUME")
    if boolean_composite and not resume:
        raise ValueError("BOOLEAN_COMPOSITE_REQUIRES_RESUME")
    if boolean_idboolops and not resume:
        raise ValueError("BOOLEAN_IDBOOLOPS_REQUIRES_RESUME")
    if boolean_association_bridge and not resume:
        raise ValueError("BOOLEAN_ASSOCIATION_BRIDGE_REQUIRES_RESUME")
    if admit_next_grade_with_debt and not resume:
        raise ValueError("DEBT_GRADE_ADMISSION_REQUIRES_RESUME")
    if admit_next_grade_with_debt and numeric_staircase:
        raise ValueError("DEBT_GRADE_ADMISSION_INCOMPATIBLE_WITH_NUMERIC_STAIRCASE")
    if autonomous_curriculum and not retention_enabled:
        raise ValueError("AUTONOMOUS_CURRICULUM_REQUIRES_RETENTION")
    if autonomous_curriculum and flash_mode:
        raise ValueError("AUTONOMOUS_CURRICULUM_INCOMPATIBLE_WITH_FLASH_MODE")
    if retention_enabled or experiment_budget is not None:
        _runtime_experiment_runs.require_training_run(
            run_dir, _paths.REPO_ROOT / "runs",
            issue_budget=experiment_budget)
    if experiment_budget is not None:
        experiment_budget.assert_can_allocate(600_000_000)
    if boolean_association_bridge:
        saved_path = _pathlib.Path(run_dir).expanduser().resolve() / "state.json"
        if not saved_path.is_file():
            raise ValueError("TEACHING_ENRICHMENT_REQUIRES_ADMITTED_FACTORY_RELEASE")
        saved_release = _json.loads(saved_path.read_text(encoding="utf-8"))
        if not _runtime_admission.admitted_release_supports_teaching_option(
                _pathlib.Path(run_dir).expanduser().resolve(), saved_release):
            raise ValueError("TEACHING_ENRICHMENT_NOT_ADMITTED_BY_FACTORY_RELEASE")
    if not retention_enabled and resume:
        # Fail before GPU loading, orphan recovery, or any state mutation when
        # a protected student's policy would otherwise be silently disabled.
        saved_path = _pathlib.Path(run_dir).expanduser().resolve() / "state.json"
        if (saved_path.is_file() and _json.loads(saved_path.read_text()).get(
                "learning_experiment") is not None):
            raise ValueError("LEARNING_EXPERIMENT_PROTECTED_RESUME_REQUIRES_RETENTION")
    import mlx.core as mx
    mx.set_default_device(mx.gpu)
    with _runtime_timing_trace.trace_span("PREPARE_SOURCE"):
        manifest, historical_course, engine, teacher_sha, historical_teacher, provenance = _runtime_session.prepare_source(
            source_root, source_checkpoint, manifest_path)
    course_a = _compatibility_live_releases.initial_course(historical_course)
    # Build only verified source-bound metadata; no student, optimizer or
    # checkpoint is touched while preparing a future grade's course.
    course_b = None
    course_c = None
    staircase_course = None
    course = course_a
    run_dir = _pathlib.Path(run_dir).expanduser().resolve()
    start = _time.monotonic()
    with _runtime_session.operator_lock(run_dir), _contextlib.ExitStack() as resources:
        _runtime_timing_trace.trace_mark("OPERATOR_LOCK_ACQUIRED")
        if resume:
            saved = _json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            pending = run_dir / "states" / f"{saved['generation'] + 1:07d}.json"
            if pending.exists() and (pending.is_symlink() or not pending.is_file()):
                raise ValueError("HUMAN_TRAINER_PENDING_GENERATION_UNSAFE_PATH")
            pending_state = (_json.loads(pending.read_text(encoding="utf-8"))
                             if pending.exists() else None)
            if saved.get("factory_admission_v2") is not None:
                saved_release = _runtime_admission._read_executable_factory_release_artifact(
                    run_dir, saved)
                course = _compatibility_executable_projection.legacy_course_for_profile(
                    course_a, source_root, saved_release.profile)
                admitted_courses = None
            else:
                course, admitted_courses = _compatibility_executable_projection.resolve_legacy_resume_course(
                    historical_course, source_root, saved, course_a,
                    pending=pending_state)
            with _runtime_timing_trace.trace_span("RESUME_STUDENT"):
                params, optimizer, graph, receipt = _runtime_session._resume(
                    run_dir, manifest, course, teacher_sha,
                    grade_a_course=course_a, source_root=source_root,
                    admitted_courses=admitted_courses)
            admitted_v2 = _runtime_admission._require_executable_factory_admission(
                run_dir, receipt, graph)
            course = _compatibility_executable_projection.legacy_course_for_profile(
                course_a, source_root, admitted_v2.profile)
            active_grade_count = len(admitted_v2.execution_plan.grades)
            target_boolean_profile = None
            if (active_grade_count <= 2 and not autonomous_curriculum and
                    _compatibility_executable_projection.profile_has_legacy_inventory(admitted_v2, course)):
                target_boolean_profile = _profiles_school.with_disabled_future_grades(
                    _profiles_school.boolean_entry_profile(full=full_grade_b),
                    tuple(
                        grade.grade_id
                        for grade in admitted_v2.curriculum.grades[2:]))
            if (target_boolean_profile is not None and
                    receipt["school"]["stage"] == "AWAITING_NEXT_GRADE" and
                    active_grade_count == 1):
                receipt, course, admitted_v2, _ = _runtime_release_adoption._adopt_executable_profile(
                    run_dir, receipt, course_a, source_root, graph,
                    target_boolean_profile)
            elif (target_boolean_profile is not None and
                  active_grade_count == 2 and
                  admitted_v2.profile != target_boolean_profile):
                current_program = _factory_schedule.schedule_program_from_executable_release(
                    admitted_v2)
                current_school = _runtime_state._state_from_json(
                    receipt["school"], current_program)
                if current_school.grade == current_program.grades[-1].id:
                    receipt, course, admitted_v2, _ = _runtime_release_adoption._adopt_executable_profile(
                        run_dir, receipt, course_a, source_root, graph,
                        target_boolean_profile)
            admitted_v2 = _runtime_admission._require_executable_factory_admission(
                run_dir, receipt, graph)
            if ((receipt["school"]["stage"] == "AWAITING_NEXT_GRADE" or
                 admit_next_grade_with_debt) and
                    (not autonomous_curriculum or admit_next_grade_with_debt) and
                    len(admitted_v2.execution_plan.grades) == 2 and
                    len(admitted_v2.curriculum.grades) > 2):
                if admit_next_grade_with_debt:
                    receipt = _runtime_exam_execution._measure_debt_admission_boundary(
                        mx, run_dir, receipt, manifest, course, source_root,
                        params, graph)
                catalog_transition = _profiles_catalog.numeric_entry_transition(
                    admitted_v2, graph,
                    full_boolean=full_grade_b,
                    maximum=3 if numeric_staircase else 10)
                params, optimizer, graph, receipt, course = (
                    _runtime_release_adoption._adopt_catalog_profile(
                        mx, run_dir, receipt, course_a, source_root, graph,
                        params, optimizer, catalog_transition,
                        reserve_gib=reserve_gib,
                        allow_mastery_debt=admit_next_grade_with_debt))
            receipt = _runtime_reconciliation._repair_championship_source_context(run_dir, receipt, course)
        else:
            if numeric_staircase:
                raise ValueError('NUMERIC_STAIRCASE_REQUIRES_RESUME')
            params, optimizer, graph, receipt = _runtime_session._init(
                run_dir, manifest, course, teacher_sha,
                historical_teacher, provenance, source_checkpoint,
                source_root=source_root, reserve_gib=reserve_gib,
                permitted_preexisting=(
                    (".experiment-run.json",)
                    if experiment_budget is not None else ()))
        receipt, executable_release, schedule_program = _runtime_release_adoption._ensure_executable_release(
            run_dir, receipt, course, course_a, source_root, graph)
        with _runtime_timing_trace.trace_span("RECONCILE_VOCABULARY"):
            receipt = _runtime_reconciliation._reconcile_vocabulary_metadata(
                run_dir, receipt, course, params, optimizer, graph)
        learning_settings = (_learning_learning_experiment.Settings(
            probe_each=experiment_probe_each,
            mature_max_loss=experiment_mature_max_loss,
            introduction_extra_loss=experiment_introduction_extra_loss,
            protected_cap_limit=experiment_protected_cap_limit)
            if retention_enabled else None)
        with _runtime_timing_trace.trace_span("RECONCILE_LEARNING_SETTINGS"):
            receipt = _runtime_reconciliation._reconcile_learning_settings(
                run_dir, receipt, course, learning_settings, optimizer)
        if learning_settings is not None:
            with _runtime_timing_trace.trace_span("SEED_WHOLE_STUDENT_PEAK"):
                receipt = _runtime_reconciliation._seed_saved_whole_student_peak(
                    run_dir, receipt, course, optimizer)
        if learning_settings is not None:
            receipt = _runtime_frontier_refresh._refresh_fixed_frontier(
                mx, run_dir, receipt, course, params, optimizer)
        autonomy_session = None
        if autonomous_curriculum:
            from bilqis_mlx.runtime.autonomy_live import LiveAutonomySession
            autonomy_session = LiveAutonomySession.open(
                run_dir, source_root, executable_release)
        source_prefetch_executor = None
        if learning_settings is not None and source_prefetch_workers:
            from bilqis_mlx.runtime.source_prefetch import (
                source_prefetch_pool,
            )
            source_prefetch_executor = resources.enter_context(
                source_prefetch_pool(source_prefetch_workers))
        school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
        if autonomy_session is not None:
            autonomy_session.recover_teaching(
                receipt, school.current_student)
        if (stagnation_grace_grade is not None and
                stagnation_grace_grade not in set(school.active_grades)):
            raise ValueError("STAGNATION_GRACE_GRADE_NOT_ACTIVE")
        grace, grace_created = _learning_stagnation_control.reconcile_optimizer_step_grace(
            receipt.get("stagnation_grace"),
            requested_grade=stagnation_grace_grade,
            requested_steps=stagnation_grace_steps,
            optimizer_step=school.current_student.optimizer_step)
        if grace != receipt.get("stagnation_grace"):
            receipt = _runtime_checkpoints._advance(
                run_dir, {**receipt, "stagnation_grace": grace}, school,
                result=receipt["result"])
            if grace_created:
                _runtime_checkpoints._record(run_dir, {
                    "event": "SCHOOL_STAGNATION_GRACE_CONFIGURED",
                    "generation": receipt["generation"],
                    "grade": grace["grade"],
                    "started_optimizer_step": grace["started_optimizer_step"],
                    "optimizer_step_budget": grace["optimizer_step_budget"],
                    "until_optimizer_step": grace["until_optimizer_step"],
                    "reason": grace["reason"],
                    "model_and_optimizer_unchanged": True,
                })
        previous_stagnation = receipt.get("stagnation_session")
        prior_debt = _learning_stagnation_control.quarantined_capabilities(previous_stagnation)
        school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
        deferred_before_reentry = school.stage == "DEFERRED_STAGNATION"
        if prior_debt and deferred_before_reentry:
            school = _curriculum_scheduler.reactivate_stagnation_debt(_runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school, prior_debt)
            receipt = {**receipt, "school": _dataclasses.asdict(school)}
        history = list(receipt.get("stagnation_history", ()))
        if previous_stagnation is not None:
            history.append({
                "session_id": previous_stagnation["session_id"],
                "started_generation": previous_stagnation["started_generation"],
                "ended_before_generation": receipt["generation"],
                "quarantined": list(prior_debt),
                "alerts": list(_learning_stagnation_control.end_of_run_alerts(previous_stagnation)),
            })
        receipt["stagnation_history"] = history[-16:]
        receipt["stagnation_session"] = _learning_stagnation_control.start_session(
            session_id=_uuid.uuid4().hex, generation=receipt["generation"],
            required_capabilities=_curriculum_scheduler.assessment_capabilities(
                _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course), school),
            progress_checkpoint=_dataclasses.asdict(school.current_student))
        debt_grades = {capability.partition(".")[0] for capability in prior_debt}
        grace_reentry = _learning_stagnation_control.grace_suppressed_capabilities(
            receipt.get("stagnation_grace"), required_capabilities=tuple(prior_debt),
            optimizer_step=school.current_student.optimizer_step)
        if (prior_debt and deferred_before_reentry and len(debt_grades) == 1 and
                set(grace_reentry) != set(prior_debt)):
            receipt["stagnation_session"], rehabilitation_event = (
                _learning_stagnation_control.activate_sole_grade_rehabilitation(
                    receipt["stagnation_session"],
                    capabilities=tuple(prior_debt),
                    generation=receipt["generation"]))
            pending = list(receipt.get("_pending_visit_events", ()))
            pending.append(rehabilitation_event)
            receipt["_pending_visit_events"] = pending
        school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
        _runtime_checkpoints._record(run_dir, {
            "event": "SCHOOL_SESSION_STARTED",
            "generation": receipt["generation"],
            "run_id": receipt["run_id"],
            "grade": school.grade,
            "grade_phase": school.stage,
            "optimizer_step": school.current_student.optimizer_step,
            "checkpoint_sha256": school.current_student.sha256,
            "committed_total_visits": school.visits,
            "source_prefetch_workers": (source_prefetch_workers
                                         if source_prefetch_executor is not None else 0),
            "flash_mode": flash_mode,
            "boolean_association_bridge": boolean_association_bridge,
            "autonomous_curriculum": autonomous_curriculum,
        })
        visits = 0
        while True:
            if experiment_budget is not None:
                experiment_budget.assert_can_allocate(600_000_000)
            final_numeric_scope = receipt.get("numeric_scope_final_maximum")
            if final_numeric_scope is not None:
                admitted_v2 = _runtime_admission._require_executable_factory_admission(
                    run_dir, receipt, graph)
                active_program = _factory_schedule.schedule_program_from_executable_release(
                    admitted_v2)
                active_school = _runtime_state._state_from_json(
                    receipt["school"], active_program)
                next_numeric_profile = _profiles_catalog.next_numeric_scope_profile(
                    admitted_v2, final_maximum=final_numeric_scope)
                if (next_numeric_profile is not None and
                        active_school.stage == "AWAITING_NEXT_GRADE"):
                    receipt, course, executable_release, schedule_program = (
                        _runtime_release_adoption._adopt_executable_profile(
                            run_dir, receipt, course_a, source_root, graph,
                            next_numeric_profile))
            school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
            receipt = _runtime_reconciliation._reconcile_stagnation_scope(
                run_dir, receipt, course, school)
            school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
            autonomy_teaching_work = None
            budget_reason = _runtime_session.session_stop_reason(
                stage="MAIN", elapsed_seconds=_time.monotonic() - start, minutes=minutes,
                visits=visits, max_visits=max_visits)
            if (autonomy_session is not None and school.stage == "AWAITING_NEXT_GRADE" and
                    budget_reason is None):
                autonomy_session.refresh_release(
                    _runtime_admission._read_executable_factory_release_artifact(run_dir, receipt))
                proposal, proposal_file = autonomy_session.propose_source_frontier_work(
                    school.current_student, graph)
                if proposal.disposition.value == "PROPOSAL":
                    params, optimizer, graph, receipt, course = _runtime_release_adoption._adopt_jit_proposal(
                        mx, run_dir, receipt, course_a, source_root, graph, params, optimizer,
                        autonomy_session, proposal, reserve_gib=reserve_gib)
                    autonomy_session.refresh_release(
                        _runtime_admission._read_executable_factory_release_artifact(run_dir, receipt))
                    _runtime_checkpoints._record(run_dir, {
                        "event": "SCHOOL_AUTONOMY_JIT_PROPOSAL_ADOPTED",
                        "generation": receipt["generation"],
                        "proposal_sha256": proposal.proposal_sha256,
                        "proposal_file": proposal_file,
                        "factory_release_sha256": receipt["factory_release_sha256"],
                        "actual_neural_updates": 0,
                    })
                    continue
            reason = _runtime_session.session_stop_reason(
                stage=("MAIN" if autonomy_session is not None and
                       school.stage == "AWAITING_NEXT_GRADE" else school.stage),
                elapsed_seconds=_time.monotonic() - start,
                minutes=minutes, visits=visits, max_visits=max_visits,
                grade=school.grade, flash_mode=flash_mode)
            if reason is not None:
                break
            if school.stage.startswith("ASSESS_"):
                if flash_mode:
                    # Flash may skip expensive championship/promotion work, but
                    # it may not skip the fresh cumulative evidence needed to
                    # choose recovery work or advance the cross-grade spiral.
                    receipt = _runtime_boundary_commit._flush_flash_student(
                        run_dir, receipt, course, params, optimizer, graph,
                        reserve_gib=reserve_gib)
                    receipt = _runtime_exam_execution._take_exam(
                        mx, run_dir, receipt, manifest, course, source_root,
                        source_checkpoint, params, optimizer, graph,
                        reserve_gib=reserve_gib, scheduler_only=True,
                        session_elapsed_seconds=_time.monotonic() - start)
                    if experiment_budget is not None:
                        experiment_budget.assert_can_allocate(0)
                    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
                    if school.stage.startswith("ASSESS_"):
                        # Scheduler-only evidence found no remaining imperfect
                        # grade. Preserve the qualification debt for a full
                        # authoritative exam rather than minting mastery in flash.
                        reason = "FLASH_QUALIFICATION_REQUIRED"
                        break
                    continue
                with _runtime_timing_trace.trace_span(
                        "ASSESSMENT", generation=receipt["generation"],
                        phase=school.stage, grade=school.grade):
                    receipt = _runtime_exam_execution._take_exam(
                        mx, run_dir, receipt, manifest, course, source_root,
                        source_checkpoint, params, optimizer, graph,
                        reserve_gib=reserve_gib,
                        session_elapsed_seconds=_time.monotonic() - start)
                if experiment_budget is not None:
                    experiment_budget.assert_can_allocate(0)
                continue
            if autonomous_curriculum:
                from bilqis_mlx.factory.autonomy import (
                    AutonomyActionKind)
                from bilqis_mlx.runtime.autonomy_live import scheduled_teaching_matches

                current_release = _runtime_admission._read_executable_factory_release_artifact(run_dir, receipt)
                autonomy_session.refresh_release(current_release)
                action = autonomy_session.action(school.current_student)
                if action.deferred_obligation_ids:
                    selected_work = (
                        action.evidence_work or
                        (action.teaching_work
                         if action.kind is AutonomyActionKind.TEACHING
                         else None))
                    _runtime_checkpoints._record(run_dir, {
                        "event": "SCHOOL_AUTONOMY_REMEDIATION_DEFERRED",
                        "generation": receipt["generation"],
                        "grade": school.grade,
                        "deferred_obligations":
                            list(action.deferred_obligation_ids),
                        "selected_capability": (
                            selected_work.capability_id
                            if selected_work is not None else None),
                        "student_sha256": school.current_student.sha256,
                        "optimizer_step":
                            school.current_student.optimizer_step,
                        "actual_neural_updates": 0,
                    })
                if action.kind is AutonomyActionKind.SAFE_HOLD:
                    frontier_result = (
                        autonomy_session.propose_source_frontier_work(
                            school.current_student, graph))
                    if frontier_result is not None:
                        proposal, proposal_file = frontier_result
                        reason = (
                            _bilqis_mlx_operator_vocabulary.AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED.code
                            if proposal.disposition.value ==
                            "SOURCE_DEVELOPMENT"
                            else "AUTONOMY_JIT_PROPOSAL_READY")
                        _runtime_checkpoints._record(run_dir, {
                            "event": (
                                "SCHOOL_AUTONOMY_SOURCE_DEVELOPMENT_REQUIRED"
                                if proposal.disposition.value ==
                                "SOURCE_DEVELOPMENT"
                                else "SCHOOL_AUTONOMY_JIT_PROPOSAL_READY"),
                            "generation": receipt["generation"],
                            "grade": school.grade,
                            "deferred_obligations":
                                list(action.deferred_obligation_ids),
                            "proposal_sha256": proposal.proposal_sha256,
                            "proposal_file": proposal_file,
                            "frontier_sha256": proposal.frontier_sha256,
                            "candidate_gate_count":
                                len(proposal.candidate_gates),
                            "selected_candidate_ids":
                                list(proposal.selected_candidate_ids),
                            "student_sha256":
                                school.current_student.sha256,
                            "optimizer_step":
                                school.current_student.optimizer_step,
                            "model_and_optimizer_unchanged": True,
                        })
                    else:
                        reason = _bilqis_mlx_operator_vocabulary.AUTONOMY_SAFE_HOLD.code
                        _runtime_checkpoints._record(run_dir, {
                            "event": "SCHOOL_AUTONOMY_SAFE_HOLD",
                            "generation": receipt["generation"],
                            "grade": school.grade,
                            "deferred_obligations":
                                list(action.deferred_obligation_ids),
                            "student_sha256":
                                school.current_student.sha256,
                            "optimizer_step":
                                school.current_student.optimizer_step,
                            "model_and_optimizer_unchanged": True,
                        })
                    break
                if action.kind is AutonomyActionKind.SOURCE_COVERAGE:
                    reason = "AUTONOMY_SOURCE_COVERAGE_REQUIRED"
                    _runtime_checkpoints._record(run_dir, {
                        "event": "SCHOOL_AUTONOMY_SOURCE_COVERAGE_BLOCKED",
                        "generation": receipt["generation"],
                        "grade": school.grade,
                        "debt": action.source_coverage_debt,
                        "model_and_optimizer_unchanged": True,
                    })
                    break
                if action.kind is AutonomyActionKind.LEARNING_EVIDENCE:
                    optimizer_step = int(optimizer.state["step"].item())
                    if optimizer_step != school.current_student.optimizer_step:
                        raise ValueError(
                            "AUTONOMY_EVIDENCE_REQUIRES_DURABLE_CHECKPOINT")
                    work = action.evidence_work
                    evidence = autonomy_session.measure(
                        graph, work,
                        checkpoint={
                            **_dataclasses.asdict(school.current_student),
                            "model_and_native_adamw": True,
                        },
                        seed=_runtime_state._seed(
                            receipt,
                            capability="AUTONOMY_EVIDENCE:" +
                            work.obligation.obligation_id,
                            step=len(autonomy_session.ledger.receipts) + 1),
                        predictor=lambda rows: _learning_student_ops._predictions(
                            mx, params, list(rows), receipt["config"],
                            receipt["answer_ids"]),
                    )
                    _runtime_checkpoints._record(run_dir, {
                        "event": "SCHOOL_AUTONOMY_EVIDENCE_RECORDED",
                        "generation": receipt["generation"],
                        "grade": school.grade,
                        "capability": work.capability_id,
                        "obligation": work.obligation.obligation_id,
                        "passed": evidence.passed,
                        "cohort_sha256": evidence.cohort_sha256,
                        "student_sha256": evidence.checkpoint_sha256,
                        "optimizer_step": evidence.optimizer_step,
                    })
                    if evidence.passed:
                        advanced = autonomy_session.advance_if_complete(
                            school, work.capability_id)
                        if advanced != school:
                            receipt = _runtime_checkpoints._advance(
                                run_dir, receipt, advanced,
                                result=_runtime_exam_execution._school_result_label(advanced))
                            visits += 1
                            _runtime_checkpoints._record(run_dir, {
                                "event":
                                    "SCHOOL_AUTONOMY_EVIDENCE_VISIT_COMPLETED",
                                "generation": receipt["generation"],
                                "grade": advanced.grade,
                                "capability": work.capability_id,
                                "optimizer_step":
                                    advanced.current_student.optimizer_step,
                                "student_sha256":
                                    advanced.current_student.sha256,
                                "retained_optimizer_updates": 0,
                            })
                    continue
                if action.kind is AutonomyActionKind.QUALIFICATION:
                    scheduled = _curriculum_scheduler.next_capability(school)
                    if (scheduled is not None and
                            scheduled in set(autonomy_session.evidence_complete(school.current_student))):
                        advanced = _curriculum_scheduler.visit(
                            course, school, scheduled,
                            school.current_student)
                        receipt = _runtime_checkpoints._advance(
                            run_dir, receipt, advanced,
                            result=_runtime_exam_execution._school_result_label(advanced))
                        visits += 1
                        _runtime_checkpoints._record(run_dir, {
                            "event":
                                "SCHOOL_AUTONOMY_QUALIFIED_VISIT_COMPLETED",
                            "generation": receipt["generation"],
                            "grade": advanced.grade,
                            "capability": scheduled,
                            "optimizer_step":
                                advanced.current_student.optimizer_step,
                            "student_sha256":
                                advanced.current_student.sha256,
                            "retained_optimizer_updates": 0,
                        })
                        continue
                elif action.kind is AutonomyActionKind.TEACHING:
                    target = action.teaching_work.capability_id
                    if not scheduled_teaching_matches(school, target):
                        rerouted = autonomy_session.reroute_teaching(
                            school, target)
                        receipt = _runtime_checkpoints._advance(
                            run_dir, receipt, rerouted,
                            result=_runtime_exam_execution._school_result_label(rerouted))
                        school = rerouted
                        _runtime_checkpoints._record(run_dir, {
                            "event": "SCHOOL_AUTONOMY_TEACHING_REROUTED",
                            "generation": receipt["generation"],
                            "grade": school.grade,
                            "capability": target,
                            "student_sha256": school.current_student.sha256,
                            "optimizer_step":
                                school.current_student.optimizer_step,
                            "actual_neural_updates": 0,
                        })
                    if not scheduled_teaching_matches(school, target):
                        raise ValueError(
                            "AUTONOMY_TEACHING_REROUTE_FAILED")
                    autonomy_teaching_work = action.teaching_work
            with _runtime_timing_trace.trace_span("DISK_HEADROOM", visit_index=visits + 1):
                budget = _runtime_disk.headroom_snapshot(run_dir, required_bytes=600_000_000,
                                           reserve_gib=reserve_gib)
            if not budget["sufficient"]:
                reason = "DISK_RESERVE_REACHED"
                break
            # Retain the original fail-closed checkpoint preflight against
            # disk changes between telemetry and the actual write boundary.
            with _runtime_timing_trace.trace_span("DISK_HEADROOM_ASSERT", visit_index=visits + 1):
                _runtime_disk.assert_headroom(run_dir, required_bytes=600_000_000,
                                reserve_gib=reserve_gib)
            with _runtime_timing_trace.trace_span(
                    "VISIT_TOTAL", visit_index=visits + 1,
                    generation=receipt["generation"], phase=school.stage,
                    grade=school.grade):
                parent_for_visit = school
                pending_before = len(receipt.get("_pending_visit_events", ()))
                receipt = _runtime_visits._take_visit(
                    mx, run_dir, receipt, manifest, course, engine,
                    params, optimizer, graph, steps_per_visit=steps_per_visit,
                    batch_size=batch_size, reserve_gib=reserve_gib,
                    source_root=source_root, learning_settings=learning_settings,
                    boolean_association_bridge=boolean_association_bridge,
                    autonomy_teaching_option=(autonomy_teaching_work.teaching_option_ids[0]
                                              if autonomy_teaching_work is not None else None),
                    source_prefetch_executor=source_prefetch_executor,
                    source_prefetch_workers=(source_prefetch_workers
                                             if source_prefetch_executor is not None else 0))
            visits += 1
            if autonomous_curriculum:
                # Autonomy evidence may only refer to a complete, read-back
                # verified model+AdamW checkpoint. Publish every autonomous
                # teaching visit immediately instead of carrying RAM-only state.
                autonomy_visit = (receipt.get("_pending_visit_events") or [{}])[-1]
                delivery = autonomy_visit.get("autonomy_teaching")
                receipt = _runtime_boundary_commit._flush_working_student(
                    mx, run_dir, receipt, manifest, course,
                    params, optimizer, graph, reserve_gib=reserve_gib,
                    source_root=source_root)
                if experiment_budget is not None:
                    experiment_budget.assert_can_allocate(0)
                school_after_flush = _runtime_state._state_from_json(
                    receipt["school"],
                    _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
                if autonomy_teaching_work is not None:
                    failed = autonomy_teaching_work.failed_evidence
                    current = school_after_flush.current_student
                    durable_autonomy_visit = None
                    if delivery is not None:
                        digest = delivery.get("specimen_content_sha256")
                        durable_autonomy_visit = next((
                            event for event in reversed(
                                receipt.get("delivery_outbox", ()))
                            if (isinstance(
                                    event.get("autonomy_teaching"), dict) and
                                event["autonomy_teaching"].get(
                                    "specimen_content_sha256") == digest)
                        ), None)
                        if durable_autonomy_visit is None:
                            raise ValueError(
                                "AUTONOMY_TEACHING_DURABLE_EVENT_MISSING")
                    if (delivery is not None and
                            current.sha256 != failed.checkpoint_sha256 and
                            current.optimizer_step > failed.optimizer_step):
                        intervention = autonomy_session.recover_teaching(
                            receipt, current)
                        if intervention is None:
                            raise ValueError(
                                "AUTONOMY_TEACHING_DURABLE_RECEIPT_MISSING")
                        _runtime_checkpoints._record(run_dir, {
                            "event":
                                "SCHOOL_AUTONOMY_TEACHING_RECORDED",
                            "generation": receipt["generation"],
                            "grade": school_after_flush.grade,
                            "capability":
                                autonomy_teaching_work.capability_id,
                            "obligation": failed.obligation_id,
                            "parent_student_sha256":
                                failed.checkpoint_sha256,
                            "student_sha256": current.sha256,
                            "optimizer_step": current.optimizer_step,
                        })
                    elif (delivery is not None and
                            current.sha256 == failed.checkpoint_sha256 and
                            current.optimizer_step == failed.optimizer_step and
                            durable_autonomy_visit.get(
                                "retained_optimizer_updates") == 0):
                        rejected = (
                            autonomy_session.rejected_attempt_from_event(
                                durable_autonomy_visit, failed))
                        _runtime_checkpoints._record(run_dir, {
                            "event":
                                "SCHOOL_AUTONOMY_TEACHING_REJECTED_RECORDED",
                            "generation": receipt["generation"],
                            "grade": school_after_flush.grade,
                            "capability":
                                autonomy_teaching_work.capability_id,
                            "obligation": failed.obligation_id,
                            "attempt_id": rejected.attempt_id,
                            "retention_reason":
                                rejected.retention_reason,
                            "student_sha256": current.sha256,
                            "optimizer_step": current.optimizer_step,
                            "candidate_optimizer_step":
                                rejected.candidate_optimizer_step,
                            "retained_optimizer_updates": 0,
                        })
            pending_visits = receipt.get("_pending_visit_events", ())
            if len(pending_visits) > pending_before:
                latest_visit = pending_visits[-1]
                if type(latest_visit.get("attempted_optimizer_updates")) is int:
                    # Project the complete visit into the live dashboard now,
                    # but preserve the durable checkpoint-gated event ledger.
                    # The telemetry layer deduplicates this exact generation
                    # when the real receipt is published at the boundary.
                    _runtime_checkpoints._notify_viewer({
                        **latest_visit,
                        "_live_ephemeral": True,
                        "_dashboard_redraw": False,
                    })
            after_visit = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
        with _runtime_timing_trace.trace_span("FLUSH_FLASH_STUDENT" if flash_mode else "FLUSH_WORKING_STUDENT",
                        visits=visits):
            if experiment_budget is not None:
                experiment_budget.assert_can_allocate(600_000_000)
            if flash_mode:
                receipt = _runtime_boundary_commit._flush_flash_student(
                    run_dir, receipt, course, params, optimizer, graph,
                    reserve_gib=reserve_gib)
            else:
                receipt = _runtime_boundary_commit._flush_working_student(
                    mx, run_dir, receipt, manifest, course, params, optimizer, graph,
                    reserve_gib=reserve_gib, source_root=source_root)
        if experiment_budget is not None:
            experiment_budget.assert_can_allocate(0)
        school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
        budget = _runtime_disk.headroom_snapshot(run_dir, required_bytes=600_000_000,
                                   reserve_gib=reserve_gib)
        elapsed_seconds = round(_time.monotonic() - start, 3)
        stagnation_alerts = _learning_stagnation_control.end_of_run_alerts(receipt.get("stagnation_session"))
        stagnation_quarantined = _learning_stagnation_control.quarantined_capabilities(
            receipt.get("stagnation_session"))
        _runtime_checkpoints._record(run_dir, {
            "event": "SCHOOL_SESSION_STOPPED", "stop_reason": reason,
            "generation": receipt["generation"], "run_id": receipt["run_id"],
            "optimizer_step": school.current_student.optimizer_step,
            "checkpoint_sha256": school.current_student.sha256,
            "visits_this_command": visits, "committed_total_visits": school.visits,
            "minutes": minutes, "max_visits": max_visits,
            "elapsed_seconds": elapsed_seconds,
            "grade_phase": school.stage, "grade": school.grade,
            "source_prefetch_workers": (source_prefetch_workers
                                         if source_prefetch_executor is not None else 0),
            "flash_mode": flash_mode,
            "boolean_association_bridge": boolean_association_bridge,
            "autonomous_curriculum": autonomous_curriculum,
            "resume_required": school.stage != "AWAITING_NEXT_GRADE",
            "stagnation_session_id": receipt.get("stagnation_session", {}).get(
                "session_id"),
            "stagnation_quarantined": list(stagnation_quarantined),
            "stagnation_alerts": list(stagnation_alerts),
            **{k: budget[k] for k in ("free_bytes", "reserve_bytes", "estimated_write_bytes")},
        })
        # Reclaim superseded JSON snapshot storage after the committed stop
        # receipt. Lossless compression retains exact source bytes and SHA
        # readback; all complete model/AdamW checkpoints remain untouched.
        from bilqis_mlx.state_archive import compact_states
        try:
            with _runtime_timing_trace.trace_span("STATE_ARCHIVE_COMPACT"):
                maintenance = compact_states(run_dir, max_files=64)
        except (OSError, ValueError) as exc:
            maintenance = {"error": str(exc), "compressed_generations": 0}
            _runtime_checkpoints._record(run_dir, {"event": "SCHOOL_STATE_ARCHIVE_BLOCKED",
                              "generation": receipt["generation"],
                              "reason": str(exc)})
        _runtime_timing_trace.trace_mark(
            "OPERATE_END", stop_reason=reason, visits=visits,
            optimizer_step=school.current_student.optimizer_step)
        return {
            "status": receipt["result"],
            "stop_reason": reason,
            "elapsed_seconds": elapsed_seconds,
            "time_limit_minutes": minutes,
            "max_visits": max_visits,
            "disk_free_gib": round(budget["free_bytes"] / 1024**3, 3),
            "disk_reserve_gib": round(budget["reserve_bytes"] / 1024**3, 3),
            "disk_next_visit_gib": round(budget["estimated_write_bytes"] / 1024**3, 3),
            "grade": school.grade,
            "phase": school.stage,
            "visits_this_command": visits,
            "committed_total_visits": school.visits,
            "optimizer_step": school.current_student.optimizer_step,
            "checkpoint_sha256": school.current_student.sha256,
            "latest_exam": receipt["last_exam"],
            "stagnation_quarantined": list(stagnation_quarantined),
            "stagnation_alerts": list(stagnation_alerts),
            "stagnation_grace": receipt.get("stagnation_grace"),
            "experimental_retention": learning_settings is not None,
            "retention_enabled": learning_settings is not None,
            "source_prefetch_workers": (source_prefetch_workers
                                         if source_prefetch_executor is not None else 0),
            "flash_mode": flash_mode,
            "boolean_association_bridge": boolean_association_bridge,
            "state_archive": maintenance,
            "safe_resume_command": _runtime_session._resume_command(
                run_dir, source_root, learning_settings,
                boolean_association_bridge=boolean_association_bridge,
                autonomous_curriculum=autonomous_curriculum,
                source_prefetch_workers=source_prefetch_workers),
            "original_source_checkpoint_modified": False,
        }
