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

def activate_next_admitted_grade(
        run_dir, receipt, previous_course, successor, graph=None):
    return _runtime_release_adoption._activate_next_admitted_grade(
        run_dir, receipt, previous_course, successor, graph)


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
