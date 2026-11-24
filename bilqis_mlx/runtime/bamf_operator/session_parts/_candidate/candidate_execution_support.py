"""Source, mentor, capture, and shadow helpers for candidate-horizon execution."""
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
        "fresh_support": tuple(getattr(lesson, "fresh_support", ())),
    }
    unavailable = getattr(lesson, "weakness_unavailable", ())
    if unavailable:
        role_kwargs["controls"] = {"weakness_unavailable": dict(unavailable)}
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
        horizon, rehearsal_plan, policy_support_enabled, source_lane_cls, source_metrics_cls,
        prepare_evidence_root, capture_cls):
    source_lane = None
    if (source_prefetch_metrics is not None or source_prefetch_workers
            or rehearsal_plan is not None or policy_support_enabled):
        metrics = source_prefetch_metrics or source_metrics_cls()
        source_lane = source_lane_cls(
            selection, context, parent, horizon, workers=source_prefetch_workers,
            executor=source_prefetch_executor, metrics=metrics,
            rehearsal_plan=rehearsal_plan,
            policy_support_enabled=policy_support_enabled)
    from .evidence_mode import strict_evidence_enabled
    strict = strict_evidence_enabled()
    if not strict:
        from .learning_trace import CandidateLearningTrace
        return source_lane, CandidateLearningTrace(
            selection, generation=cache.generation,
            accepted_manifest_sha256=cache.accepted_manifest_sha256,
            candidate_attempt_ordinal=candidate_attempt_ordinal,
            parent_optimizer_step=parent.retained_state.optimizer_step)
    introductory = None
    if strict:
        prepare_evidence_root(run_dir)
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
    from .evidence_mode import strict_evidence_enabled
    if not strict_evidence_enabled():
        return ()
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


def _step_source_inputs(source_lane, rows, ordinal, prepared_host_step, *, measure=True):
    if prepared_host_step is not None:
        lesson = prepared_host_step.lesson
        rehearsal_rows = (
            *tuple(getattr(lesson, "prior", ())),
            *tuple(getattr(lesson, "preservation", ())),
            *tuple(getattr(lesson, "retention_support", ())),
        )
        pipeline_kwargs = {
            "prepared_learning_first_source_inputs":
                prepared_host_step.prepared_source_inputs,
            "prepared_learning_first_source_identity":
                prepared_host_step.source_identity,
        }
        if measure:
            pipeline_kwargs.update({
                "pipeline_host_preparation_wall_seconds":
                    prepared_host_step.preparation_wall_seconds,
                "pipeline_host_overlap_wall_seconds":
                    prepared_host_step.overlap_wall_seconds,
                "pipeline_host_wait_wall_seconds":
                    prepared_host_step.host_wait_wall_seconds,
                "pipeline_accelerator_wait_for_host_wall_seconds":
                    prepared_host_step.host_wait_wall_seconds,
            })
        # The physical wait belongs exclusively to the host-preparation lane.
        return (
            lesson, lesson.direct, lesson.enrichment, rehearsal_rows,
            0.0, 0.0, 0.0, pipeline_kwargs,
        )

    source_started = time.perf_counter() if measure else None
    wait_before = (
        float(source_lane.metrics.wait_seconds)
        if measure and source_lane is not None else 0.0)
    lesson, source_rows, enrichment_rows, rehearsal_rows = _lesson_for_step(
        source_lane, rows, ordinal)
    source_seconds = (time.perf_counter() - source_started) if measure else 0.0
    wait_seconds = (
        max(0.0, float(source_lane.metrics.wait_seconds) - wait_before)
        if measure and source_lane is not None else 0.0)
    return (
        lesson, source_rows, enrichment_rows, rehearsal_rows,
        source_seconds, wait_seconds, max(0.0, source_seconds - wait_seconds), {},
    )
