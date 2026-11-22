"""Accepted A09 planning projection consumed by C03.4 priority authority."""
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.priority_planning_parts.cache import (
    PriorityPlanningCache,
    PriorityPlanningEpoch,
    _accepted_credit_key,
    _emit_progress,
    _invalid,
    _planning_key,
    _snapshot_key,
    _static_key,
)
from bilqis_mlx.runtime.priority_planning_parts.epoch import (
    build_priority_planning_epoch,
)


def priority_planning_from_epoch(epoch, *, progress=None, planning_cache=None):
    """Project C03 planning from one already-derived accepted A09 epoch."""
    from bilqis_mlx.factory import candidate_realizations
    from bilqis_mlx.factory.atlas_frontier_progress import plan_frontier_progress
    from bilqis_mlx.factory.atlas_frontier_selection import (
        ranked_frontier_target, select_frontier_delta_for_projection,
    )
    from bilqis_mlx.runtime.priority_qualification import (
        _issue_internal_priority_planning,
    )

    if type(epoch) is not PriorityPlanningEpoch:
        _invalid("BAMF_PRIORITY_PLANNING_EPOCH_INVALID")
    if planning_cache is not None and type(planning_cache) is not PriorityPlanningCache:
        _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
    key = _planning_key(epoch) if planning_cache is not None else None
    if planning_cache is not None and planning_cache._planning_key == key:
        planning_cache.planning_hits += 1
        planning = planning_cache._planning
        if planning is None:
            _invalid("BAMF_PRIORITY_PLANNING_CACHE_INVALID")
        _emit_progress(progress, "planner: reusing ranked bounded target")
        return planning
    if planning_cache is not None:
        planning_cache.planning_misses += 1
    current = epoch.current_release
    candidate = epoch.candidate_set
    snapshot = epoch.snapshot
    closure = epoch.closure
    requested = epoch.requested_keys
    selected = projection = None
    _emit_progress(progress, "planner: ranking next bounded target")
    try:
        semantic_id, rows = ranked_frontier_target(snapshot, closure, requested)
    except BilqisError as error:
        if error.context.get("reason") != "BAMF_PLANNER_NO_BOUNDED_READY_DELTA":
            raise
    else:
        try:
            projection = candidate_realizations.project_authoritative_target(
                semantic_id, current, rows)
        except ValueError:
            _invalid("BAMF_PRIORITY_A09_REALIZATION_MISSING")
        selected = select_frontier_delta_for_projection(
            snapshot, closure, current, projection, requested)
    if selected is None and epoch.accepted_credit is not None:
        from bilqis_mlx.factory.atlas_delta_adapter import (
            plan_frontier_progress_with_accepted_credit,
        )
        planning_progress = plan_frontier_progress_with_accepted_credit(
            snapshot, closure, epoch.accepted_credit)
    else:
        planning_progress = plan_frontier_progress(
            snapshot, closure, selected,
            current_release=current if selected is not None else None,
            selected_projection=projection)
    _emit_progress(progress, "planner: candidate frontier ready")
    planning = _issue_internal_priority_planning(
        planning_progress, closure, selected, projection)
    if planning_cache is not None:
        planning_cache._planning_key = key
        planning_cache._planning = planning
    return planning


def priority_planning(run_dir, source_context, atlas_artifact_path, *, progress=None):
    """Project current A09 state from accepted custody without requiring a C07 lease."""
    epoch = build_priority_planning_epoch(
        Path(run_dir), source_context, atlas_artifact_path, progress)
    return priority_planning_from_epoch(epoch, progress=progress)


__all__ = (
    "PriorityPlanningCache",
    "PriorityPlanningEpoch",
    "build_priority_planning_epoch",
    "priority_planning",
    "priority_planning_from_epoch",
)
