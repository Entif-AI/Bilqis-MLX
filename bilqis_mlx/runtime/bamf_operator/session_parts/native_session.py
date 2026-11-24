"""Native BAMF session bindings kept outside the top-level coordinator."""
from __future__ import annotations

from functools import partial
from bilqis_mlx.learning._atlas_candidate.identity_binding import (
    candidate_identity_metrics_delta, candidate_identity_metrics_snapshot,
)
from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.runtime.accepted_priority_visit import (
    execute_accepted_priority_candidate,
    execute_learning_first_priority_candidate,
    prepare_accepted_priority_candidate_visit,
)
from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
from bilqis_mlx.runtime.factory_candidate_training import FactoryDeliveryObservation
from bilqis_mlx.runtime.factory_retention_owner import (
    bind_current_retention_protection_plan, bind_factory_baseline_successor,
    derive_current_plasticity_escape_state, evaluate_factory_retention_candidate,
    measure_current_retention_shadow_target,
)
from bilqis_mlx.learning.teacher_multifidelity import (
    DEFAULT_SHADOW_POLICY, active_rungs,
)
from bilqis_mlx.runtime._factory_identity_evaluation import (
    _finalize_factory_generation_authority,
)
from bilqis_mlx.runtime.foundation_teacher_owner import derive_accepted_teacher_successor
from bilqis_mlx.runtime.priority_rejection_replay import (
    candidate_step_horizon, rejection_attempt_ordinals,
)
from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import currentness_metrics

from ..evidence_parts import CandidateEvidenceCapture as _Capture, prepare_candidate_evidence_root
from ..performance import measure_observed_phase, observe_completed_step
from .session_support import BamfPreparedVisit, _resource_observation, _step_seed
from ..source_prefetch import CandidateSourceLane, SourcePrefetchMetrics
from .rehearsal import compile_rehearsal_plan
from .candidate_execution import (
    candidate_horizon_execution as _candidate_horizon_execution_impl,
    execute_horizon as _execute_horizon_impl,
)
from .priority_hold import (
    adopt_and_activate_certified_successor,
    priority_hold_result as _priority_hold_result_impl,
)
from .admission_reentry import accepted_admission_reentry, accepted_learning_reentry


def priority_hold_result(*args, **kwargs):
    """Preserve native-session patch seams while delegating hold ownership."""
    return _priority_hold_result_impl(
        *args, adopt_successor=adopt_and_activate_certified_successor, **kwargs)


def execute_horizon(
        run_dir, selection, context, parent, atlas_path, feature_path, rows, horizon,
        cache, candidate_attempt_ordinal, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer, adviser_pool,
        *, emit_progress, invalid, rehearsal_plan=None, candidate_visit=None,
        candidate_executor=None,
        policy_support_enabled=False,
        distributed_profile=None, distributed_executor=None):
    candidate_executor = (
        execute_accepted_priority_candidate
        if candidate_executor is None else candidate_executor)
    candidate_kwargs = {
        "candidate_visit": candidate_visit,
        "distributed_profile": distributed_profile,
        "distributed_executor": distributed_executor,
    }
    if candidate_executor is execute_learning_first_priority_candidate:
        candidate_kwargs["accepted_cache"] = cache
        from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache
        candidate_kwargs["learning_first_cache"] = LearningFirstPreparationCache()
    return _execute_horizon_impl(
        run_dir, selection, context, parent, atlas_path, feature_path,
        rows, horizon, cache, candidate_attempt_ordinal, progress,
        source_prefetch_workers, source_prefetch_executor,
        source_prefetch_metrics, observer, adviser_pool,
        source_lane_cls=CandidateSourceLane, source_metrics_cls=SourcePrefetchMetrics,
        prepare_evidence_root=prepare_candidate_evidence_root, capture_cls=_Capture,
        delivery_observation_cls=FactoryDeliveryObservation,
        execute_candidate=partial(candidate_executor, **candidate_kwargs),
        step_seed=_step_seed,
        emit_progress=emit_progress, invalid=invalid,
        observe_completed_step_fn=observe_completed_step,
        rehearsal_plan=rehearsal_plan,
        policy_support_enabled=policy_support_enabled,
        shadow_policy=DEFAULT_SHADOW_POLICY, shadow_rungs_fn=active_rungs,
        shadow_probe_fn=measure_current_retention_shadow_target)


def candidate_horizon_execution(
        run_dir, parent, context, atlas_path, feature_path, selection, rows,
        capability, host_cache, steps_per_visit, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer, adviser_pool,
        *, emit_progress, invalid,
        distributed_profile=None, distributed_executor=None, attempt_ordinals=None):
    from .evidence_mode import strict_mode_enabled
    strict = strict_mode_enabled()
    if host_cache is None and not strict:
        invalid("BAMF_LEARNING_FIRST_SESSION_CACHE_REQUIRED")
    cache = host_cache if host_cache is not None else bind_accepted_execution_cache(run_dir)
    from bilqis_mlx.runtime.bamf_bundle.execution_cache import AcceptedExecutionCache
    candidate_visit = (
        prepare_accepted_priority_candidate_visit(selection, context)
        if strict else None)
    candidate_executor = (
        execute_accepted_priority_candidate
        if strict else execute_learning_first_priority_candidate)
    if type(cache) is AcceptedExecutionCache:
        bind_current_retention_protection_plan(context, parent, cache)
    rehearsal_plan = (
        compile_rehearsal_plan(run_dir, parent, cache, context, selection)
        if type(cache) is AcceptedExecutionCache else None)
    return _candidate_horizon_execution_impl(
        run_dir, parent, context, atlas_path, feature_path, selection, rows,
        capability, host_cache, steps_per_visit, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer, adviser_pool,
        bind_cache=bind_accepted_execution_cache, horizon_for=candidate_step_horizon,
        rejection_ordinals=(rejection_attempt_ordinals if attempt_ordinals is None
                            else lambda *_args: attempt_ordinals),
        execute_horizon_fn=lambda *args, **kwargs: execute_horizon(
            *args, **kwargs, emit_progress=emit_progress, invalid=invalid,
            rehearsal_plan=rehearsal_plan, candidate_visit=candidate_visit,
            candidate_executor=candidate_executor,
            policy_support_enabled=not strict,
            distributed_profile=distributed_profile,
            distributed_executor=distributed_executor),
        currentness_metrics_fn=currentness_metrics, emit_progress=emit_progress,
        identity_snapshot=candidate_identity_metrics_snapshot)


def retention_result(
        run_dir, parent, context, atlas_path, selection, capability, cache, steps,
        capture, rejection_journal_ordinal, rejection_attempt_ordinal,
        identity_before, progress, observer, *, emit_progress,
        mastery_debt_min_utility=0.05, preflight=None):
    from .retention import retention_result as _retention_result_impl
    return _retention_result_impl(
        run_dir, parent, context, atlas_path, selection, capability, cache, steps,
        capture, rejection_journal_ordinal, rejection_attempt_ordinal,
        identity_before, progress, observer,
        evaluate_candidate=lambda *args, **kwargs: evaluate_factory_retention_candidate(
            *args, mastery_debt_min_utility=mastery_debt_min_utility,
            **({"preflight": preflight} if preflight is not None else {}), **kwargs),
        issue_decision=issue_factory_retention_decision,
        identity_delta=candidate_identity_metrics_delta,
        resource_observation=_resource_observation,
        derive_successor=derive_accepted_teacher_successor,
        bind_baseline_successor=bind_factory_baseline_successor,
        finalize_generation_authority=_finalize_factory_generation_authority,
        derive_plasticity_escape=derive_current_plasticity_escape_state,
        prepared_visit_type=BamfPreparedVisit, emit_progress=emit_progress,
        measure_observed_phase_fn=measure_observed_phase)


def execute_selected_visit(
        run_dir, parent, context, atlas_path, feature_path, selection, host_cache,
        steps_per_visit, reserve_gib, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer,
        *, emit_progress, invalid,
        distributed_profile=None, distributed_executor=None,
        mastery_debt_min_utility=0.05):
    rows = selection.offer.rows()
    if observer is not None:
        from .evidence_mode import strict_mode_enabled
        strict = strict_mode_enabled()
        selected_policy = getattr(selection, "policy", None)
        selected_policy_key = getattr(
            getattr(getattr(selection, "visit", None), "identity", None),
            "policy_key", None)
        stage = getattr(observer, "stage", None)
        if strict:
            from ..evidence_parts.projection import (
                selected_visit_evidence, unknown_generated_grade_evidence,
            )
            visit_evidence = selected_visit_evidence(selection)
            observer.update(
                visit_evidence=visit_evidence,
                selected_policy=(
                    dict(selected_policy) if isinstance(selected_policy, dict) else None),
                generated_grade_evidence=unknown_generated_grade_evidence(
                    visit_evidence.get("grade_id")))
        elif callable(stage):
            stage(
                selected_policy=(
                    dict(selected_policy) if isinstance(selected_policy, dict) else None),
                selected_policy_key=selected_policy_key,
            )
        else:
            observer.update(
                selected_policy=(
                    dict(selected_policy) if isinstance(selected_policy, dict) else None),
                selected_policy_key=selected_policy_key,
            )
    emit_progress(
        progress, f"selected {selection.offer.capability_id} with {len(rows)} source rows")
    capability = selection.offer.capability_id
    from .evidence_mode import strict_mode_enabled
    strict = strict_mode_enabled()
    if host_cache is None and not strict:
        invalid("BAMF_LEARNING_FIRST_SESSION_CACHE_REQUIRED")
    adviser_cache = host_cache if host_cache is not None else bind_accepted_execution_cache(run_dir)
    from bilqis_mlx.runtime.retention.local_preflight import prepare_factory_target_preflight
    from bilqis_mlx.runtime.bamf_bundle.execution_cache import require_accepted_execution_cache
    from bilqis_mlx.runtime.factory_retention_owner import CURRENT_EVIDENCE_STAGE
    from bilqis_mlx.runtime.capability_retention import EvidenceStage
    preflight = attempt_ordinals = None
    if CURRENT_EVIDENCE_STAGE is EvidenceStage.FOUNDATION_ACQUISITION:
        require_accepted_execution_cache(adviser_cache)
        attempt_ordinals = rejection_attempt_ordinals(
            run_dir, parent, adviser_cache, capability)
        with measure_observed_phase(observer, "target_preflight_wall_seconds"):
            preflight = prepare_factory_target_preflight(
                context, parent, adviser_cache, atlas_path, selection, attempt_ordinals[0],
                mastery_debt_min_utility=mastery_debt_min_utility)
        if preflight.skip:
            return BamfPreparedVisit(
                "PERFECT_TARGET_SKIPPED", parent, selection=selection,
                capability=capability, preflight=preflight)
    adviser_pool = None
    if strict:
        from bilqis_mlx.runtime.championship_advisers import prepare_championship_adviser_pool
        adviser_pool = prepare_championship_adviser_pool(
            run_dir, parent, context, atlas_path, adviser_cache, reserve_gib=reserve_gib)
    horizon_state = candidate_horizon_execution(
        run_dir, parent, context, atlas_path, feature_path, selection, rows,
        capability, adviser_cache, steps_per_visit, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer, adviser_pool,
        emit_progress=emit_progress, invalid=invalid,
        distributed_profile=distributed_profile,
        distributed_executor=distributed_executor,
        **({"attempt_ordinals": attempt_ordinals} if attempt_ordinals is not None else {}))
    cache, steps, capture, journal_ordinal, attempt_ordinal, identity_before = horizon_state
    return retention_result(
        run_dir, parent, context, atlas_path, selection, capability, cache, steps,
        capture, journal_ordinal, attempt_ordinal, identity_before, progress, observer,
        emit_progress=emit_progress,
        mastery_debt_min_utility=mastery_debt_min_utility,
        **({"preflight": preflight} if preflight is not None else {}))
