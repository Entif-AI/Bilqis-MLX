"""Focused helpers for developmental exam execution."""
from __future__ import annotations

import dataclasses as _dataclasses

import bilqis_mlx.factory.schedule as _factory_schedule
import bilqis_mlx.generated_assessment as _bilqis_mlx_generated_assessment
import bilqis_mlx.learning.champions as _learning_champions
import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.runtime.admission as _runtime_admission
import bilqis_mlx.runtime.assessment as _runtime_assessment
import bilqis_mlx.runtime.mlx_checkpoint as _runtime_mlx_checkpoint
import bilqis_mlx.runtime.state as _runtime_state
import bilqis_mlx.source_adapters.school as _source_adapters_school

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
            ("GRADE_" + school.grade + "_PROMOTED_WITH_DEBT_AWAITING_NEXT_GRADE")
            if school.stage == "AWAITING_NEXT_GRADE_WITH_DEBT" else
            ("GRADE_" + school.revalidation_target_grade +
             "_REVALIDATING_" + school.grade)
            if school.revalidation_target_grade else
            "ACTIVE_GRADE_" + school.grade)


def _promotion_due_after_routine(
        before, after, *, complete_assessment: bool = True) -> bool:
    """Whether the scheduler recorded a real grade qualification.

    Ordinary debt/recovery scheduling may move between grades and stages
    without satisfying the grade criterion. The scheduler increments the
    grade-exam epoch only when a complete assessment actually promotes the
    current grade, so use that durable authority rather than generic movement.
    """
    before_epoch = getattr(before, "grade_exam_epoch", None)
    after_epoch = getattr(after, "grade_exam_epoch", None)
    return (
        complete_assessment
        and type(before_epoch) is int
        and type(after_epoch) is int
        and after_epoch == before_epoch + 1
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
        assessment_epoch=school.grade_exam_epoch)
    guesses = _learning_student_ops._predictions(
        mx, parameters, list(cohort.rows), receipt["config"], receipt["answer_ids"])
    measured = _bilqis_mlx_generated_assessment.score(cohort, guesses, _dataclasses.asdict(school.current_student))
    return {**receipt, "debt_admission_boundary_exam": {
        **pointer,
        "boundary_schema": "bilqis.mlx.debt-admission-boundary/v2",
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "exam_rubric_sha256": pointer["rubric_sha256"],
        "assessment_scope_sha256": _runtime_state._fingerprint(full_scope),
        "source_exam_plane": "DEBT_ADMISSION_BOUNDARY",
        "scores": measured["scores"],
        "misses_for_teacher": list(measured["misses_for_teacher"]),
    }}
