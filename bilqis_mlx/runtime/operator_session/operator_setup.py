"""Prepare the admitted student and session resources under the operator lock."""
import bilqis_mlx.factory.schedule as _factory_schedule
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.profiles.catalog as _profiles_catalog
import bilqis_mlx.runtime.admission as _runtime_admission
import bilqis_mlx.runtime.exam_execution as _runtime_exam_execution
import bilqis_mlx.runtime.frontier_refresh as _runtime_frontier_refresh
import bilqis_mlx.runtime.reconciliation as _runtime_reconciliation
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.session as _runtime_session
import bilqis_mlx.runtime.timing_trace as _runtime_timing_trace


def prepare_operator_session(*, resume, run_dir, manifest, historical_course, course_a,
                             source_root, teacher_sha, historical_teacher, provenance,
                             source_checkpoint, course, numeric_staircase, reserve_gib,
                             model_topology, qualification, experiment_budget, mx,
                             full_grade_b, autonomous_curriculum, admit_next_grade_with_debt,
                             _resume_boolean_profile,
                             _numeric_entry_transition):
    if resume:
        params, optimizer, graph, receipt, course = _runtime_session._resume_admitted_student(
            run_dir, manifest, historical_course, course_a, source_root, teacher_sha)
        admitted_v2 = _runtime_admission._require_executable_factory_admission(
            run_dir, receipt, graph)
        receipt, _, admitted_v2, _ = (
            _runtime_release_adoption._adopt_source_presentation_revision_if_needed(
                run_dir, receipt, course_a, source_root, graph, admitted_v2))
        receipt, course, admitted_v2 = _resume_boolean_profile(
            run_dir, receipt, course_a, source_root, graph, admitted_v2,
            full_grade_b=full_grade_b,
            autonomous_curriculum=autonomous_curriculum)
        admitted_v2 = _runtime_admission._require_executable_factory_admission(
            run_dir, receipt, graph)
        course = _factory_schedule.schedule_program_from_executable_release(admitted_v2)
        if (admit_next_grade_with_debt and
                len(admitted_v2.execution_plan.grades) == 2 and
                len(admitted_v2.curriculum.grades) > 2):
            if admit_next_grade_with_debt:
                receipt = _runtime_exam_execution._measure_debt_admission_boundary(
                    mx, run_dir, receipt, manifest, course, source_root,
                    params, graph)
            catalog_transition = _numeric_entry_transition(
                admitted_v2, graph, full_grade_b=full_grade_b,
                experiment_budget=experiment_budget)
            params, optimizer, graph, receipt, course = (
                _runtime_release_adoption._adopt_catalog_profile(
                    mx, run_dir, receipt, course_a, source_root, graph,
                    params, optimizer, catalog_transition,
                    reserve_gib=reserve_gib,
                    allow_mastery_debt=admit_next_grade_with_debt))
        admitted_v2 = _runtime_admission._require_executable_factory_admission(
            run_dir, receipt, graph)
        course = _factory_schedule.schedule_program_from_executable_release(admitted_v2)
        receipt = _runtime_reconciliation._repair_championship_source_context(run_dir, receipt, course)
    else:
        if numeric_staircase:
            raise ValueError('NUMERIC_STAIRCASE_REQUIRES_RESUME')
        params, optimizer, graph, receipt = _runtime_session._init(
            run_dir, manifest, course, teacher_sha,
            historical_teacher, provenance, source_checkpoint,
            source_root=source_root, reserve_gib=reserve_gib, model_topology=model_topology, qualification=qualification,
            permitted_preexisting=(
                (".experiment-run.json",)
                if experiment_budget is not None else ()))
    if experiment_budget is not None and receipt.get("numeric_scope_final_maximum") is None:
        receipt = {**receipt, "numeric_scope_final_maximum":
                   _profiles_catalog.numeric_scope_bounds()[0]}
    params, optimizer, graph, receipt, course, _ = (
        _runtime_release_adoption._auto_adopt_known_grade_boundary(
            mx, run_dir, receipt, course, course_a, source_root, manifest,
            params, optimizer, graph, reserve_gib=reserve_gib,
            full_grade_b=full_grade_b, numeric_staircase=numeric_staircase))
    return params, optimizer, graph, receipt, course


def configure_operator_session(*, schedule_program, run_dir, receipt, params, optimizer,
                               graph, experiment_probe_each, experiment_mature_max_loss,
                               experiment_introduction_extra_loss, experiment_protected_cap_limit,
                               retention_enabled, mx, autonomous_curriculum, source_root,
                               executable_release, source_prefetch_workers, resources):
    course = schedule_program
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
    return receipt, course, learning_settings, autonomy_session, source_prefetch_executor
