"""Serialized operator session and school phase dispatch."""
from __future__ import annotations

from .topology_lifecycle import operator_topology
from .operator_session.operator_preflight import validate_operator_preflight
from .operator_session.operator_disk import operator_disk_ready
from .operator_session.operator_finish import finish_operator_session
from .operator_session.operator_stagnation import start_stagnation_session
from .operator_session.operator_setup import prepare_operator_session, configure_operator_session
from .operator_session.operator_visit import execute_operator_visit
from .operator_session.operator_autonomy import DispatchControl, dispatch_autonomy
from .operator_session.operator_profiles import numeric_entry_transition, resume_boolean_profile
from .operator_session.operator_iteration import prepare_operator_iteration


import bilqis_mlx.compatibility.live_releases as _compatibility_live_releases
import bilqis_mlx.operator_vocabulary as _bilqis_mlx_operator_vocabulary
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.experiment_runs as _runtime_experiment_runs
import bilqis_mlx.runtime.mlx_memory as _runtime_mlx_memory
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.session as _runtime_session
import bilqis_mlx.runtime.timing_trace as _runtime_timing_trace
import contextlib as _contextlib
import pathlib as _pathlib
import time as _time


def _stage_atlas_frontier_attempt(run_dir, receipt, proposal, proposal_file, *,
                                  record=_runtime_checkpoints._record):
    from .atlas_admission import stage_unleased_atlas_proposal
    result = stage_unleased_atlas_proposal(run_dir, proposal)
    record(run_dir, {
        "event": "SCHOOL_ATLAS_ADMISSION_STAGED", "generation": receipt["generation"],
        "proposal_sha256": result.proposal_sha256, "proposal_file": proposal_file,
        "lease_sha256": result.lease_sha256, "reason": result.reason,
        "operator_action": result.operator_action, "actual_neural_updates": 0,
    })
    return _bilqis_mlx_operator_vocabulary.ATLAS_ADMISSION_STAGED.code


def _numeric_entry_transition(release, graph, *, full_grade_b, experiment_budget):
    return numeric_entry_transition(release, graph, full_grade_b=full_grade_b,
        experiment_budget=experiment_budget)


def _resume_boolean_profile(run_dir, receipt, course_a, source_root, graph,
                            admitted_v2, *, full_grade_b, autonomous_curriculum):
    return resume_boolean_profile(run_dir, receipt, course_a, source_root, graph,
        admitted_v2, full_grade_b=full_grade_b, autonomous_curriculum=autonomous_curriculum)


def operate(run_dir: _pathlib.Path, source_root: _pathlib.Path, source_checkpoint: _pathlib.Path,
            manifest_path: _pathlib.Path, *, resume: bool = False, minutes: int = 90,
            max_visits: int = 0, steps_per_visit: int = 16,
            batch_size: int = 32, reserve_gib: float = 100., model_topology=None,
            numeric_staircase: bool = False,
            boolean_composite: bool = False,
            boolean_idboolops: bool = False,
            full_grade_b: bool = True,
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
            experiment_budget: _runtime_experiment_runs.ExperimentRunBudget | None = None, qualification=None) -> dict:
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
    validate_operator_preflight(
        run_dir=run_dir, minutes=minutes, steps_per_visit=steps_per_visit,
        max_visits=max_visits, batch_size=batch_size,
        source_prefetch_workers=source_prefetch_workers,
        stagnation_grace_grade=stagnation_grace_grade,
        stagnation_grace_steps=stagnation_grace_steps, resume=resume,
        flash_mode=flash_mode, boolean_composite=boolean_composite,
        boolean_idboolops=boolean_idboolops,
        boolean_association_bridge=boolean_association_bridge,
        admit_next_grade_with_debt=admit_next_grade_with_debt,
        numeric_staircase=numeric_staircase, autonomous_curriculum=autonomous_curriculum,
        retention_enabled=retention_enabled, experiment_budget=experiment_budget)
    model_topology = operator_topology(run_dir, resume=resume, requested=model_topology)
    import mlx.core as mx
    mx.set_default_device(mx.gpu)
    with _runtime_timing_trace.trace_span("PREPARE_SOURCE"):
        manifest, historical_course, engine, teacher_sha, historical_teacher, provenance = _runtime_session.prepare_source(
            source_root, source_checkpoint, manifest_path)
    course_a = _compatibility_live_releases.initial_course(historical_course)
    course_b = None
    course_c = None
    staircase_course = None
    course = course_a
    run_dir = _pathlib.Path(run_dir).expanduser().resolve()
    start = _time.monotonic()
    with _runtime_session.operator_lock(run_dir), _contextlib.ExitStack() as resources:
        _runtime_timing_trace.trace_mark("OPERATOR_LOCK_ACQUIRED")
        memory_policy = resources.enter_context(
            _runtime_mlx_memory.training_memory_policy(mx))
        _runtime_timing_trace.trace_mark("MLX_MEMORY_POLICY", **memory_policy)
        params, optimizer, graph, receipt, course = prepare_operator_session(
            resume=resume, run_dir=run_dir, manifest=manifest, historical_course=historical_course,
            course_a=course_a, source_root=source_root, teacher_sha=teacher_sha,
            historical_teacher=historical_teacher, provenance=provenance,
            source_checkpoint=source_checkpoint, course=course, numeric_staircase=numeric_staircase,
            reserve_gib=reserve_gib, model_topology=model_topology, qualification=qualification,
            experiment_budget=experiment_budget, mx=mx, full_grade_b=full_grade_b,
            autonomous_curriculum=autonomous_curriculum, admit_next_grade_with_debt=admit_next_grade_with_debt,

              _resume_boolean_profile=_resume_boolean_profile,
            _numeric_entry_transition=_numeric_entry_transition)
        receipt, executable_release, schedule_program = _runtime_release_adoption._ensure_executable_release(
            run_dir, receipt, course, course_a, source_root, graph)
        receipt, course, learning_settings, autonomy_session, source_prefetch_executor = configure_operator_session(
            schedule_program=schedule_program, run_dir=run_dir, receipt=receipt, params=params,
            optimizer=optimizer, graph=graph, experiment_probe_each=experiment_probe_each,
            experiment_mature_max_loss=experiment_mature_max_loss,
            experiment_introduction_extra_loss=experiment_introduction_extra_loss,
            experiment_protected_cap_limit=experiment_protected_cap_limit,
            retention_enabled=retention_enabled, mx=mx, autonomous_curriculum=autonomous_curriculum,
            source_root=source_root, executable_release=executable_release,
            source_prefetch_workers=source_prefetch_workers, resources=resources)
        receipt, school = start_stagnation_session(
            run_dir=run_dir, receipt=receipt, course=course, autonomy_session=autonomy_session,
            stagnation_grace_grade=stagnation_grace_grade,
            stagnation_grace_steps=stagnation_grace_steps,
            source_prefetch_workers=source_prefetch_workers,
            source_prefetch_executor=source_prefetch_executor, flash_mode=flash_mode,
            boolean_association_bridge=boolean_association_bridge,
            autonomous_curriculum=autonomous_curriculum)
        visits = 0
        while True:
            (control, reason, receipt, course, executable_release, schedule_program,
             params, optimizer, graph, school, autonomy_teaching_work) = prepare_operator_iteration(
                experiment_budget=experiment_budget, run_dir=run_dir, receipt=receipt,
                course_a=course_a, source_root=source_root, graph=graph, course=course,
                executable_release=executable_release, schedule_program=schedule_program,
                numeric_staircase=numeric_staircase, mx=mx, manifest=manifest, params=params,
                optimizer=optimizer, reserve_gib=reserve_gib, full_grade_b=full_grade_b,
                autonomy_session=autonomy_session, start=start, minutes=minutes, visits=visits,
                max_visits=max_visits, flash_mode=flash_mode, source_checkpoint=source_checkpoint, _stage_atlas_frontier_attempt=_stage_atlas_frontier_attempt)
            if control is DispatchControl.STOP:
                break
            if control is DispatchControl.CONTINUE:
                continue
            if autonomous_curriculum:
                control, reason, receipt, school, visits, autonomy_teaching_work = dispatch_autonomy(
                    autonomy_session=autonomy_session, school=school, graph=graph,
                    receipt=receipt, run_dir=run_dir, mx=mx, params=params, optimizer=optimizer,
                    course=course, visits=visits, autonomy_teaching_work=autonomy_teaching_work)
                if control is DispatchControl.STOP:
                    break
                if control is DispatchControl.CONTINUE:
                    continue
            if not operator_disk_ready(run_dir, reserve_gib, visits):
                reason = "DISK_RESERVE_REACHED"
                break
            receipt, visits = execute_operator_visit(
                mx=mx, run_dir=run_dir, receipt=receipt, manifest=manifest, course=course,
                engine=engine, params=params, optimizer=optimizer, graph=graph,
                steps_per_visit=steps_per_visit, batch_size=batch_size, reserve_gib=reserve_gib,
                source_root=source_root, learning_settings=learning_settings,
                boolean_association_bridge=boolean_association_bridge,
                autonomy_teaching_work=autonomy_teaching_work,
                source_prefetch_executor=source_prefetch_executor,
                source_prefetch_workers=source_prefetch_workers, visits=visits, school=school,
                autonomous_curriculum=autonomous_curriculum, experiment_budget=experiment_budget,
                autonomy_session=autonomy_session)
        return finish_operator_session(
            mx=mx, run_dir=run_dir, receipt=receipt, manifest=manifest, course=course,
            params=params, optimizer=optimizer, graph=graph, reserve_gib=reserve_gib,
            source_root=source_root, experiment_budget=experiment_budget,
            flash_mode=flash_mode, visits=visits, start=start, reason=reason,
            minutes=minutes, max_visits=max_visits,
            source_prefetch_workers=source_prefetch_workers,
            source_prefetch_executor=source_prefetch_executor,
            boolean_association_bridge=boolean_association_bridge,
            autonomous_curriculum=autonomous_curriculum, learning_settings=learning_settings)
