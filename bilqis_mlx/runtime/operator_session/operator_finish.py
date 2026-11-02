"""Flush and record the end of an operator session."""
import bilqis_mlx.learning.stagnation_control as _learning_stagnation_control
import bilqis_mlx.runtime.boundary_commit as _runtime_boundary_commit
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.disk as _runtime_disk
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.session as _runtime_session
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.runtime.timing_trace as _runtime_timing_trace
import time as _time


def finish_operator_session(*, mx, run_dir, receipt, manifest, course, params,
                            optimizer, graph, reserve_gib, source_root,
                            experiment_budget, flash_mode, visits, start,
                            reason, minutes, max_visits, source_prefetch_workers,
                            source_prefetch_executor, boolean_association_bridge,
                            autonomous_curriculum, learning_settings):
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
        "resume_required": school.stage not in ("AWAITING_NEXT_GRADE", "AWAITING_NEXT_GRADE_WITH_DEBT"),
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
