"""Candidate-horizon execution helpers for the BAMF operator session."""
from __future__ import annotations

import time


def _mentor_observation(
        adviser_pool, source_rows, lesson, selection, capture, optimizer_step,
        delivery_observation_cls, observer=None):
    enrichment_rows = lesson.enrichment
    role_kwargs = {
        "prior": tuple(getattr(lesson, "prior", ())),
        "preservation": tuple(getattr(lesson, "preservation", ())),
        "support": tuple(getattr(lesson, "retention_support", ())),
    }
    if adviser_pool is None:
        observation = delivery_observation_cls(
            capture, optimizer_step, source_rows, selection.offer.source_seed,
            enrichment=enrichment_rows, **role_kwargs)
        return observation, None
    from bilqis_mlx.runtime.championship_advisers import (
        championship_mentor_supervision,
    )
    started = time.perf_counter()
    supervision = championship_mentor_supervision(
        adviser_pool, source_rows, source_seed=selection.offer.source_seed,
        teacher_strategy=selection.policy)
    if observer is not None:
        try:
            record = getattr(observer, "record", {})
            current = (
                record.get("adviser_wall_seconds", 0.0)
                if isinstance(record, dict) else 0.0)
            observer.update(
                adviser_wall_seconds=float(current or 0.0)
                + max(0.0, time.perf_counter() - started))
        except Exception:
            pass
    if supervision is None:
        observation = delivery_observation_cls(
            capture, optimizer_step, source_rows, selection.offer.source_seed,
            enrichment=enrichment_rows, **role_kwargs)
        return observation, None
    observation = delivery_observation_cls(
        capture, optimizer_step, source_rows, selection.offer.source_seed,
        enrichment=enrichment_rows, guidance=supervision.guidance_record(),
        mentors=supervision.to_record(), _mentor_supervision=supervision, **role_kwargs)
    return observation, supervision


def _lesson_for_step(source_lane, rows, ordinal):
    lesson = None if source_lane is None else source_lane.lesson(ordinal)
    if lesson is None:
        from bilqis_mlx.runtime.bamf_operator.source_prefetch import CandidateLessonRows
        lesson = CandidateLessonRows(tuple(rows))
    rehearsal_rows = (
        *tuple(getattr(lesson, "prior", ())),
        *tuple(getattr(lesson, "preservation", ())),
        *tuple(getattr(lesson, "retention_support", ())),
    )
    return lesson, lesson.direct, lesson.enrichment, rehearsal_rows


def _candidate_capture(
        run_dir, selection, context, parent, cache, candidate_attempt_ordinal,
        source_prefetch_workers, source_prefetch_executor, source_prefetch_metrics,
        horizon, rehearsal_plan, source_lane_cls, source_metrics_cls,
        prepare_evidence_root, capture_cls):
    source_lane = None
    if source_prefetch_metrics is not None or source_prefetch_workers:
        metrics = source_prefetch_metrics or source_metrics_cls()
        source_lane = source_lane_cls(
            selection, context, parent, horizon, workers=source_prefetch_workers,
            executor=source_prefetch_executor, metrics=metrics,
            rehearsal_plan=rehearsal_plan)
    prepare_evidence_root(run_dir)
    introductory = None
    try:
        from bilqis_mlx.learning.teacher_lineage import instruction_history
        from bilqis_mlx.runtime.priority_rejection_replay import rejection_recency
        projected_teacher = getattr(
            getattr(getattr(selection, "visit", None), "projection", None),
            "teacher_state", None)
        history_state, seen = instruction_history(
            projected_teacher if projected_teacher is not None else parent.teacher_state)
        _, rejected = rejection_recency(run_dir, parent, cache)
        capability = selection.offer.capability_id
        introductory = (
            False if capability in set(seen) | set(rejected)
            else True if history_state == "COMPLETE"
            else None)
    except (AttributeError, TypeError, ValueError, KeyError):
        introductory = None
    capture_kwargs = dict(
        generation=cache.generation,
        accepted_manifest_sha256=cache.accepted_manifest_sha256,
        candidate_attempt_ordinal=candidate_attempt_ordinal,
        parent_optimizer_step=parent.retained_state.optimizer_step,
    )
    if introductory is not None:
        capture_kwargs["introductory"] = introductory
    return source_lane, capture_cls(run_dir, selection, **capture_kwargs)


def _configure_shadow(capture, horizon, shadow_policy, shadow_rungs_fn,
                      shadow_probe_fn):
    if (shadow_policy is None or horizon < shadow_policy.rungs[0]
            or not callable(shadow_rungs_fn) or not callable(shadow_probe_fn)):
        return ()
    shadow_rungs = tuple(shadow_rungs_fn(shadow_policy, horizon))
    capture.configure_multifidelity(
        full_budget_steps=horizon, rungs=shadow_rungs,
        policy_version=shadow_policy.version,
        minimum_target_delta_to_continue=(
            shadow_policy.minimum_target_delta_to_continue),
        minimum_decision_step=shadow_policy.minimum_decision_step)
    return shadow_rungs


def _observe_shadow_rung(
        ordinal, shadow_rungs, shadow_parent_correct, shadow_probe_fn,
        context, candidate, atlas_path, selection, run_dir, parent, cache, capture):
    if ordinal not in shadow_rungs:
        return shadow_parent_correct
    probe_started = time.perf_counter()
    probe = shadow_probe_fn(
        context, candidate, atlas_path, selection.offer.capability_id,
        run_dir=run_dir, parent_correct=shadow_parent_correct,
        accepted_parent=parent, execution_cache=cache)
    capture.record_multifidelity_rung(
        step=ordinal, target_probe=probe,
        probe_wall_seconds=max(0.0, time.perf_counter() - probe_started))
    return (
        probe.get("parent_correct")
        if shadow_parent_correct is None else shadow_parent_correct)


def execute_horizon(
        run_dir, selection, context, parent, atlas_path, feature_path,
        rows, horizon, cache, candidate_attempt_ordinal, progress,
        source_prefetch_workers, source_prefetch_executor,
        source_prefetch_metrics, observer, adviser_pool=None, *, source_lane_cls,
        source_metrics_cls, prepare_evidence_root, capture_cls,
        delivery_observation_cls, execute_candidate, step_seed,
        emit_progress, invalid, observe_completed_step_fn, rehearsal_plan=None,
        shadow_policy=None, shadow_rungs_fn=None, shadow_probe_fn=None):
    source_lane, capture = _candidate_capture(
        run_dir, selection, context, parent, cache, candidate_attempt_ordinal,
        source_prefetch_workers, source_prefetch_executor, source_prefetch_metrics,
        horizon, rehearsal_plan, source_lane_cls, source_metrics_cls,
        prepare_evidence_root, capture_cls)
    steps, candidate = [], None
    shadow_rungs = _configure_shadow(
        capture, horizon, shadow_policy, shadow_rungs_fn, shadow_probe_fn)
    shadow_parent_correct = None
    for ordinal in range(1, horizon + 1):
        candidate_step_started_at = time.perf_counter()
        begin_step_started = time.perf_counter()
        begin_step = getattr(observer, "begin_step", None)
        if callable(begin_step):
            begin_step(ordinal, parent.retained_state.optimizer_step + ordinal)
        observer_begin_step_wall_seconds = (
            time.perf_counter() - begin_step_started)
        source_prepare_started = time.perf_counter()
        source_wait_before = (
            float(source_lane.metrics.wait_seconds)
            if source_lane is not None else 0.0)
        lesson, source_rows, enrichment_rows, rehearsal_rows = _lesson_for_step(
            source_lane, rows, ordinal)
        source_prepare_wall_seconds = time.perf_counter() - source_prepare_started
        source_lane_wait_wall_seconds = max(
            0.0,
            (float(source_lane.metrics.wait_seconds) - source_wait_before)
            if source_lane is not None else 0.0)
        source_lesson_materialization_wall_seconds = max(
            0.0, source_prepare_wall_seconds - source_lane_wait_wall_seconds)
        mentor_started = time.perf_counter()
        observation, mentor_supervision = _mentor_observation(
            adviser_pool, source_rows, lesson, selection, capture,
            parent.retained_state.optimizer_step + ordinal,
            delivery_observation_cls, observer)
        mentor_observation_wall_seconds = time.perf_counter() - mentor_started
        progress_started = time.perf_counter()
        emit_progress(progress, f"executing candidate step {ordinal}/{horizon}")
        progress_emission_wall_seconds = time.perf_counter() - progress_started
        step = execute_candidate(
            selection, context, atlas_path, feature_path,
            teacher_hparams=parent.optimizer_hyperparameters,
            observation=observation,
            optimizer_step_seed=step_seed(selection.visit.identity.visit_id, ordinal),
            max_norm=1.0, candidate=candidate,
            finalize_candidate=(ordinal == horizon),
            prepared_source_rows=(source_rows if source_lane is not None else None),
            prepared_enrichment_rows=enrichment_rows,
            prepared_rehearsal_rows=rehearsal_rows,
            rehearsal_by_id=getattr(lesson, "rehearsal_by_id", {}),
            rehearsal_bindings=getattr(lesson, "rehearsal_bindings_by_id", {}),
            rehearsal_authorities=getattr(lesson, "rehearsal_authorities_by_id", {}),
            candidate_step_started_at=candidate_step_started_at,
            source_prepare_wall_seconds=source_prepare_wall_seconds,
            source_lane_wait_wall_seconds=source_lane_wait_wall_seconds,
            source_lesson_materialization_wall_seconds=(
                source_lesson_materialization_wall_seconds),
            mentor_observation_wall_seconds=mentor_observation_wall_seconds,
            progress_emission_wall_seconds=progress_emission_wall_seconds,
            observer_begin_step_wall_seconds=observer_begin_step_wall_seconds)
        candidate = step.transaction
        if candidate.update_steps != ordinal:
            invalid("BAMF_C16_3_CANDIDATE_HORIZON_DRIFT")
        steps.append(step)
        observe_completed_step_fn(observer, step, candidate)
        if getattr(candidate, "motif_transition", None) is not None:
            break
        shadow_parent_correct = _observe_shadow_rung(
            ordinal, shadow_rungs, shadow_parent_correct, shadow_probe_fn,
            context, candidate, atlas_path, selection, run_dir, parent, cache,
            capture)
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
    emit_progress(
        progress,
        f"candidate horizon is atomic for up to {horizon} optimizer steps; "
        "the session time limit is checked between candidate visits")
    if observer is not None:
        observer.update(
            phase="TRAINING", capability_id=capability, candidate_step=0,
            candidate_horizon=horizon,
            candidate_optimizer_step=parent.retained_state.optimizer_step)
    identity_before = identity_snapshot()
    steps, capture = execute_horizon_fn(
        run_dir, selection, context, parent, atlas_path, feature_path, rows, horizon,
        cache, rejection_journal_ordinal, progress, source_prefetch_workers,
        source_prefetch_executor, source_prefetch_metrics, observer, adviser_pool)
    if observer is not None:
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
