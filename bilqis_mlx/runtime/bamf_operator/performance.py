"""Best-effort live performance projection for the BAMF operator."""
from __future__ import annotations

from contextlib import contextmanager
import time


STEP_COST_FIELDS = (
    "candidate_step_wall_seconds",
    "candidate_unattributed_wall_seconds",
    "pre_neural_source_compile_wall_seconds",
    "source_lane_wait_wall_seconds",
    "source_lesson_materialization_wall_seconds",
    "pipeline_host_preparation_wall_seconds",
    "pipeline_host_overlap_wall_seconds",
    "pipeline_host_wait_wall_seconds",
    "pipeline_accelerator_wait_for_host_wall_seconds",
    "pipeline_prepared_ahead_used",
    "pipeline_discarded_prefetch_work",
    "mentor_observation_wall_seconds",
    "progress_emission_wall_seconds",
    "observer_begin_step_wall_seconds",
    "candidate_delivery_setup_wall_seconds",
    "factory_request_validation_wall_seconds",
    "factory_semantic_context_wall_seconds",
    "factory_prepared_source_validation_wall_seconds",
    "factory_training_compile_wall_seconds",
    "factory_b11_binding_wall_seconds",
    "factory_motif_planning_wall_seconds",
    "factory_result_construction_wall_seconds",
    "salience_preparation_wall_seconds",
    "mentor_supervision_currentness_wall_seconds",
    "mentor_evidence_validation_wall_seconds",
    "resource_plan_wall_seconds",
    "prepared_feature_context_wall_seconds",
    "candidate_training_orchestration_wall_seconds",
    "candidate_reporting_wall_seconds",
    "currentness_binding_wall_seconds",
    "accepted_currentness_refresh_wall_seconds",
    "accepted_currentness_live_fence_wall_seconds",
    "accepted_parent_currentness_wall_seconds",
    "lawful_frontier_currentness_wall_seconds",
    "teacher_visit_currentness_wall_seconds",
    "source_currentness_wall_seconds",
    "source_currentness_qualification_wall_seconds",
    "source_currentness_offer_validate_wall_seconds",
    "source_currentness_planning_generation_wall_seconds",
    "source_currentness_static_binding_wall_seconds",
    "source_currentness_row_decode_wall_seconds",
    "source_currentness_row_authority_wall_seconds",
    "source_currentness_row_canonical_wall_seconds",
    "source_currentness_qualification_owner_wall_seconds",
    "source_currentness_feature_owner_wall_seconds",
    "source_currentness_source_owner_wall_seconds",
    "source_currentness_b11_sources_wall_seconds",
    "source_currentness_packed_frames_wall_seconds",
    "source_currentness_registration_wall_seconds",
    "source_currentness_materialized_other_wall_seconds",
    "source_currentness_internal_other_wall_seconds",
    "candidate_binding_wall_seconds",
    "candidate_identity_full_computations",
    "candidate_identity_numerical_bytes_hashed",
    "candidate_identity_binding_issues",
    "candidate_identity_binding_reuses",
    "candidate_identity_require_calls",
    "candidate_identity_full_hash_wall_seconds",
    "candidate_identity_require_wall_seconds",
    "learning_first_step_token_issues",
    "learning_first_step_token_hits",
    "learning_first_step_token_misses",
    "learning_first_step_full_proof_fallbacks",
    "learning_first_step_token_issue_wall_seconds",
    "learning_first_step_token_require_wall_seconds",
    "b11_preflight_wall_seconds",
    "b11_finite_validation_wall_seconds",
    "b11_execution_rebinding_wall_seconds",
    "b11_refinement_selection_wall_seconds",
    "b11_route_compatibility_wall_seconds",
    "b11_route_kernel_prepare_wall_seconds",
    "b11_fallback_trace_preflight_wall_seconds",
    "b11_preflight_other_wall_seconds",
    "b11_autodiff_wall_seconds",
    "b11_autodiff_dispatch_wall_seconds",
    "b11_autodiff_dispatch_rebind_wall_seconds",
    "b11_autodiff_dispatch_source_producer_wall_seconds",
    "b11_autodiff_dispatch_source_hidden_graph_wall_seconds",
    "b11_autodiff_dispatch_refinement_graph_wall_seconds",
    "b11_autodiff_dispatch_route_graph_wall_seconds",
    "b11_autodiff_dispatch_transform_other_wall_seconds",
    "b11_autodiff_materialization_wall_seconds",
    "b11_route_evidence_wall_seconds",
    "b11_autodiff_other_wall_seconds",
    "b11_gradient_finite_validation_wall_seconds",
    "b11_postflight_validation_wall_seconds",
    "b11_postflight_trajectory_validation_wall_seconds",
    "b11_postflight_output_attestation_wall_seconds",
    "b11_postflight_loss_validation_wall_seconds",
    "b11_postflight_gradient_structure_wall_seconds",
    "b11_postflight_result_construction_wall_seconds",
    "b11_postflight_other_wall_seconds",
    "b11_total_wall_seconds",
    "b11_outer_other_wall_seconds",
    "b11_materialization_barrier_count",
    "b11_host_readback_count",
    "b11_validation_sync_count",
    "optimizer_admission_wall_seconds",
    "motif_staging_wall_seconds",
    "evidence_capture_wall_seconds",
    "candidate_terminal_step",
    "loss_total",
    "c08_gradient_launches",
    "c08_vectorized_microbatches",
    "c08_materialization_barriers",
    "c08_scalar_fallback_rows",
    "c08_logical_batch_wall_seconds",
    "c08_row_execution_inputs_wall_seconds",
    "c08_group_execution_wall_seconds",
    "c08_aggregation_wall_seconds",
    "c08_final_materialization_wall_seconds",
    "c08_result_construction_wall_seconds",
    "c08_unattributed_wall_seconds",
    "c08_reused_materialized_full_batch",
    "c08_rows_per_gradient_launch",
    "b11_provider_draw_count",
    "b11_atlas_reload_count",
    "logical_rows",
    "compiled_positions",
)

VISIT_PERFORMANCE_FIELDS = (
    "accepted_state_setup_wall_seconds",
    "accepted_state_setup_other_wall_seconds",
    "accepted_runtime_host_wall_seconds",
    "accepted_generation_load_wall_seconds",
    "accepted_source_context_wall_seconds",
    "accepted_feature_authentication_wall_seconds",
    "planning_wall_seconds",
    "planning_offer_fanout_wall_seconds",
    "source_materialization_wall_seconds",
    "selected_source_cache_hit",
    "selected_source_cache_lookup_wall_seconds",
    "selected_source_factory_build_wall_seconds",
    "selected_source_model_build_wall_seconds",
    "selected_source_b11_binding_wall_seconds",
    "selected_source_motif_planning_wall_seconds",
    "selected_source_owner_build_wall_seconds",
    "selected_source_registration_currentness_wall_seconds",
    "selected_source_qualification_wall_seconds",
    "target_evaluation_wall_seconds",
    "protected_retention_wall_seconds",
    "broad_certification_wall_seconds",
    "retention_wall_seconds",
    "retention_target_prepare_wall_seconds",
    "retention_target_solver_wall_seconds",
    "retention_target_parent_wall_seconds",
    "retention_target_candidate_wall_seconds",
    "retention_protected_prepare_wall_seconds",
    "retention_protected_parent_solver_wall_seconds",
    "retention_protected_parent_wall_seconds",
    "retention_protected_candidate_solver_wall_seconds",
    "retention_protected_candidate_wall_seconds",
    "retention_decision_finalize_wall_seconds",
    "championship_wall_seconds",
    "championship_prepare_wall_seconds",
    "championship_solver_wall_seconds",
    "championship_candidate_wall_seconds",
    "adviser_wall_seconds",
    "evidence_finalization_wall_seconds",
    "rejection_wall_seconds",
    "publishing_wall_seconds",
)

RETENTION_PROFILE_FIELDS = (
    "retention_target_case_count",
    "retention_protected_case_count",
    "retention_reference_case_count",
    "retention_parent_cache_reused",
    "retention_target_shared_backbone_launches",
    "retention_target_scalar_neural_launches",
    "retention_protected_shared_backbone_launches",
    "retention_protected_scalar_neural_launches",
    "championship_case_count",
    "championship_shared_backbone_launches",
    "championship_scalar_neural_launches",
)

PERFORMANCE_FIELDS = STEP_COST_FIELDS + VISIT_PERFORMANCE_FIELDS

_SELECTED_SOURCE_FIELDS = (
    ("source_materialization_cache_hit", "selected_source_cache_hit"),
    ("source_materialization_cache_lookup_wall_seconds", "selected_source_cache_lookup_wall_seconds"),
    ("source_materialization_wait_wall_seconds", "selected_source_wait_wall_seconds"),
    ("source_materialization_factory_source_wall_seconds", "selected_source_factory_build_wall_seconds"),
    ("source_materialization_model_source_wall_seconds", "selected_source_model_build_wall_seconds"),
    ("source_materialization_b11_binding_wall_seconds", "selected_source_b11_binding_wall_seconds"),
    ("source_materialization_motif_planning_wall_seconds", "selected_source_motif_planning_wall_seconds"),
    ("source_materialization_owner_build_wall_seconds", "selected_source_owner_build_wall_seconds"),
    ("source_materialization_registration_currentness_wall_seconds", "selected_source_registration_currentness_wall_seconds"),
    ("source_currentness_qualification_wall_seconds", "selected_source_qualification_wall_seconds"),
)


def selected_source_visit_fields(observation) -> dict:
    if not isinstance(observation, dict):
        return {}
    return {
        target: observation[source]
        for source, target in _SELECTED_SOURCE_FIELDS
        if type(observation.get(source)) in (int, float) and observation[source] >= 0
    }


def observe_completed_step(observer, step, candidate) -> None:
    """Publish only already-realized host facts; never affect execution."""
    if observer is None:
        return
    try:
        cost = getattr(step, "realized_cost", {})
        fields = {
            name: cost[name] for name in STEP_COST_FIELDS
            if isinstance(cost, dict) and name in cost
        }
        payload = dict(
            candidate_step=candidate.update_steps,
            candidate_optimizer_step=candidate.parent.optimizer_step
            + candidate.update_steps,
            **fields)
        complete_step = getattr(observer, "complete_step", None)
        if callable(complete_step):
            complete_step(**payload)
        else:
            observer.update(**payload)
    except Exception:
        pass


@contextmanager
def measure_observed_phase(observer, field: str):
    """Time an existing host boundary without adding device synchronization."""
    started = time.perf_counter()
    try:
        yield
    finally:
        if observer is not None:
            try:
                stage = getattr(observer, "stage", None)
                if callable(stage):
                    stage(**{field: time.perf_counter() - started})
                else:
                    observer.update(**{field: time.perf_counter() - started})
            except Exception:
                pass


__all__ = (
    "PERFORMANCE_FIELDS", "RETENTION_PROFILE_FIELDS", "STEP_COST_FIELDS",
    "VISIT_PERFORMANCE_FIELDS",
    "measure_observed_phase", "observe_completed_step", "selected_source_visit_fields",
)
