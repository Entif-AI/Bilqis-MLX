"""Factory execution lineage owner."""
from __future__ import annotations

from ..execution import CurriculumDelta, ExecutionPlan, PlanLineage
from .. import execution as _api








def _verify_lineage_curriculum(
        previous: ExecutionPlan, current: ExecutionPlan, lineage: PlanLineage) -> None:
    if (lineage.previous_curriculum_sha256 != previous.curriculum_sha256 or
            lineage.next_curriculum_sha256 != current.curriculum_sha256):
        raise ValueError("FACTORY_PLAN_LINEAGE_CURRICULUM_DRIFT")


def diff_execution_plans(
        previous: ExecutionPlan, current: ExecutionPlan, *,
        lineage: PlanLineage | None = None) -> CurriculumDelta:
    if not isinstance(previous, _api.ExecutionPlan) or not isinstance(current, _api.ExecutionPlan):
        raise TypeError("FACTORY_EXECUTION_PLAN_DIFF_INVALID_INPUT")
    if previous.curriculum_sha256 == current.curriculum_sha256:
        if lineage is None:
            geometry = _api.SemanticGeometryChange.UNCHANGED
        else:
            _api._verify_lineage_curriculum(previous, current, lineage)
            geometry = lineage.semantic_geometry
    else:
        if lineage is None:
            raise ValueError("FACTORY_EXECUTION_PLAN_LINEAGE_REQUIRED")
        _api._verify_lineage_curriculum(previous, current, lineage)
        geometry = lineage.semantic_geometry

    previous_grades = previous.grade_map
    current_grades = current.grade_map
    previous_caps = previous.capability_map
    current_caps = current.capability_map
    projection_changes = tuple(
        name for name in (
            "roster", "schedule", "assessment", "source", "answer_schema",
            "coverage", "teaching")
        if getattr(previous.projection_digests, name) !=
           getattr(current.projection_digests, name))
    return _api.CurriculumDelta(
        previous_plan_sha256=previous.digest(),
        next_plan_sha256=current.digest(),
        previous_curriculum_sha256=previous.curriculum_sha256,
        next_curriculum_sha256=current.curriculum_sha256,
        previous_source_binding_sha256=previous.source_binding_sha256,
        next_source_binding_sha256=current.source_binding_sha256,
        added_grades=tuple(sorted(set(current_grades) - set(previous_grades))),
        removed_grades=tuple(sorted(set(previous_grades) - set(current_grades))),
        revised_grades=tuple(sorted(
            grade for grade in set(previous_grades) & set(current_grades)
            if previous_grades[grade] != current_grades[grade])),
        added_capabilities=tuple(sorted(set(current_caps) - set(previous_caps))),
        removed_capabilities=tuple(sorted(set(previous_caps) - set(current_caps))),
        changed_capabilities=tuple(sorted(
            cap for cap in set(previous_caps) & set(current_caps)
            if previous_caps[cap] != current_caps[cap])),
        projection_changes=projection_changes,
        semantic_geometry=geometry.value,
    )
