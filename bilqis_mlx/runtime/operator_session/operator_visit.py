"""Execute one operator visit and its durable autonomy receipts."""
import bilqis_mlx.runtime.boundary_commit as _runtime_boundary_commit
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.runtime.timing_trace as _runtime_timing_trace
import bilqis_mlx.runtime.visits as _runtime_visits


def execute_operator_visit(*, mx, run_dir, receipt, manifest, course, engine, params,
                           optimizer, graph, steps_per_visit, batch_size, reserve_gib,
                           source_root, learning_settings, boolean_association_bridge,
                           autonomy_teaching_work, source_prefetch_executor,
                           source_prefetch_workers, visits, school, autonomous_curriculum,
                           experiment_budget, autonomy_session):
    with _runtime_timing_trace.trace_span(
            "VISIT_TOTAL", visit_index=visits + 1,
            generation=receipt["generation"], phase=school.stage,
            grade=school.grade):
        parent_for_visit = school
        pending_before = len(receipt.get("_pending_visit_events", ()))
        _runtime_checkpoints._notify_viewer({"_runtime_phase": "VISITING", "_dashboard_redraw": True})
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
    return receipt, visits
