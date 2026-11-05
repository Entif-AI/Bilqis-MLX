"""Profile transitions for operator startup."""
import bilqis_mlx.compatibility.executable_projection as _compatibility_executable_projection
import dataclasses as _dataclasses
import bilqis_mlx.factory.schedule as _factory_schedule
import bilqis_mlx.profiles.catalog as _profiles_catalog
import bilqis_mlx.profiles.school as _profiles_school
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state


def numeric_entry_transition(release, graph, *, full_grade_b, experiment_budget):
    initial, terminal = _profiles_catalog.numeric_scope_bounds()
    transition = _profiles_catalog.numeric_entry_transition(
        release, graph, full_boolean=full_grade_b, maximum=initial)
    return _dataclasses.replace(
        transition,
        numeric_scope_final_maximum=(initial if experiment_budget is not None else terminal))


def resume_boolean_profile(run_dir, receipt, course_a, source_root, graph,
                           admitted_v2, *, full_grade_b, autonomous_curriculum):
    """Apply the operator-selected Boolean profile without neural updates."""
    course = _factory_schedule.schedule_program_from_executable_release(admitted_v2)
    active_grade_count = len(admitted_v2.execution_plan.grades)
    target = None
    if (not autonomous_curriculum and
            _compatibility_executable_projection.profile_has_legacy_inventory(
                admitted_v2, course)):
        if active_grade_count == 1:
            target = _profiles_school.with_disabled_future_grades(
                _profiles_school.boolean_entry_profile(full=full_grade_b),
                tuple(grade.grade_id for grade in admitted_v2.curriculum.grades[2:]))
        elif full_grade_b:
            target = _profiles_school.full_boolean_upgrade_profile(admitted_v2.profile)
        elif active_grade_count <= 2:
            target = _profiles_school.with_disabled_future_grades(
                _profiles_school.boolean_entry_profile(full=False),
                tuple(grade.grade_id for grade in admitted_v2.curriculum.grades[2:]))
    if target is None or admitted_v2.profile == target:
        return receipt, course, admitted_v2
    if receipt["school"]["stage"] == "AWAITING_NEXT_GRADE" and active_grade_count == 1:
        return _runtime_release_adoption._adopt_executable_profile(
            run_dir, receipt, course_a, source_root, graph, target)[:3]
    if active_grade_count < 2:
        return receipt, course, admitted_v2
    school = _runtime_state._state_from_json(receipt["school"], course)
    if not full_grade_b and school.grade != course.grades[-1].id:
        return receipt, course, admitted_v2
    return _runtime_release_adoption._adopt_executable_profile(
        run_dir, receipt, course_a, source_root, graph, target,
        invalidate_assessment_evidence=full_grade_b)[:3]
