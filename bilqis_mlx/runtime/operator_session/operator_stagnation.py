"""Set up the operator session's stagnation and reentry state."""
import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import dataclasses as _dataclasses
import bilqis_mlx.learning.stagnation_control as _learning_stagnation_control
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import uuid as _uuid


def start_stagnation_session(*, run_dir, receipt, course, autonomy_session,
                             stagnation_grace_grade, stagnation_grace_steps,
                             source_prefetch_workers, source_prefetch_executor,
                             flash_mode, boolean_association_bridge,
                             autonomous_curriculum):
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
    return receipt, school
