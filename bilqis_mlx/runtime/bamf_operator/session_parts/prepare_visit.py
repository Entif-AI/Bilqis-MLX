"""Production BAMF visit preparation orchestration."""
from pathlib import Path
import time

from bilqis_mlx.runtime.atlas_memory_retry import (
    CandidateMemoryExhausted,
    OOM_EXHAUSTED,
)
from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
    VisitCurrentnessMetrics,
)
from bilqis_mlx.runtime.factory_retention_owner import (
    bind_current_retention_protection_plan,
)
from bilqis_mlx.runtime.operator_session import MAX_CANDIDATE_HORIZON

from ..performance import selected_source_visit_fields
from .session_support import BamfPreparedVisit


def _record_planning_observation(observer, selection, planning_started):
    if observer is None:
        return
    identity = getattr(getattr(getattr(selection, "visit", None), "identity", None),
                       "visit_id", None)
    if isinstance(identity, str) and identity:
        observer.update(visit_id=identity)
    planning_total = max(0.0, time.perf_counter() - planning_started)
    source_wall = float(
        getattr(selection, "source_materialization_wall_seconds", None) or 0.0)
    from bilqis_mlx.runtime.priority_source_materialization import (
        source_materialization_observation,
    )
    observer.update(
        planning_wall_seconds=max(0.0, planning_total - source_wall),
        source_materialization_wall_seconds=(source_wall or None),
        **selected_source_visit_fields(
            source_materialization_observation(selection.offer)))


def prepare_bamf_visit_impl(
        run_dir: Path, *, steps_per_visit, batch_size, reserve_gib, progress,
        source_prefetch_workers, source_prefetch_executor,
        source_prefetch_metrics, observer, resource_holds, distributed_profile,
        distributed_executor, planning_cache, mastery_debt_min_utility,
        invalid, emit_progress, execution_context, execute_selected_visit,
        priority_hold_result, schedule_program, accepted_priority_school_fn,
        select_priority_visit) -> BamfPreparedVisit:
    """Compose the production visit through retention without publishing it."""
    if (type(steps_per_visit) is not int
            or not 1 <= steps_per_visit <= MAX_CANDIDATE_HORIZON):
        invalid("BAMF_OPERATOR_SESSION_BOUNDS_INVALID")
    emit_progress(progress, "validating accepted generation and source custody")
    visit_currentness_metrics = VisitCurrentnessMetrics()
    accepted_state_metrics = {}
    accepted_state_started = time.perf_counter()
    parent, context, atlas_path, feature_path = execution_context(
        run_dir, currentness_metrics=visit_currentness_metrics,
        performance_metrics=accepted_state_metrics)
    if observer is not None:
        observer.bind_parent(parent)
        observer.update(phase="SELECTING")
    program = schedule_program(context.release)
    accepted_host = getattr(context, "_accepted_runtime_host", None)
    host_cache = getattr(accepted_host, "_accepted_cache", None)
    if host_cache is not None:
        bind_current_retention_protection_plan(context, parent, host_cache)
    school = accepted_priority_school_fn(
        parent, program,
        candidate_identity_sha256=getattr(
            host_cache, "_candidate_identity_sha256", None))
    accepted_state_total = max(0.0, time.perf_counter() - accepted_state_started)
    accepted_state_metrics["accepted_state_setup_wall_seconds"] = accepted_state_total
    accepted_state_metrics["accepted_state_setup_other_wall_seconds"] = max(
        0.0,
        accepted_state_total - sum(float(accepted_state_metrics.get(name, 0.0)) for name in (
            "accepted_runtime_host_wall_seconds",
            "accepted_generation_load_wall_seconds",
            "accepted_source_context_wall_seconds",
            "accepted_feature_authentication_wall_seconds",
        )))
    if observer is not None:
        observer.update(**accepted_state_metrics)
    emit_progress(progress, "planning current candidate frontier and teacher priority")
    planning_started = time.perf_counter()
    selection = select_priority_visit(
        run_dir, context, atlas_path, program=program, school=school,
        progress=progress, resource_holds=resource_holds,
        planning_cache=planning_cache, logical_batch_size=batch_size)
    _record_planning_observation(observer, selection, planning_started)
    if selection.status != "TEACHER_SELECTED":
        if (selection.status == "NO_ADMISSIBLE_TEACHING"
                and any(reason == OOM_EXHAUSTED for _, reason in selection.holds)):
            return BamfPreparedVisit("RESOURCE_HOLD", parent, selection=selection)
        return priority_hold_result(
            run_dir, selection, context, parent, atlas_path, reserve_gib, progress,
            emit_progress=emit_progress)
    try:
        return execute_selected_visit(
            run_dir, parent, context, atlas_path, feature_path, selection, host_cache,
            steps_per_visit, reserve_gib, progress, source_prefetch_workers,
            source_prefetch_executor, source_prefetch_metrics, observer,
            distributed_profile, distributed_executor,
            mastery_debt_min_utility=mastery_debt_min_utility)
    except CandidateMemoryExhausted as error:
        return BamfPreparedVisit(
            "RESOURCE_REJECTED", parent, selection=selection,
            capability=selection.offer.capability_id, resource=error.to_record())
