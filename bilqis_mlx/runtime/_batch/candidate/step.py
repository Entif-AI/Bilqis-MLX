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
    derive_participation_inputs,
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


from .execution import (
    _execute_training_and_admission, _prepared_feature_context,
    _realized_candidate_cost,
)


from .reporting import _candidate_cost


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
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_evidence_enabled,
        )
        if finalize_candidate and strict_evidence_enabled():
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
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    strict = strict_evidence_enabled()
    if accepted_cache is None:
        source_context.require_accepted_runtime(Path(run_dir))
    if accepted_cache is not None:
        if currentness_transaction is None:
            if strict:
                _invalid("FACTORY_CANDIDATE_ACCEPTED_CACHE_CURRENTNESS_REQUIRED")
            cache = accepted_cache
        else:
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
    if candidate is not None and strict:
        cache = bind_candidate_execution_cache(
            cache, parent, candidate, spec=parent.topology, extents=parent.extents)
    parameters = (
        parent.retained_state.optimizer if candidate is None else candidate.optimizer
    ).parameters
    if strict:
        generation = bind_execution_generation(
            cache, parameters, spec=parent.topology,
            extents=parent.extents).generation_digest
    else:
        from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
        generation = execution_generation_digest(
            parameters, spec=parent.topology, extents=parent.extents)
    if strict and cache.generation_binding != generation:
        _invalid("FACTORY_CANDIDATE_STEP_GENERATION_DRIFT")
    return cache, generation
