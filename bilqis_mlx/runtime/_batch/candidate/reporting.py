"""Candidate cost reporting helpers."""
from __future__ import annotations

import time

from bilqis_mlx.learning._atlas_candidate.identity_binding import candidate_identity_metrics_delta
from .execution import _realized_candidate_cost


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
