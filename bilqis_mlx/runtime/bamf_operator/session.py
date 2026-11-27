"""C16.3 persistent BAMF-native human-session coordinator."""
from __future__ import annotations
from contextlib import nullcontext
from pathlib import Path
import time
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.runtime.accepted_priority_visit import accepted_priority_school
from bilqis_mlx.runtime.bamf_bundle import record_bamf_rejection
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, bind_accepted_execution_cache, load_accepted_generation,
)
from bilqis_mlx.runtime.active_grade_cadence import record_active_grade_cadence_attempt
from bilqis_mlx.runtime.foundation_teacher_owner import select_foundation_priority_visit
from .locking import bamf_operator_lock
from .performance import measure_observed_phase
from .telemetry import TrainerObservation
from bilqis_mlx.runtime.operator_session import (
    DEFAULT_CANDIDATE_HORIZON, MAX_CANDIDATE_HORIZON,
)
from .session_parts.session_support import (
    BamfPreparedVisit, _execution_context, _resource_observation, _step_seed,
)
from .source_prefetch import (
    NATIVE_SOURCE_WORKER_COUNTS, SourcePrefetchMetrics,
)
from .evidence_parts import CandidateEvidenceCapture as _Capture
from .session_parts.stop_receipt import (
    record_normal_stop_receipt, stop_resource_witness,
)
from .session_parts.session_execution import operate as _operate_impl
from .session_parts.session_visit import visit as _visit_impl
from .session_parts.native_session import (
    accepted_admission_reentry as _accepted_admission_reentry_impl,
    adopt_and_activate_certified_successor as _adopt_and_activate_certified_successor,
    execute_selected_visit as _execute_selected_visit_impl,
    priority_hold_result as _priority_hold_result,
)
from .session_parts.maintenance import (
    run_pending_operator_maintenance as _maintenance_run_pending,
    run_post_operator_maintenance as _maintenance_run_post,
    training_memory_context as _training_memory_context)
from .session_parts.prepare_visit import prepare_bamf_visit_impl as _prepare_bamf_visit_impl


class _SessionExecutionContext:
    """Reuse one accepted execution snapshot until publication advances generation."""

    def __init__(self, *, strict: bool, loader):
        self.strict = bool(strict)
        self.loader = loader
        self.snapshot = None
        self.prepared_tasks = None

    def __call__(self, run_dir: Path, **kwargs):
        if self.strict:
            return self.loader(run_dir, **kwargs)
        if self.snapshot is None:
            self.snapshot = self.loader(run_dir, **kwargs)
            from .session_parts.prepared_task_catalog import attach_catalog
            self.prepared_tasks = attach_catalog(self.snapshot, self.prepared_tasks)
        return self.snapshot

    def accepted_publication(self) -> None:
        if not self.strict:
            self.snapshot = None

    def persist_tasks(self):
        if self.prepared_tasks is not None:
            self.prepared_tasks.persist()

def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_FIRST_STUDENT.INVALID, reason=reason)
from .session_parts.session_support import BamfOperatorResult
def _emit_progress(progress, message: str) -> None:
    if progress is not None:
        progress(message)


def _execute_selected_visit(
        run_dir, parent, context, atlas_path, feature_path, selection, host_cache,
        steps_per_visit, reserve_gib, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer,
        distributed_profile=None, distributed_executor=None,
        mastery_debt_min_utility=0.05):
    return _execute_selected_visit_impl(
        run_dir, parent, context, atlas_path, feature_path, selection, host_cache,
        steps_per_visit, reserve_gib, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer,
        emit_progress=_emit_progress, invalid=_invalid,
        distributed_profile=distributed_profile,
        distributed_executor=distributed_executor,
        mastery_debt_min_utility=mastery_debt_min_utility)


def _accepted_admission_reentry(
        run_dir: Path, parent_graph: dict, reserve_gib: float, progress=None):
    return _accepted_admission_reentry_impl(
        run_dir, parent_graph, reserve_gib, progress,
        emit_progress=_emit_progress, invalid=_invalid)


def _accepted_learning_reentry(
        run_dir: Path, parent_graph: dict, reserve_gib: float, progress=None):
    """Compose evidence refresh and C07 only for an explicit admission boundary."""
    from .accepted_learning_evidence import refresh_accepted_learning_evidence
    evidence = refresh_accepted_learning_evidence(Path(run_dir), progress=progress)
    _emit_progress(progress, "accepted learner evidence refresh: "
                   f"{evidence.measured} measured, {evidence.passed} passed; "
                   f"next {evidence.final_action}")
    return _accepted_admission_reentry(run_dir, parent_graph, reserve_gib, progress)


def prepare_bamf_visit(
        run_dir: Path, *, steps_per_visit: int = DEFAULT_CANDIDATE_HORIZON,
        batch_size: int = 32,
        reserve_gib: float = 100.0,
        progress=None, source_prefetch_workers: int = 0,
        source_prefetch_executor=None,
        source_prefetch_metrics: SourcePrefetchMetrics | None = None, observer=None,
        resource_holds=frozenset(), distributed_profile=None,
        distributed_executor=None, planning_cache=None,
        mastery_debt_min_utility: float = 0.05,
        execution_context=None) -> BamfPreparedVisit:
    execution_context = _execution_context if execution_context is None else execution_context
    return _prepare_bamf_visit_impl(
        run_dir, steps_per_visit=steps_per_visit, batch_size=batch_size,
        reserve_gib=reserve_gib, progress=progress,
        source_prefetch_workers=source_prefetch_workers,
        source_prefetch_executor=source_prefetch_executor,
        source_prefetch_metrics=source_prefetch_metrics, observer=observer,
        resource_holds=resource_holds, distributed_profile=distributed_profile,
        distributed_executor=distributed_executor, planning_cache=planning_cache,
        mastery_debt_min_utility=mastery_debt_min_utility,
        invalid=_invalid, emit_progress=_emit_progress,
        execution_context=execution_context,
        execute_selected_visit=_execute_selected_visit,
        priority_hold_result=_priority_hold_result,
        schedule_program=schedule_program_from_executable_release,
        accepted_priority_school_fn=accepted_priority_school,
        select_priority_visit=select_foundation_priority_visit)


def _visit(run_dir: Path, reserve_gib: float, *, steps_per_visit=DEFAULT_CANDIDATE_HORIZON,
           batch_size=32,
           progress=None, source_prefetch_workers=0,
           source_prefetch_executor=None, source_prefetch_metrics=None, observer=None,
           run_authority_binding=None, resource_holds=frozenset(),
           distributed_profile=None, distributed_executor=None,
           planning_cache=None, mastery_debt_min_utility=0.05,
           execution_context=None):
    def prepare_visit(*args, **kwargs):
        return prepare_bamf_visit(
            *args, **kwargs, distributed_profile=distributed_profile,
            distributed_executor=distributed_executor,
            planning_cache=planning_cache,
            mastery_debt_min_utility=mastery_debt_min_utility,
            execution_context=execution_context)
    return _visit_impl(
        run_dir, reserve_gib, steps_per_visit=steps_per_visit, progress=progress,
        batch_size=batch_size,
        source_prefetch_workers=source_prefetch_workers,
        source_prefetch_executor=source_prefetch_executor,
        source_prefetch_metrics=source_prefetch_metrics, observer=observer,
        run_authority_binding=run_authority_binding, resource_holds=resource_holds,
        prepare_visit=prepare_visit, record_rejection=record_bamf_rejection,
        accept_publish=accept_and_publish, load_generation=load_accepted_generation,
        measure_phase=measure_observed_phase, emit_progress=_emit_progress,
        record_cadence_attempt=record_active_grade_cadence_attempt)


def _run_post_operator_maintenance(
        run_dir: Path, *, progress=None, expected_token: str | None = None):
    return _maintenance_run_post(
        run_dir, progress=progress, expected_token=expected_token)


def _run_pending_operator_maintenance(run_dir: Path, *, progress=None):
    return _maintenance_run_pending(run_dir, progress=progress, post_maintenance=_run_post_operator_maintenance)


class _OperatorMaintenance:
    def __init__(self, *, profile_release, reserve_gib: float, progress=None):
        self.profile_release = profile_release
        self.reserve_gib = reserve_gib
        self.progress = progress
        self.token = None

    def before_visits(self, root):
        root = Path(root)
        if (root / "bamf-state.json").is_file() or (root / "state.json").is_file():
            from bilqis_mlx._data_plane.maintenance_lifecycle import mark_maintenance_pending
            from bilqis_mlx.data_plane import data_plane
            self.token = mark_maintenance_pending(data_plane(), root)
        if self.profile_release is not None:
            from bilqis_mlx.runtime._release_adoption.native_profile import adopt_profile_release
            adopt_profile_release(
                root, self.profile_release, reserve_gib=self.reserve_gib)

    def finish(self, run_dir: Path) -> None:
        try:
            _run_post_operator_maintenance(
                run_dir, progress=self.progress, expected_token=self.token)
        except Exception as error:
            try:
                _emit_progress(
                    self.progress,
                    f"post-operator data-plane maintenance deferred: {error}",
                )
            except Exception:
                pass


def _make_session_visit_fn(
        *, planning_cache, distributed_profile, distributed_executor,
        mastery_debt_min_utility: float,
        execution_context: _SessionExecutionContext):
    def visit_fn(*args, **kwargs):
        visit_kwargs = {
            "planning_cache": planning_cache,
            "mastery_debt_min_utility": mastery_debt_min_utility,
            "execution_context": execution_context,
        }
        if distributed_profile is not None or distributed_executor is not None:
            visit_kwargs.update({
                "distributed_profile": distributed_profile,
                "distributed_executor": distributed_executor,
            })
        result = _visit(*args, **kwargs, **visit_kwargs)
        if result in {"ACCEPTED", "GRADE_TRANSITIONED"}:
            execution_context.accepted_publication()
        return result
    return visit_fn


def operate_bamf(
    run_dir: Path, *, minutes: int = 90,
    max_visits: int = 0, steps_per_visit: int = DEFAULT_CANDIDATE_HORIZON,
    batch_size: int = 32,
    reserve_gib: float = 100.0,
    source_prefetch_workers: int = 2,
    parent_graph: dict | None = None,
    profile_release=None,
    run_authority=None,
    distributed_profile=None,
    distributed_executor=None,
    strict_mode: bool = False,
    strict_evidence: bool | None = None,
    mastery_debt_min_utility: float = 0.05,
    progress=None,
) -> BamfOperatorResult:
    """Run the human-authorized BAMF lineage until a bounded stop condition."""
    from bilqis_mlx.runtime.c08_distributed_executor import DistributedExecutorBinding
    from bilqis_mlx.runtime.priority_planning_owner import PriorityPlanningCache
    from bilqis_mlx.runtime.run_authority import bind_native_run_authority
    from bilqis_mlx.runtime.source_prefetch import source_prefetch_pool
    if (distributed_profile is None
            and type(distributed_executor) is DistributedExecutorBinding):
        distributed_profile = distributed_executor.profile
    if strict_evidence is not None:
        strict_mode = bool(strict_mode or strict_evidence)
    session_execution_context = _SessionExecutionContext(
        strict=strict_mode, loader=_execution_context)
    maintenance = _OperatorMaintenance(
        profile_release=profile_release, reserve_gib=reserve_gib, progress=progress)
    planning_cache = PriorityPlanningCache(Path(run_dir))
    visit_fn = _make_session_visit_fn(
        planning_cache=planning_cache,
        distributed_profile=distributed_profile,
        distributed_executor=distributed_executor,
        mastery_debt_min_utility=mastery_debt_min_utility,
        execution_context=session_execution_context,
    )
    _run_pending_operator_maintenance(Path(run_dir), progress=progress)
    from .session_parts.evidence_mode import evidence_mode
    from bilqis_mlx.runtime.championship_advisers import championship_adviser_session
    try:
        with evidence_mode(strict=strict_mode), championship_adviser_session():
            return _operate_impl(
                Path(run_dir), minutes=minutes, max_visits=max_visits,
                steps_per_visit=steps_per_visit, batch_size=batch_size,
                reserve_gib=reserve_gib,
                source_prefetch_workers=source_prefetch_workers, progress=progress,
                max_horizon=MAX_CANDIDATE_HORIZON,
                worker_counts=NATIVE_SOURCE_WORKER_COUNTS, invalid=_invalid,
                metrics_type=SourcePrefetchMetrics, source_pool_factory=source_prefetch_pool,
                null_context=nullcontext, operator_lock=bamf_operator_lock,
                visit_fn=visit_fn, observer_type=TrainerObservation,
                emit_progress=_emit_progress, monotonic=time.monotonic,
                load_generation=load_accepted_generation, result_type=BamfOperatorResult,
                resource_snapshot=stop_resource_witness,
                record_stop=record_normal_stop_receipt,
                before_stop=session_execution_context.persist_tasks, elapsed_clock=time.perf_counter,
                before_visits=maintenance.before_visits,
                training_memory_context=_training_memory_context,
                bind_run_authority=(
                    lambda current_run_dir:
                    bind_native_run_authority(current_run_dir, run_authority)))
    finally:
        maintenance.finish(Path(run_dir))
