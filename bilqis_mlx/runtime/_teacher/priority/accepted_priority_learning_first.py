"""Training-first execution for one accepted C03 priority visit."""
from dataclasses import replace
from pathlib import Path

from bilqis_mlx.runtime.atlas_training_contracts import BamfVisitProvenance
from bilqis_mlx.runtime.factory_candidate_training import execute_factory_candidate_step

from .accepted_priority_candidate import _invalid
from .accepted_priority_candidate_execution import _candidate_delivery_setup
from .accepted_priority_visit_contracts import _require_issued


def _learning_first_delivery(
        selection, source_context, prepared_source_rows, prepared_enrichment_rows,
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_bindings,
        rehearsal_authorities, observation, teacher_hparams,
        prepared_fresh_support_rows, fresh_support_by_id, fresh_support_binding,
        fresh_support_authority, fresh_support_unavailable_reason,
        fresh_support_depth_control):
    planning_generation = selection.offer._planning_generation
    parent = planning_generation._parent
    semantic_context = planning_generation._authenticated_features
    policy, hparams, delivery_inputs, setup_seconds = _candidate_delivery_setup(
        selection, source_context, prepared_source_rows,
        prepared_enrichment_rows, prepared_rehearsal_rows, rehearsal_by_id,
        rehearsal_bindings, rehearsal_authorities, observation, teacher_hparams,
        prepared_fresh_support_rows=prepared_fresh_support_rows,
        fresh_support_by_id=fresh_support_by_id,
        fresh_support_binding=fresh_support_binding,
        fresh_support_authority=fresh_support_authority,
        fresh_support_unavailable_reason=fresh_support_unavailable_reason,
        fresh_support_depth_control=fresh_support_depth_control)
    return parent, semantic_context, policy, hparams, delivery_inputs, setup_seconds


def _learning_first_step_start(candidate_step_started_at, candidate_visit):
    if candidate_step_started_at is None:
        candidate_step_started_at = 0.0
    if candidate_visit is not None:
        _invalid("BAMF_LEARNING_FIRST_CANDIDATE_VISIT_FORBIDDEN")
    return candidate_step_started_at


def execute_learning_first_priority_candidate(
        selection, source_context, atlas_artifact_path, feature_artifact_path, *,
        teacher_hparams, observation, optimizer_step_seed, max_norm,
        memory_budget=None, salience_provider=None, capture_diagnostics=False,
        candidate=None, finalize_candidate=True, prepared_source_rows=None,
        prepared_source_seed=None,
        prepared_enrichment_rows=(), prepared_rehearsal_rows=(),
        rehearsal_by_id=None, rehearsal_bindings=None, rehearsal_authorities=None,
        prepared_fresh_support_rows=(), fresh_support_by_id=None,
        fresh_support_binding=None, fresh_support_authority=None,
        fresh_support_unavailable_reason=None, fresh_support_depth_control=None,
        candidate_step_started_at=None, source_prepare_wall_seconds=0.0,
        source_lane_wait_wall_seconds=0.0,
        source_lesson_materialization_wall_seconds=0.0,
        mentor_observation_wall_seconds=0.0, progress_emission_wall_seconds=0.0,
        observer_begin_step_wall_seconds=0.0, candidate_visit=None,
        accepted_cache=None, learning_first_cache=None,
        prepared_learning_first_source_inputs=None,
        prepared_learning_first_source_identity=None,
        pipeline_host_preparation_wall_seconds=0.0,
        pipeline_host_overlap_wall_seconds=0.0,
        pipeline_host_wait_wall_seconds=0.0,
        pipeline_accelerator_wait_for_host_wall_seconds=0.0,
        distributed_profile=None, distributed_executor=None):
    """Execute a selected lesson without strict source/custody ceremony."""
    _require_issued(selection)
    if selection.status != "TEACHER_SELECTED":
        return selection
    candidate_step_started_at = _learning_first_step_start(
        candidate_step_started_at, candidate_visit)
    (
        parent, semantic_context, policy, hparams, delivery_inputs,
        candidate_delivery_setup_wall_seconds,
    ) = _learning_first_delivery(
        selection, source_context, prepared_source_rows, prepared_enrichment_rows,
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_bindings,
        rehearsal_authorities, observation, teacher_hparams,
        prepared_fresh_support_rows, fresh_support_by_id, fresh_support_binding,
        fresh_support_authority, fresh_support_unavailable_reason,
        fresh_support_depth_control)
    (offer, rows, enrichment, rehearsal, rehearsal_by_id, rehearsal_bindings,
     rehearsal_authorities, fresh_support, fresh_support_by_id, capability, delivery,
     observation) = delivery_inputs
    source_seed = offer.source_seed if prepared_source_seed is None else prepared_source_seed
    if prepared_source_seed is not None:
        observation = replace(observation, seed=source_seed)
    delivered_rows = (*rows, *rehearsal, *enrichment, *fresh_support)
    provenance = BamfVisitProvenance.from_c03_record(selection.visit.identity.to_record())
    return execute_factory_candidate_step(
        Path(selection._run_dir), source_context, parent,
        atlas_artifact_path, feature_artifact_path, delivered_rows,
        capability=capability, delivery=delivery, requested_count=len(delivered_rows),
        source_seed=source_seed, source_each=len(rows) + len(enrichment),
        optimizer_step_seed=optimizer_step_seed, visit_provenance=provenance,
        teacher_strategy=policy, teacher_hparams=hparams, max_norm=max_norm,
        observation=observation, memory_budget=memory_budget,
        rehearsal_by_id=rehearsal_by_id,
        rehearsal_bindings=rehearsal_bindings,
        rehearsal_authorities=rehearsal_authorities,
        fresh_support_by_id=fresh_support_by_id,
        salience_provider=salience_provider, capture_diagnostics=capture_diagnostics,
        candidate=candidate, finalize_candidate=finalize_candidate,
        currentness_transaction=None,
        candidate_step_started_at=candidate_step_started_at,
        currentness_binding_wall_seconds=0.0,
        upstream_pre_neural_source_compile_wall_seconds=(
            float(source_prepare_wall_seconds)
            + candidate_delivery_setup_wall_seconds),
        source_lane_wait_wall_seconds=source_lane_wait_wall_seconds,
        source_lesson_materialization_wall_seconds=(
            source_lesson_materialization_wall_seconds),
        mentor_observation_wall_seconds=mentor_observation_wall_seconds,
        progress_emission_wall_seconds=progress_emission_wall_seconds,
        observer_begin_step_wall_seconds=observer_begin_step_wall_seconds,
        candidate_delivery_setup_wall_seconds=candidate_delivery_setup_wall_seconds,
        semantic_context=semantic_context, prepared_source=None,
        accepted_cache=accepted_cache, selected_source_authority=None,
        learning_first_cache=learning_first_cache,
        prepared_learning_first_source_inputs=prepared_learning_first_source_inputs,
        prepared_learning_first_source_identity=(
            prepared_learning_first_source_identity),
        pipeline_host_preparation_wall_seconds=pipeline_host_preparation_wall_seconds,
        pipeline_host_overlap_wall_seconds=pipeline_host_overlap_wall_seconds,
        pipeline_host_wait_wall_seconds=pipeline_host_wait_wall_seconds,
        pipeline_accelerator_wait_for_host_wall_seconds=(
            pipeline_accelerator_wait_for_host_wall_seconds),
        distributed_profile=distributed_profile,
        distributed_executor=distributed_executor)


__all__ = ("execute_learning_first_priority_candidate",)
