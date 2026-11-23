"""Observed cost accounting for one native Factory candidate step."""
from __future__ import annotations

import time

from bilqis_mlx.runtime.atlas_resources import DistributedStepTelemetry


def _distributed_cost(prepared, gradient, logical_batch_wall_seconds) -> dict:
    metadata = getattr(gradient, "distributed_metadata", None)
    if metadata is None:
        return {}
    manifest = metadata.manifest
    communication = metadata.communication_seconds
    compute = metadata.compute_seconds_per_worker
    peaks = metadata.peak_memory_per_worker
    step_seconds = max(float(logical_batch_wall_seconds or 0.0), 1e-12)
    logical_positions = sum(
        len(item.compiled.compiled.rows[0].positions)
        for item in prepared.compiled_rows)
    telemetry = DistributedStepTelemetry(
        manifest.digest, len(prepared.compiled_rows), logical_positions,
        compute, communication, step_seconds, 1, peaks, manifest.world_size)
    return {
        "c08_distributed_manifest_digest": manifest.digest,
        "c08_distributed_retained_generation": manifest.retained_generation,
        "c08_distributed_retained_manifest_sha256":
            manifest.retained_manifest_sha256,
        "c08_distributed_logical_batch_digest": manifest.logical_batch_digest,
        "c08_distributed_source_release": manifest.source_release,
        "c08_distributed_curriculum_release": manifest.curriculum_release,
        "c08_distributed_world_size": manifest.world_size,
        "c08_distributed_backend": manifest.backend,
        "c08_distributed_device_families": tuple(
            worker.device_family for worker in manifest.workers),
        "c08_distributed_mlx_version": manifest.mlx_version,
        "c08_distributed_numeric_precision": manifest.numeric_precision,
        "c08_distributed_reduction_policy": manifest.reduction_policy,
        "c08_distributed_compute_seconds_per_worker": compute,
        "c08_distributed_communication_seconds": communication,
        "c08_distributed_peak_memory_bytes_per_worker": peaks,
        "c08_distributed_examples_per_second": telemetry.examples_per_second,
        "c08_distributed_positions_per_second": telemetry.positions_per_second,
        "c08_distributed_attempted_steps_per_hour":
            telemetry.attempted_steps_per_hour,
    }


def _stage_timing_cost(stage_metrics):
    optional = (
        "source_lane_wait_wall_seconds", "source_lesson_materialization_wall_seconds",
        "mentor_observation_wall_seconds", "progress_emission_wall_seconds",
        "observer_begin_step_wall_seconds", "candidate_delivery_setup_wall_seconds",
        "factory_request_validation_wall_seconds", "factory_semantic_context_wall_seconds",
        "factory_prepared_source_validation_wall_seconds", "factory_training_compile_wall_seconds",
        "factory_b11_binding_wall_seconds", "factory_motif_planning_wall_seconds",
        "factory_result_construction_wall_seconds", "salience_preparation_wall_seconds",
        "mentor_supervision_currentness_wall_seconds", "mentor_evidence_validation_wall_seconds",
        "resource_plan_wall_seconds", "prepared_feature_context_wall_seconds",
        "candidate_training_orchestration_wall_seconds",
        "pipeline_host_preparation_wall_seconds",
        "pipeline_host_overlap_wall_seconds",
        "pipeline_host_wait_wall_seconds",
        "pipeline_accelerator_wait_for_host_wall_seconds",
    )
    result = {name: stage_metrics.get(name, 0.0) for name in optional}
    result.update({
        "pre_neural_source_compile_wall_seconds": stage_metrics[
            "pre_neural_source_compile_wall_seconds"],
        "currentness_binding_wall_seconds": stage_metrics["currentness_binding_wall_seconds"],
        "optimizer_admission_wall_seconds": stage_metrics["optimizer_admission_wall_seconds"],
        "motif_staging_wall_seconds": stage_metrics["motif_staging_wall_seconds"],
        "candidate_terminal_step": stage_metrics["candidate_terminal_step"],
        "pipeline_prepared_ahead_used": int(
            stage_metrics.get("pipeline_prepared_ahead_used", 0)),
        "pipeline_discarded_prefetch_work": int(
            stage_metrics.get("pipeline_discarded_prefetch_work", 0)),
    })
    return result


def _b11_timing_cost(b11):
    float_names = (
        "b11_preflight_wall_seconds", "b11_finite_validation_wall_seconds",
        "b11_execution_rebinding_wall_seconds", "b11_refinement_selection_wall_seconds",
        "b11_route_compatibility_wall_seconds", "b11_route_kernel_prepare_wall_seconds",
        "b11_fallback_trace_preflight_wall_seconds", "b11_preflight_other_wall_seconds",
        "b11_autodiff_wall_seconds", "b11_autodiff_dispatch_wall_seconds",
        "b11_autodiff_dispatch_rebind_wall_seconds",
        "b11_autodiff_dispatch_source_producer_wall_seconds",
        "b11_autodiff_dispatch_source_hidden_graph_wall_seconds",
        "b11_autodiff_dispatch_refinement_graph_wall_seconds",
        "b11_autodiff_dispatch_route_graph_wall_seconds",
        "b11_autodiff_dispatch_transform_other_wall_seconds",
        "b11_autodiff_materialization_wall_seconds", "b11_route_evidence_wall_seconds",
        "b11_autodiff_other_wall_seconds", "b11_gradient_finite_validation_wall_seconds",
        "b11_postflight_validation_wall_seconds",
        "b11_postflight_trajectory_validation_wall_seconds",
        "b11_postflight_output_attestation_wall_seconds",
        "b11_postflight_loss_validation_wall_seconds",
        "b11_postflight_gradient_structure_wall_seconds",
        "b11_postflight_result_construction_wall_seconds",
    )
    result = {name: float(b11.get(name, 0.0)) for name in float_names}
    result.update({
        "b11_materialization_barrier_count": int(
            b11.get("b11_materialization_barrier_count", 0)),
        "b11_host_readback_count": int(b11.get("b11_host_readback_count", 0)),
        "b11_validation_sync_count": int(b11.get("b11_validation_sync_count", 0)),
        "b11_provider_draw_count": int(b11.get("b11_provider_draw_count", 0)),
        "b11_atlas_reload_count": int(b11.get("b11_atlas_reload_count", 0)),
    })
    return result


def realized_candidate_cost(
        start, candidate_step_started_at, loss_total, prepared,
        resource_plan, memory_budget, transaction,
        feature_context, semantic_context_materialized_in_step, c08_metrics,
        stage_metrics, gradient, *, invalid):
    gradient_launches, vectorized_microbatches, materialization_barriers, \
        scalar_fallback_rows, logical_batch_wall_seconds = c08_metrics
    b11 = getattr(gradient, "_performance_observation", {})
    if not isinstance(b11, dict):
        b11 = {}
    step_atlas_reloads = (
        feature_context.atlas_reload_count
        if semantic_context_materialized_in_step else 0)
    step_feature_rebuilds = (
        feature_context.feature_manifest_rebuild_count
        if semantic_context_materialized_in_step else 0)
    bound_source_authorities = sum(
        compiled.source_execution_authority is not None
        for compiled in prepared.compiled_rows)
    authority_free_rows = len(prepared.compiled_rows) - bound_source_authorities
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    strict = strict_evidence_enabled()
    if strict and authority_free_rows:
        invalid("FACTORY_CANDIDATE_SOURCE_EXECUTION_AUTHORITY_MISSING")
    cold_requalification_rows = authority_free_rows if strict else 0
    elapsed = time.perf_counter() - start
    cost = {
        "wall_seconds": elapsed,
        "candidate_step_wall_seconds": time.perf_counter() - candidate_step_started_at,
        "logical_rows": len(prepared.compiled_rows),
        "logical_batch_size": len(prepared.compiled_rows),
        "c08_microbatch_size": resource_plan.microbatch_size,
        "c08_microbatch_count": len(resource_plan.groups),
        "compiled_positions": sum(
            len(item.compiled.compiled.rows[0].positions) for item in prepared.compiled_rows),
        "loss_total": float(loss_total.item()),
        "c08_estimated_peak_bytes": resource_plan.estimated_peak_bytes,
        "c08_memory_budget_bytes": memory_budget.allocation_bytes,
        "c08_gradient_launches": gradient_launches,
        "c08_vectorized_microbatches": vectorized_microbatches,
        "c08_materialization_barriers": materialization_barriers,
        "c08_scalar_fallback_rows": scalar_fallback_rows,
        "c08_logical_batch_wall_seconds": logical_batch_wall_seconds,
        "c08_row_execution_inputs_wall_seconds": float(
            b11.get("c08_row_execution_inputs_wall_seconds", 0.0)),
        "c08_group_execution_wall_seconds": float(
            b11.get("c08_group_execution_wall_seconds", 0.0)),
        "c08_aggregation_wall_seconds": float(
            b11.get("c08_aggregation_wall_seconds", 0.0)),
        "c08_final_materialization_wall_seconds": float(
            b11.get("c08_final_materialization_wall_seconds", 0.0)),
        "c08_result_construction_wall_seconds": float(
            b11.get("c08_result_construction_wall_seconds", 0.0)),
        "c08_unattributed_wall_seconds": float(
            b11.get("c08_unattributed_wall_seconds", 0.0)),
        "c08_reused_materialized_full_batch": bool(
            b11.get("c08_reused_materialized_full_batch", False)),
        "c08_rows_per_gradient_launch": len(prepared.compiled_rows) / gradient_launches,
        "optimizer_steps": 1,
        "candidate_optimizer_steps": transaction.update_steps,
        "atlas_reload_count": step_atlas_reloads,
        "feature_manifest_rebuild_count": step_feature_rebuilds,
        "visit_atlas_reload_count": feature_context.atlas_reload_count,
        "visit_feature_manifest_rebuild_count": feature_context.feature_manifest_rebuild_count,
        "b11_source_authority_bound_rows": bound_source_authorities,
        "b11_source_authority_free_rows": authority_free_rows,
        "b11_source_cold_requalification_rows": cold_requalification_rows,
    }
    cost.update(_stage_timing_cost(stage_metrics))
    cost.update(_b11_timing_cost(b11))
    cost.update(_distributed_cost(
        prepared, gradient, logical_batch_wall_seconds))
    return cost


__all__ = ("realized_candidate_cost",)
