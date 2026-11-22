"""Run and observe one prepared Factory candidate step before publication."""
from __future__ import annotations

from pathlib import Path
import time

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning._atlas_candidate.identity_binding import (
    candidate_identity_metrics_delta, candidate_identity_metrics_snapshot,
)
from bilqis_mlx.runtime.bamf_bundle import is_authenticated_generation_feature_context
from bilqis_mlx.runtime.bamf_bundle.admission import (
    admit_uninterrupted_candidate_step, bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
    bind_candidate_execution_cache, bind_execution_generation,
)
from bilqis_mlx.runtime.atlas_resources import (
    DistributedExecutionProfile, persist_distributed_manifest,
)

from ..atlas_training_delivery import capture_realized_delivery
from ..factory_candidate_components import (
    FactoryCandidateStep, _invalid, _reporting_diagnostics, _resource_plan,
    _stage_retained_motifs,
)
from bilqis_mlx.runtime.factory_candidate_cost import realized_candidate_cost
from bilqis_mlx.runtime.factory_candidate_microbatch import (
    bind_factory_distributed_outcome, execute_factory_logical_batch,
    execute_factory_training_row,
)
from bilqis_mlx.runtime.c08_distributed_manifest import issue_distributed_step_manifest
from bilqis_mlx.runtime.c08_distributed_outcome import DistributedStepOutcome
from bilqis_mlx.runtime.c08_distributed_executor import DistributedExecutorBinding
from .retry import execute_with_oom_retry


def _realized_candidate_cost(*args, **kwargs):
    """Compatibility seam for the reporting contract after structural extraction."""
    return realized_candidate_cost(*args, **kwargs, invalid=_invalid)


def _prepared_feature_context(prepared, semantic_context):
    feature_context = prepared.semantic_context if semantic_context is None else semantic_context
    if not is_authenticated_generation_feature_context(feature_context):
        _invalid("FACTORY_CANDIDATE_SEMANTIC_CONTEXT_INVALID")
    feature_context.__post_init__()
    return feature_context


def _execute_training_and_admission(
        run_dir, source_context, parent, prepared, feature_context, generation, cache,
        resource_plan, teacher_hparams, max_norm, candidate, currentness_transaction,
        salience_supervision, mentor_supervision, distributed_profile,
        distributed_executor):
    parameters = dict((parent.retained_state.optimizer if candidate is None
                       else candidate.optimizer).parameters)
    if len(prepared.compiled_rows) == 1:
        gradient, authority, targets = execute_factory_training_row(
            parameters, prepared.compiled_rows[0], source_context,
            feature_context.snapshot, generation, cache,
            salience_supervision=salience_supervision,
            mentor_supervision=mentor_supervision)
        authorities, target_rows = (authority,), (targets,)
        optimizer_started = time.perf_counter()
        transaction = admit_uninterrupted_candidate_step(
            Path(run_dir), parent, loss_bearing_target=True,
            gradient_execution=gradient, teacher_hparams=teacher_hparams,
            max_norm=max_norm, candidate=candidate, execution_cache=cache,
            currentness_transaction=currentness_transaction)
        loss_total = gradient.loss_total
        c08_metrics = (1, 0, 1, 0, None)
    else:
        if (distributed_profile is None) != (distributed_executor is None):
            _invalid("FACTORY_DISTRIBUTED_CONFIGURATION_INCOMPLETE")
        if distributed_profile is None:
            gradient, authorities, target_rows = execute_factory_logical_batch(
                parameters, prepared, source_context, feature_context.snapshot,
                generation, cache, resource_plan,
                salience_supervision=salience_supervision,
                mentor_supervision=mentor_supervision)
            logical_batch_wall_seconds = gradient.wall_seconds
        else:
            if (type(distributed_profile) is not DistributedExecutionProfile
                    or type(distributed_executor) is not DistributedExecutorBinding
                    or distributed_executor.profile != distributed_profile):
                _invalid("FACTORY_DISTRIBUTED_CONFIGURATION_INVALID")
            distributed_started = time.perf_counter()
            manifest = issue_distributed_step_manifest(
                parent, prepared.training_batch, resource_plan,
                distributed_profile)
            persist_distributed_manifest(Path(run_dir), manifest)
            outcome = distributed_executor.execute(
                parameters=parameters, prepared=prepared,
                source_context=source_context,
                feature_snapshot=feature_context.snapshot,
                generation=generation, cache=cache, resource_plan=resource_plan,
                manifest=manifest, salience_supervision=salience_supervision,
                mentor_supervision=mentor_supervision)
            if type(outcome) is not DistributedStepOutcome:
                _invalid("FACTORY_DISTRIBUTED_OUTCOME_REQUIRED")
            gradient, authorities, target_rows = bind_factory_distributed_outcome(
                prepared, source_context, feature_context.snapshot, generation,
                resource_plan, manifest, outcome)
            logical_batch_wall_seconds = time.perf_counter() - distributed_started
        optimizer_started = time.perf_counter()
        transaction = admit_uninterrupted_candidate_step(
            Path(run_dir), parent, loss_bearing_target=True,
            logical_batch_execution=gradient,
            training_batch=prepared.training_batch,
            logical_batch_plan=resource_plan,
            teacher_hparams=teacher_hparams, max_norm=max_norm, candidate=candidate,
            execution_cache=cache,
            currentness_transaction=currentness_transaction)
        loss_total = gradient.weighted_mean_loss
        c08_metrics = (
            gradient.gradient_launches, gradient.vectorized_microbatches,
            gradient.materialization_barriers, gradient.scalar_fallback_rows,
            logical_batch_wall_seconds)
    return (
        gradient, authorities, target_rows, transaction, loss_total, c08_metrics,
        time.perf_counter() - optimizer_started,
    )


def _candidate_cost(
        start, stage_metrics, gradient, loss_total, prepared, resource_plan,
        memory_budget, transaction, feature_context,
        semantic_context_materialized_in_step, c08_metrics, retry, identity_before):
    gradient_observation = dict(getattr(gradient, "_performance_observation", {}) or {})
    c08_row_inputs_seconds = float(
        gradient_observation.get("c08_row_execution_inputs_wall_seconds", 0.0))
    c08_result_seconds = float(
        gradient_observation.get("c08_result_construction_wall_seconds", 0.0))
    c08_wall_seconds = float(c08_metrics[4] or 0.0)
    stage_metrics["candidate_training_orchestration_wall_seconds"] = max(
        0.0,
        stage_metrics.pop("retry_wall_seconds")
        - c08_row_inputs_seconds
        - c08_wall_seconds
        - c08_result_seconds
        - stage_metrics["optimizer_admission_wall_seconds"]
        - stage_metrics["motif_staging_wall_seconds"],
    )
    reporting_started = time.perf_counter()
    cost = _realized_candidate_cost(
        start, stage_metrics["candidate_step_started_at"], loss_total,
        prepared, resource_plan, memory_budget, transaction,
        feature_context, semantic_context_materialized_in_step, c08_metrics,
        stage_metrics, gradient)
    if retry is not None:
        cost["c08_oom_retries"] = retry.retries_used
        cost["c08_original_microbatch_size"] = retry.original_plan.microbatch_size
    cost.update(candidate_identity_metrics_delta(identity_before))
    cost["candidate_reporting_wall_seconds"] = time.perf_counter() - reporting_started
    return cost


def _capture_candidate_result(
        prepared, resource_plan, authorities, target_rows, gradient, transaction,
        cost, source_context, observation, capability, delivered_rows, generation,
        capture_diagnostics, start, candidate_step_started_at):
    evidence_started = time.perf_counter()
    capture_realized_delivery(
        prepared.training_batch, source_context, observation.capture,
        capability, observation.step, tuple(delivered_rows),
        generation_binding=generation, option_rows=observation.option_rows,
        priority=observation.priority, preservation=observation.preservation,
        support=observation.support, enrichment=observation.enrichment,
        guidance=observation.guidance, controls=observation.controls,
        seed=observation.seed, cost=cost, prior=observation.prior,
        mentors=observation.mentors)
    cost["evidence_capture_wall_seconds"] = time.perf_counter() - evidence_started
    cost["wall_seconds"] = time.perf_counter() - start
    cost["candidate_step_wall_seconds"] = (
        time.perf_counter() - candidate_step_started_at)
    exclusive_wall_seconds = sum(float(cost.get(name, 0.0) or 0.0) for name in (
        "observer_begin_step_wall_seconds", "source_lane_wait_wall_seconds",
        "source_lesson_materialization_wall_seconds", "mentor_observation_wall_seconds",
        "progress_emission_wall_seconds", "currentness_binding_wall_seconds",
        "candidate_delivery_setup_wall_seconds", "factory_request_validation_wall_seconds",
        "factory_semantic_context_wall_seconds", "factory_prepared_source_validation_wall_seconds",
        "factory_training_compile_wall_seconds", "factory_b11_binding_wall_seconds",
        "factory_motif_planning_wall_seconds", "factory_result_construction_wall_seconds",
        "salience_preparation_wall_seconds", "mentor_supervision_currentness_wall_seconds",
        "mentor_evidence_validation_wall_seconds", "resource_plan_wall_seconds",
        "prepared_feature_context_wall_seconds", "c08_row_execution_inputs_wall_seconds",
        "c08_logical_batch_wall_seconds", "c08_result_construction_wall_seconds",
        "candidate_training_orchestration_wall_seconds", "optimizer_admission_wall_seconds",
        "motif_staging_wall_seconds", "candidate_reporting_wall_seconds",
        "evidence_capture_wall_seconds",
    ))
    cost["candidate_unattributed_wall_seconds"] = max(
        0.0, cost["candidate_step_wall_seconds"] - exclusive_wall_seconds)
    diagnostics = _reporting_diagnostics(gradient, capture_diagnostics)
    return FactoryCandidateStep(
        prepared, resource_plan,
        authorities[0] if len(authorities) == 1 else authorities,
        target_rows[0] if len(target_rows) == 1 else target_rows,
        diagnostics, transaction, cost)


def _execute_prepared_candidate(
        run_dir, source_context, parent, atlas_artifact_path, delivered_rows, *,
        capability, teacher_hparams, max_norm, observation, memory_budget,
        cache, generation, prepared, start, capture_diagnostics,
        salience_supervision=None, candidate=None, currentness_transaction=None,
        mentor_supervision=None,
        accepted_cache=None,
        semantic_context=None,
        semantic_context_materialized_in_step=False,
        stage_metrics=None, distributed_profile=None, distributed_executor=None,
        finalize_candidate=True) -> FactoryCandidateStep:
    stage_metrics = dict(stage_metrics or {})
    mentor_evidence_started = time.perf_counter()
    if mentor_supervision is not None:
        try:
            mentor_supervision.require_evidence(
                observation.mentors, observation.guidance)
        except BilqisError:
            _invalid("FACTORY_MENTOR_EVIDENCE_DRIFT")
    stage_metrics["mentor_evidence_validation_wall_seconds"] = (
        time.perf_counter() - mentor_evidence_started
        if mentor_supervision is not None else 0.0)
    identity_before = candidate_identity_metrics_snapshot()
    resource_plan_started = time.perf_counter()
    resource_plan, memory_budget = _resource_plan(prepared, parent, memory_budget)
    stage_metrics["resource_plan_wall_seconds"] = (
        time.perf_counter() - resource_plan_started)
    feature_context_started = time.perf_counter()
    feature_context = _prepared_feature_context(prepared, semantic_context)
    stage_metrics["prepared_feature_context_wall_seconds"] = (
        time.perf_counter() - feature_context_started)
    def execute(plan):
        (gradient, authorities, target_rows, transaction, loss_total, c08_metrics,
         optimizer_seconds) = _execute_training_and_admission(
            run_dir, source_context, parent, prepared, feature_context, generation,
            cache, plan, teacher_hparams, max_norm, candidate, currentness_transaction,
            salience_supervision, mentor_supervision, distributed_profile,
            distributed_executor)
        motif_started = time.perf_counter()
        if finalize_candidate:
            transaction = _stage_retained_motifs(
                run_dir, parent, cache, transaction, prepared, plan, memory_budget,
                currentness_transaction=currentness_transaction)
        motif_seconds = time.perf_counter() - motif_started if finalize_candidate else 0.0
        return (gradient, authorities, target_rows, transaction, loss_total,
                c08_metrics, optimizer_seconds, motif_seconds)

    def require_current():
        if currentness_transaction is not None:
            from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
                refresh_accepted_currentness,
            )
            refresh_accepted_currentness(currentness_transaction, parent)
        return _candidate_cache_and_generation(
            run_dir, source_context, parent, candidate, currentness_transaction,
            accepted_cache=accepted_cache)

    retry_started = time.perf_counter()
    result, resource_plan, retry = execute_with_oom_retry(
        execute, resource_plan, parent=parent, candidate=candidate, prepared=prepared,
        budget=memory_budget, cache=cache, require_current=require_current)
    retry_wall_seconds = time.perf_counter() - retry_started
    (gradient, authorities, target_rows, transaction, loss_total, c08_metrics,
     optimizer_wall_seconds, motif_seconds) = result
    stage_metrics["optimizer_admission_wall_seconds"] = optimizer_wall_seconds
    stage_metrics["motif_staging_wall_seconds"] = motif_seconds
    stage_metrics["candidate_terminal_step"] = finalize_candidate
    stage_metrics["retry_wall_seconds"] = retry_wall_seconds
    cost = _candidate_cost(
        start, stage_metrics, gradient, loss_total, prepared, resource_plan,
        memory_budget, transaction, feature_context,
        semantic_context_materialized_in_step, c08_metrics, retry, identity_before)
    return _capture_candidate_result(
        prepared, resource_plan, authorities, target_rows, gradient, transaction,
        cost, source_context, observation, capability, delivered_rows, generation,
        capture_diagnostics, start, stage_metrics["candidate_step_started_at"])


def _candidate_cache_and_generation(run_dir, source_context, parent, candidate,
                                    currentness_transaction, *,
                                    accepted_cache=None):
    if accepted_cache is None:
        source_context.require_accepted_runtime(Path(run_dir))
    if accepted_cache is not None:
        if currentness_transaction is None:
            _invalid("FACTORY_CANDIDATE_ACCEPTED_CACHE_CURRENTNESS_REQUIRED")
        from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
            require_accepted_currentness,
        )
        cache = require_accepted_currentness(
            currentness_transaction, cache=accepted_cache, parent=parent)._cache
    elif currentness_transaction is None:
        cache = bind_accepted_execution_cache(Path(run_dir))
    else:
        from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
            require_accepted_currentness,
        )
        cache = require_accepted_currentness(
            currentness_transaction, parent=parent)._cache
    if candidate is not None:
        cache = bind_candidate_execution_cache(
            cache, parent, candidate, spec=parent.topology, extents=parent.extents)
    parameters = (
        parent.retained_state.optimizer if candidate is None else candidate.optimizer
    ).parameters
    generation = bind_execution_generation(
        cache, parameters, spec=parent.topology,
        extents=parent.extents).generation_digest
    if cache.generation_binding != generation:
        _invalid("FACTORY_CANDIDATE_STEP_GENERATION_DRIFT")
    return cache, generation
