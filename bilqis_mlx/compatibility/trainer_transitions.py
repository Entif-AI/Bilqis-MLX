"""Historical Course migrations and sanctioned A/B/C admission policy.

Legacy Course functions preserve immutable v1 evidence. Known A/B/C entry at
mean-stability boundaries delegates to the executable factory release owners;
unknown future grades retain their separate admission boundary.
"""
from __future__ import annotations

import bilqis_mlx.runtime.admission as _runtime_admission
import bilqis_mlx.runtime.exam_execution as _runtime_exam_execution
import bilqis_mlx.factory.schedule as _factory_schedule
import bilqis_mlx.profiles.school as _profiles_school
import bilqis_mlx.profiles.catalog as _profiles_catalog
import dataclasses as _dataclasses

import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state

from copy import deepcopy
from dataclasses import asdict, replace

from ..curriculum.scheduler import (
    append_next_grade,
    assessment_capabilities,
    replace_admitted_grade,
    revise_admitted_grade,
)
from .live_releases import (
    BOOLEAN_IDENTIFICATION_RELEASE,
    MINIMAL_BOOLEAN_RELEASE,
    legacy_receipt_fields,
    rebind_same_grade_config,
    release_code_digest,
)
from ..learning.championship_identity import (
    build_school_identity,
    enforce_school_identity,
)
from ..live_curriculum import assessment_rubric_for_scope
from ..runtime.admission import _factory_admission
from .source_adapters import historical_source_registry


def _next_grade_admission_event(record, school, current_grade: str,
                                introduced_grade: str, successor, epoch: dict,
                                history: list, compatibility: dict,
                                release_sha256: str) -> dict:
    return {
        "event": "SCHOOL_NEXT_GRADE_COURSE_ADMITTED",
        "generation": record["generation"],
        "grade": introduced_grade,
        "previous_cohort_sha256":
            (record.get("last_exam") or {}).get("cohort_sha256"),
        "previous_grade": current_grade,
        "previous_grade_champion_sha256": school.champions[current_grade].sha256,
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "teacher_events": record["teacher"]["events"],
        "championship_baseline_sha256": epoch["baseline"]["sha256"],
        "archived_championship_epochs": len(history),
        "introduced_grade_rubric": successor.grades[-1].assessment_sha256,
        "release_provider_sha256": release_code_digest(successor.version),
        "factory_release_sha256": release_sha256,
        **compatibility,
        "model_and_own_adamw_unchanged": True,
    }


def activate_next_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    school = _runtime_state._state_from_json(
        receipt["school"],
        _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, previous_course))
    current_grade = previous_course.grades[-1].id
    if (not successor.executable or
            len(successor.grades) != len(previous_course.grades) + 1 or
            successor.grades[:-1] != previous_course.grades or
            school.stage != "AWAITING_NEXT_GRADE" or
            school.grade != current_grade or
            current_grade not in school.champions or
            receipt.get("curriculum_mode") != previous_course.version):
        raise ValueError("HUMAN_TRAINER_NEXT_GRADE_ADMISSION_BOUNDARY_NOT_MET")
    legacy_school = replace(school, course_digest=previous_course.digest())
    next_state = append_next_grade(previous_course, successor, legacy_school)
    from ..learning.mentor_epoch import begin_epoch
    exam = receipt.get("last_exam") or {}
    prior_caps = tuple(
        cap.id for grade in previous_course.grades for cap in grade.capabilities)
    epoch = begin_epoch(
        previous_graduate=asdict(school.current_student),
        admitted_baseline=asdict(next_state.current_student),
        introduced_grade=successor.grades[-1].id,
        source_graph_sha256=receipt["semantic_graph_sha256"],
        previous_capabilities=prior_caps,
        previous_graduation_exam={
            "checkpoint_sha256": exam.get("student_sha256"),
            "rubric_sha256": exam.get("exam_rubric_sha256"),
            "cohort_sha256": exam.get("cohort_sha256"),
            "scores": exam.get("scores"),
        })
    history = list(receipt.get("championship_epoch_history", ()))
    if receipt.get("mentor_epoch") is not None:
        history.append(receipt["mentor_epoch"])
    release, release_file, admission = _factory_admission(
        run_dir, successor, next_state.current_student,
        receipt["semantic_graph_sha256"],
        registry=historical_source_registry())
    settled = deepcopy(
        (receipt.get("mentor_epoch") or {}).get("settled_matchups", {}))
    identity = build_school_identity(
        course_sha256=successor.digest(),
        semantic_graph_sha256=receipt["semantic_graph_sha256"],
        parameter_shapes=receipt["parameter_shapes"],
        factory_release_sha256=release.release_sha256)
    epoch["settled_matchups"] = settled
    epoch["championship_school_identity"] = identity
    compatibility = legacy_receipt_fields(successor.version)
    config_update = {}
    if successor.version == MINIMAL_BOOLEAN_RELEASE:
        if not isinstance(graph, dict):
            raise ValueError("HUMAN_TRAINER_MINIMAL_GRADE_B_REQUIRES_GRAPH")
        config_update["config"] = rebind_same_grade_config(
            successor.version, receipt["config"], graph)
    candidate = {
        **receipt,
        **compatibility,
        "curriculum_mode": successor.version,
        **config_update,
        "live_rubric_sha256": assessment_rubric_for_scope(
            successor, assessment_capabilities(successor, next_state)),
        "factory_release_sha256": release.release_sha256,
        "factory_release_file": release_file,
        "factory_admission": asdict(admission),
        "championship_school_identity": identity,
        "mentor_epoch": epoch,
        "championship_epoch_history": history,
    }
    introduced_grade = successor.grades[-1].id
    record = _runtime_checkpoints._advance(
        run_dir, candidate, next_state,
        result="ACTIVE_GRADE_" + introduced_grade, persist=False)
    admitted = _next_grade_admission_event(
        record, school, current_grade, introduced_grade, successor, epoch,
        history, compatibility, release.release_sha256)
    record = _runtime_checkpoints._persist(
        run_dir, _runtime_checkpoints._with_delivery_outbox(record, (admitted,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
    return record


def activate_revised_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    return _runtime_release_adoption._activate_revised_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


def activate_replaced_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    return _runtime_release_adoption._activate_replaced_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


def _auto_adopt_known_grade_boundary(
        mx, run_dir, receipt, course, grade_a_course, source_root, manifest,
        parameters, optimizer, graph, *, reserve_gib, full_grade_b,
        numeric_staircase):
    """Consume a canonical grade boundary when its sanctioned transition exists."""
    release = _runtime_admission._require_executable_factory_admission(run_dir, receipt, graph)
    program = _factory_schedule.schedule_program_from_executable_release(release)
    school = _runtime_state._state_from_json(receipt["school"], program)
    if school.stage not in (
            "AWAITING_NEXT_GRADE", "AWAITING_NEXT_GRADE_WITH_DEBT"):
        return parameters, optimizer, graph, receipt, course, False

    active_grades = tuple(grade.grade_id for grade in release.execution_plan.grades)
    next_grade = (release.curriculum.grades[len(active_grades)].grade_id
                  if len(active_grades) < len(release.curriculum.grades) else None)
    if active_grades == ("A",) and next_grade == "B":
        if school.stage == "AWAITING_NEXT_GRADE_WITH_DEBT":
            receipt = _runtime_exam_execution._measure_debt_admission_boundary(
                mx, run_dir, receipt, manifest, course, source_root, parameters, graph)
        target = _profiles_school.with_disabled_future_grades(
            _profiles_school.boolean_entry_profile(full=full_grade_b),
            tuple(grade.grade_id for grade in release.curriculum.grades[2:]))
        receipt, course, _, _ = _runtime_release_adoption._adopt_executable_profile(
            run_dir, receipt, grade_a_course, source_root, graph, target, allow_mastery_debt=(school.stage == "AWAITING_NEXT_GRADE_WITH_DEBT"))
        return parameters, optimizer, graph, receipt, course, True

    if active_grades == ("A", "B") and next_grade == "C":
        allow_debt = school.stage == "AWAITING_NEXT_GRADE_WITH_DEBT"
        if allow_debt:
            receipt = _runtime_exam_execution._measure_debt_admission_boundary(
                mx, run_dir, receipt, manifest, course, source_root,
                parameters, graph)
        transition = _profiles_catalog.numeric_entry_transition(
            release, graph, full_boolean=full_grade_b,
            maximum=(3 if numeric_staircase or
                     receipt.get("numeric_scope_final_maximum") is not None else 10))
        if receipt.get("numeric_scope_final_maximum") is not None:
            transition = _dataclasses.replace(transition,
                numeric_scope_final_maximum=receipt["numeric_scope_final_maximum"])
        parameters, optimizer, graph, receipt, course = _runtime_release_adoption._adopt_catalog_profile(
            mx, run_dir, receipt, grade_a_course, source_root, graph,
            parameters, optimizer, transition, reserve_gib=reserve_gib,
            allow_mastery_debt=allow_debt)
        return parameters, optimizer, graph, receipt, course, True

    return parameters, optimizer, graph, receipt, course, False
