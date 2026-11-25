"""Candidate-horizon execution helpers for the BAMF operator session."""
from __future__ import annotations

import time

from .candidate_execution_support import (
    _candidate_capture, _configure_shadow, _mentor_observation,
    _observe_shadow_rung, _step_source_inputs,
)

def _execute_horizon_step(
        ordinal, horizon, source_lane, rows, selection, context, parent,
        atlas_path, feature_path, capture, observer, adviser_pool, candidate,
        shadow_rungs, shadow_parent_correct, shadow_probe_fn, run_dir, cache,
        delivery_observation_cls, execute_candidate, step_seed, emit_progress,
        progress, observe_completed_step_fn, invalid, prepared_host_step=None,
        candidate_step_started_at=None):
    from .evidence_mode import strict_mode_enabled
    strict = strict_mode_enabled()
    if candidate_step_started_at is None:
        candidate_step_started_at = time.perf_counter() if strict else 0.0
    observer_seconds = 0.0
    if strict and observer is not None:
        begin_step_started = time.perf_counter()
        begin_step = getattr(observer, "begin_step", None)
        if callable(begin_step):
            begin_step(ordinal, parent.retained_state.optimizer_step + ordinal)
        observer_seconds = time.perf_counter() - begin_step_started
    elif observer is not None:
        stage = getattr(observer, "stage", None)
        observe = stage if callable(stage) else observer.update
        observe(
            candidate_step=ordinal,
            candidate_optimizer_step=parent.retained_state.optimizer_step + ordinal)
    (
        lesson, source_rows, enrichment_rows, rehearsal_rows,
        source_seconds, wait_seconds, lesson_seconds, pipeline_kwargs,
    ) = _step_source_inputs(
        source_lane, rows, ordinal, prepared_host_step, measure=strict)
    mentor_started = time.perf_counter() if strict else None
    observation, mentor_supervision = _mentor_observation(
        adviser_pool, source_rows, lesson, selection, capture,
        parent.retained_state.optimizer_step + ordinal,
        delivery_observation_cls, observer)
    mentor_seconds = (time.perf_counter() - mentor_started) if strict else 0.0
    progress_seconds = 0.0
    if strict:
        progress_started = time.perf_counter()
        emit_progress(progress, f"executing candidate step {ordinal}/{horizon}")
        progress_seconds = time.perf_counter() - progress_started
    if not strict and getattr(lesson, "source_seed", None) is not None:
        pipeline_kwargs["prepared_source_seed"] = lesson.source_seed
    if not strict and getattr(lesson, "primary_lesson", None) is not None:
        pipeline_kwargs["prepared_primary_lesson"] = lesson.primary_lesson
    if not strict and getattr(lesson, "exact_miss_instruction", None) is not None:
        pipeline_kwargs["exact_miss_instruction"] = lesson.exact_miss_instruction
    step = execute_candidate(
        selection, context, atlas_path, feature_path,
        teacher_hparams=parent.optimizer_hyperparameters, observation=observation,
        optimizer_step_seed=step_seed(selection.visit.identity.visit_id, ordinal),
        max_norm=1.0, candidate=candidate, finalize_candidate=(ordinal == horizon),
        prepared_source_rows=(source_rows if source_lane is not None else None),
        prepared_enrichment_rows=enrichment_rows, prepared_rehearsal_rows=rehearsal_rows,
        rehearsal_by_id=getattr(lesson, "rehearsal_by_id", {}),
        rehearsal_bindings=getattr(lesson, "rehearsal_bindings_by_id", {}),
        rehearsal_authorities=getattr(lesson, "rehearsal_authorities_by_id", {}),
        prepared_fresh_support_rows=getattr(lesson, "fresh_support", ()),
        fresh_support_by_id=getattr(lesson, "fresh_support_by_id", {}),
        fresh_support_binding=getattr(lesson, "fresh_support_binding", None),
        fresh_support_authority=getattr(lesson, "fresh_support_authority", None),
        fresh_support_unavailable_reason=getattr(
            lesson, "fresh_support_unavailable_reason", None),
        fresh_support_depth_control=getattr(lesson, "fresh_support_depth_control", None),
        candidate_step_started_at=candidate_step_started_at,
        source_prepare_wall_seconds=source_seconds,
        source_lane_wait_wall_seconds=wait_seconds,
        source_lesson_materialization_wall_seconds=lesson_seconds,
        mentor_observation_wall_seconds=mentor_seconds,
        progress_emission_wall_seconds=progress_seconds,
        observer_begin_step_wall_seconds=observer_seconds,
        **pipeline_kwargs)
    candidate = step.transaction
    if prepared_host_step is not None and source_lane is not None:
        source_lane.metrics.pipeline_discarded_steps += int(
            step.realized_cost.get("pipeline_discarded_prefetch_work", 0))
    if candidate.update_steps != ordinal:
        invalid("BAMF_C16_3_CANDIDATE_HORIZON_DRIFT")
    if strict:
        observe_completed_step_fn(observer, step, candidate)
    shadow_parent_correct = _observe_shadow_rung(
        ordinal, shadow_rungs, shadow_parent_correct, shadow_probe_fn,
        context, candidate, atlas_path, selection, run_dir, parent, cache, capture)
    return step, candidate, shadow_parent_correct


def execute_horizon(
        run_dir, selection, context, parent, atlas_path, feature_path,
        rows, horizon, cache, candidate_attempt_ordinal, progress,
        source_prefetch_workers, source_prefetch_executor,
        source_prefetch_metrics, observer, adviser_pool=None, *, source_lane_cls,
        source_metrics_cls, prepare_evidence_root, capture_cls,
        delivery_observation_cls, execute_candidate, step_seed,
        emit_progress, invalid, observe_completed_step_fn, rehearsal_plan=None,
        policy_support_enabled=False, prepare_step_ahead=None,
        shadow_policy=None, shadow_rungs_fn=None, shadow_probe_fn=None):
    source_lane, capture = _candidate_capture(
        run_dir, selection, context, parent, cache, candidate_attempt_ordinal,
        source_prefetch_workers, source_prefetch_executor, source_prefetch_metrics,
        horizon, rehearsal_plan, policy_support_enabled, source_lane_cls, source_metrics_cls,
        prepare_evidence_root, capture_cls)
    steps, candidate = [], None
    shadow_rungs = _configure_shadow(
        capture, horizon, shadow_policy, shadow_rungs_fn, shadow_probe_fn)
    shadow_parent_correct = None
    pipeline = None
    if source_lane is not None:
        from .pipeline import (
            CandidateHostPreparationPipeline,
            learning_first_prepare_step,
        )
        prepare_step_ahead = (
            prepare_step_ahead
            or learning_first_prepare_step(execute_candidate, selection, context))
        if prepare_step_ahead is not None:
            pipeline = CandidateHostPreparationPipeline(
                source_lane, horizon, prepare_step_ahead, source_lane.metrics)
            pipeline.submit(1)
    try:
        for ordinal in range(1, horizon + 1):
            from .evidence_mode import strict_mode_enabled
            candidate_step_started_at = (
                time.perf_counter() if strict_mode_enabled() else 0.0)
            prepared_host_step = None
            if pipeline is not None:
                prepared_host_step = pipeline.take(ordinal)
                pipeline.submit(ordinal + 1)
            step, candidate, shadow_parent_correct = _execute_horizon_step(
                ordinal, horizon, source_lane, rows, selection, context, parent,
                atlas_path, feature_path, capture, observer, adviser_pool, candidate,
                shadow_rungs, shadow_parent_correct, shadow_probe_fn, run_dir, cache,
                delivery_observation_cls, execute_candidate, step_seed, emit_progress,
                progress, observe_completed_step_fn, invalid,
                prepared_host_step=prepared_host_step,
                candidate_step_started_at=candidate_step_started_at)
            steps.append(step)
            if getattr(candidate, "motif_transition", None) is not None:
                break
    finally:
        if pipeline is not None:
            pipeline.close()
    return steps, capture


def candidate_horizon_execution(
        run_dir, parent, context, atlas_path, feature_path, selection, rows,
        capability, host_cache, steps_per_visit, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer, adviser_pool=None, *,
        bind_cache, horizon_for, rejection_ordinals, execute_horizon_fn,
        currentness_metrics_fn, emit_progress, identity_snapshot):
    cache = host_cache if host_cache is not None else bind_cache(run_dir)
    horizon = horizon_for(run_dir, parent, cache, capability, steps_per_visit)
    rejection_journal_ordinal, rejection_attempt_ordinal = rejection_ordinals(
        run_dir, parent, cache, capability)
    from .evidence_mode import strict_mode_enabled
    strict = strict_mode_enabled()
    if strict:
        emit_progress(
            progress,
            f"candidate horizon is atomic for up to {horizon} optimizer steps; "
            "the session time limit is checked between candidate visits")
    if observer is not None:
        stage = getattr(observer, "stage", None)
        observe = observer.update if strict or not callable(stage) else stage
        observe(
            phase="TRAINING", capability_id=capability,
            visit_id=getattr(getattr(selection.visit, "identity", None), "visit_id", None),
            candidate_step=0,
            candidate_horizon=horizon,
            candidate_optimizer_step=parent.retained_state.optimizer_step)
    identity_before = identity_snapshot() if strict else None
    steps, capture = execute_horizon_fn(
        run_dir, selection, context, parent, atlas_path, feature_path, rows, horizon,
        cache, rejection_journal_ordinal, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer, adviser_pool)
    if strict and observer is not None:
        metrics = currentness_metrics_fn(
            selection.offer._planning_generation._accepted_currentness)
        observer.update(
            currentness_deep_authentications=metrics["deep_authentication_count"],
            currentness_accepted_cache_checks=metrics[
                "accepted_cache_currentness_count"],
            currentness_full_candidate_identity_hashes=metrics[
                "full_candidate_identity_hashes"],
            currentness_bundle_tree_scans=metrics["bundle_tree_scans"],
        )
    return (
        cache, steps, capture, rejection_journal_ordinal,
        rejection_attempt_ordinal, identity_before,
    )


__all__ = ("candidate_horizon_execution", "execute_horizon")
