"""Dispatch autonomous evidence, teaching, and safe-hold work."""
import bilqis_mlx.operator_vocabulary as _bilqis_mlx_operator_vocabulary
import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import dataclasses as _dataclasses
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.runtime.admission as _runtime_admission
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.exam_execution as _runtime_exam_execution
import bilqis_mlx.runtime.state as _runtime_state
from enum import Enum, auto
from .autonomy_hold import _hold_autonomy


class DispatchControl(Enum):
    PROCEED = auto()
    CONTINUE = auto()
    COLD_RESUME = auto()
    STOP = auto()


def dispatch_autonomy(*, autonomy_session, school, graph, receipt, run_dir, mx,
                      params, optimizer, course, visits, autonomy_teaching_work):
    from bilqis_mlx.factory.autonomy import (
        AutonomyActionKind)
    from bilqis_mlx.runtime.autonomy_live import scheduled_teaching_matches

    current_release = _runtime_admission._read_executable_factory_release_artifact(run_dir, receipt)
    autonomy_session.refresh_release(current_release)
    action = autonomy_session.action(school.current_student)
    if action.deferred_obligation_ids:
        _record_deferred_action(action, school, receipt, run_dir, AutonomyActionKind)
    if action.kind is AutonomyActionKind.SAFE_HOLD:
        reason = _hold_autonomy(
            autonomy_session=autonomy_session,
            school=school,
            graph=graph,
            receipt=receipt,
            run_dir=run_dir,
            action=action, record=_runtime_checkpoints._record)
        return DispatchControl.STOP, reason, receipt, school, visits, autonomy_teaching_work
    if action.kind is AutonomyActionKind.SOURCE_COVERAGE:
        reason = "AUTONOMY_SOURCE_COVERAGE_REQUIRED"
        _runtime_checkpoints._record(run_dir, {
            "event": "SCHOOL_AUTONOMY_SOURCE_COVERAGE_BLOCKED",
            "generation": receipt["generation"],
            "grade": school.grade,
            "debt": action.source_coverage_debt,
            "model_and_optimizer_unchanged": True,
        })
        return DispatchControl.STOP, reason, receipt, school, visits, autonomy_teaching_work
    if action.kind is AutonomyActionKind.LEARNING_EVIDENCE:
        return _measure_autonomy(
            autonomy_session=autonomy_session,
            school=school,
            graph=graph,
            receipt=receipt,
            run_dir=run_dir,
            visits=visits,
            autonomy_teaching_work=autonomy_teaching_work,
            action=action,
            optimizer=optimizer,
            mx=mx,
            params=params)
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
            return DispatchControl.CONTINUE, None, receipt, school, visits, autonomy_teaching_work
    elif action.kind is AutonomyActionKind.TEACHING:
        receipt, school, autonomy_teaching_work = _route_teaching(
            autonomy_session=autonomy_session,
            school=school,
            receipt=receipt,
            run_dir=run_dir,
            action=action, scheduled_teaching_matches=scheduled_teaching_matches)
    return DispatchControl.PROCEED, None, receipt, school, visits, autonomy_teaching_work



def _measure_autonomy(*, autonomy_session, school, graph, receipt, run_dir, visits, autonomy_teaching_work, action, optimizer, mx, params):
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
    return DispatchControl.CONTINUE, None, receipt, school, visits, autonomy_teaching_work


def _route_teaching(*, autonomy_session, school, receipt, run_dir, action, scheduled_teaching_matches):
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
    return receipt, school, autonomy_teaching_work




def _record_deferred_action(action, school, receipt, run_dir, AutonomyActionKind):
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
