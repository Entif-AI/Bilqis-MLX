"""Strict accepted-priority candidate delivery and execution composition."""
from dataclasses import replace
import math
from pathlib import Path
import time

from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.atlas_training_contracts import BamfVisitProvenance
from bilqis_mlx.runtime.bamf_operator.session_parts.fresh_support import (
    FreshSupportSpecimen, require_fresh_support_authority,
)
from bilqis_mlx.runtime.factory_candidate_training import execute_factory_candidate_step

from .accepted_priority_candidate import (
    _candidate_visit_inputs, _invalid, _refresh_candidate_step,
    _require_live_currentness_fence,
)
from .accepted_priority_visit_contracts import _require_issued
from .accepted_teacher_custody import _require_current_visit


def _rehearsal_inputs(rows, bindings, authorities):
    rehearsal = tuple(rows)
    by_id = {} if bindings is None else dict(bindings)
    source_bindings = {} if authorities is None else dict(authorities)
    if set(by_id) != {row.get("id") for row in rehearsal}:
        _invalid('BAMF_PRIORITY_REHEARSAL_BINDING_DRIFT')
    return rehearsal, by_id, source_bindings


def _fresh_support_inputs(
        source_context, rows, roles, binding, authority, unavailable_reason,
        depth_control):
    rows, roles = tuple(rows), {} if roles is None else dict(roles)
    if set(roles) != {row.get("id") for row in rows}:
        _invalid("BAMF_PRIORITY_FRESH_SUPPORT_ROLE_DRIFT")
    if not rows:
        if binding is not None or authority is not None:
            _invalid("BAMF_PRIORITY_FRESH_SUPPORT_ROLE_DRIFT")
        controls = {"fresh_support_delivered": 0}
        if depth_control is not None and unavailable_reason is None:
            if not isinstance(depth_control, str) or not depth_control:
                _invalid("BAMF_PRIORITY_FRESH_SUPPORT_ROLE_DRIFT")
            controls["depth_control"] = depth_control
        elif unavailable_reason:
            if depth_control is not None:
                _invalid("BAMF_PRIORITY_FRESH_SUPPORT_ROLE_DRIFT")
            controls["depth_control_unavailable_reason"] = unavailable_reason
        return rows, roles, controls
    specimen = FreshSupportSpecimen(
        rows, binding, authority, depth_control, unavailable_reason)
    require_fresh_support_authority(source_context, specimen)
    if (len(rows) != 1 or any(role != "fresh_support" for role in roles.values())
            or unavailable_reason is not None
            or not isinstance(depth_control, str) or not depth_control):
        _invalid("BAMF_PRIORITY_FRESH_SUPPORT_ROLE_DRIFT")
    return rows, roles, {
        "fresh_support_delivered": 1, "depth_control": depth_control,
    }


def _candidate_delivery_inputs(
        selection, source_context, prepared_source_rows, prepared_enrichment_rows,
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_bindings,
        rehearsal_authorities, observation, *, prepared_fresh_support_rows=(),
        fresh_support_by_id=None, fresh_support_binding=None,
        fresh_support_authority=None, fresh_support_unavailable_reason=None,
        fresh_support_depth_control=None, prepared_primary_lesson=None,
        exact_miss_instruction=None):
    offer = selection.offer
    rows = offer.rows() if prepared_source_rows is None else tuple(prepared_source_rows)
    enrichment = tuple(prepared_enrichment_rows)
    rehearsal, role_bindings, source_authorities = _rehearsal_inputs(
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_authorities)
    binding_records = {} if rehearsal_bindings is None else dict(rehearsal_bindings)
    if set(binding_records) != set(role_bindings) or set(source_authorities) != set(role_bindings):
        _invalid('BAMF_PRIORITY_REHEARSAL_AUTHORITY_DRIFT')
    prior = tuple(row for row in rehearsal if role_bindings[row["id"]] == "prior")
    preservation = tuple(
        row for row in rehearsal if role_bindings[row["id"]] == "preservation")
    support = tuple(
        row for row in rehearsal if role_bindings[row["id"]] == "retention_support")
    fresh_support, fresh_roles, fresh_controls = _fresh_support_inputs(
        source_context, prepared_fresh_support_rows, fresh_support_by_id,
        fresh_support_binding, fresh_support_authority,
        fresh_support_unavailable_reason, fresh_support_depth_control)
    primary_lesson = (getattr(selection, "metadata", None) or {}).get("primary_lesson")
    if prepared_primary_lesson is not None:
        from bilqis_mlx.runtime.priority_lesson import require_step_primary_lesson
        offer, primary_lesson = require_step_primary_lesson(
            prepared_primary_lesson, source_context, selection, rows, observation.step)
    if primary_lesson is not None:
        if rows != offer.rows() or len(rows) != primary_lesson["delivered_rows"]:
            _invalid("BAMF_PRIORITY_PRIMARY_LESSON_DRIFT")
        fresh_controls.pop("depth_control", None)
        fresh_controls.pop("depth_control_unavailable_reason", None)
        fresh_controls.update(primary_lesson["controls"])
    capability = offer.capability_id
    from bilqis_mlx.runtime.retention.local_preflight import require_exact_miss_delivery
    exact_ids = require_exact_miss_delivery(
        exact_miss_instruction, source_context, selection, observation,
        rehearsal, role_bindings, binding_records, source_authorities,
        reserved_rows=(*rows, *enrichment, *fresh_support))
    exact_controls = ({
        "exact_miss_delivery_ids": exact_ids,
        "exact_miss_replay_delivered": len(exact_ids),
    } if exact_ids else {})
    from bilqis_mlx.runtime.bamf_operator.session_parts.weakness_rehearsal import (
        delivered_weakness_controls,
    )
    weakness_controls = delivered_weakness_controls(
        source_context, capability, preservation, binding_records)
    execution = source_context.release.execution_plan.capability_map[capability]
    delivery = describe_delivered_teaching(
        source_context.release, capability, execution.teaching_option_ids[0], rows)
    observation = replace(
        observation, option_rows=rows, seed=offer.source_seed,
        prior=prior, preservation=preservation, support=support,
        controls={
            **observation.controls,
            "fragile_preservation_delivered": len(preservation) - len(exact_ids),
            "retention_support_delivered": len(support), **fresh_controls,
            **weakness_controls, **exact_controls,
        },
        **({"enrichment": enrichment} if enrichment else {}),
        **({"fresh_support": fresh_support} if fresh_support else {}))
    return (offer, rows, enrichment, rehearsal, role_bindings, binding_records,
            source_authorities, fresh_support, fresh_roles, capability, delivery,
            observation)


def _candidate_delivery_setup(
        selection, source_context, prepared_source_rows,
        prepared_enrichment_rows, prepared_rehearsal_rows, rehearsal_by_id,
        rehearsal_bindings, rehearsal_authorities, observation, teacher_hparams, **fresh):
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    strict = strict_mode_enabled()
    started = time.perf_counter() if strict else None
    policy = selection.policy
    lr = policy.get('lr') if isinstance(policy, dict) else None
    if (type(teacher_hparams) is not AdamWHyperparameters
            or type(lr) not in (int, float) or not math.isfinite(lr) or lr <= 0):
        _invalid('BAMF_PRIORITY_TEACHER_RATE_INVALID')
    hparams = replace(teacher_hparams, learning_rate=float(lr))
    delivery_inputs = _candidate_delivery_inputs(
        selection, source_context, prepared_source_rows, prepared_enrichment_rows,
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_bindings,
        rehearsal_authorities, observation, **fresh)
    return (
        policy, hparams, delivery_inputs,
        time.perf_counter() - started if strict else 0.0,
    )


def _currentness_for_step(
        visit_binding, currentness_step, planning_generation, parent, timings):
    if visit_binding is None:
        return _require_live_currentness_fence(
            currentness_step, planning_generation, parent, timings), timings
    return _refresh_candidate_step(visit_binding)


def _strict_candidate_result(
        selection, source_context, atlas_path, feature_path, parent, planning_generation,
        cache, semantic_context, prepared_source, delivery_inputs, policy, hparams,
        accepted_cache,
        observation, optimizer_step_seed, max_norm, memory_budget, salience_provider,
        capture_diagnostics, candidate, finalize_candidate, candidate_step_started_at,
        currentness_wall_seconds, currentness_timings, caller_pre_neural_wall_seconds,
        source_lane_wait_wall_seconds, source_lesson_materialization_wall_seconds,
        mentor_observation_wall_seconds, progress_emission_wall_seconds,
        observer_begin_step_wall_seconds, setup_wall_seconds, distributed_profile,
        distributed_executor):
    (offer, rows, enrichment, rehearsal, rehearsal_by_id, rehearsal_bindings,
     rehearsal_authorities, fresh_support, _fresh_roles, capability, delivery,
     observation) = delivery_inputs
    if fresh_support:
        _invalid("BAMF_STRICT_FRESH_SUPPORT_FORBIDDEN")
    delivered_rows = (*rows, *rehearsal, *enrichment)
    provenance = BamfVisitProvenance.from_c03_record(selection.visit.identity.to_record())
    result = execute_factory_candidate_step(
        Path(selection._run_dir), source_context, parent, atlas_path, feature_path,
        delivered_rows, capability=capability, delivery=delivery,
        requested_count=len(delivered_rows), source_seed=offer.source_seed,
        source_each=len(rows) + len(enrichment), optimizer_step_seed=optimizer_step_seed,
        visit_provenance=provenance, teacher_strategy=policy, teacher_hparams=hparams,
        max_norm=max_norm, observation=observation, memory_budget=memory_budget,
        rehearsal_by_id=rehearsal_by_id, rehearsal_bindings=rehearsal_bindings,
        rehearsal_authorities=rehearsal_authorities, salience_provider=salience_provider,
        capture_diagnostics=capture_diagnostics, candidate=candidate,
        finalize_candidate=finalize_candidate,
        currentness_transaction=planning_generation._accepted_currentness,
        candidate_step_started_at=candidate_step_started_at,
        currentness_binding_wall_seconds=currentness_wall_seconds,
        upstream_pre_neural_source_compile_wall_seconds=caller_pre_neural_wall_seconds,
        source_lane_wait_wall_seconds=source_lane_wait_wall_seconds,
        source_lesson_materialization_wall_seconds=source_lesson_materialization_wall_seconds,
        mentor_observation_wall_seconds=mentor_observation_wall_seconds,
        progress_emission_wall_seconds=progress_emission_wall_seconds,
        observer_begin_step_wall_seconds=observer_begin_step_wall_seconds,
        candidate_delivery_setup_wall_seconds=setup_wall_seconds,
        semantic_context=semantic_context,
        prepared_source=(prepared_source if not enrichment and not rehearsal else None),
        accepted_cache=accepted_cache,
        selected_source_authority=(
            offer.source_authority if (getattr(selection, "metadata", None) or {}).get(
                "primary_lesson") is not None else None),
        distributed_profile=distributed_profile, distributed_executor=distributed_executor)
    if not hasattr(result, "realized_cost"):
        return result
    cost = dict(result.realized_cost)
    cost.update(currentness_timings)
    cost["candidate_binding_wall_seconds"] = max(
        0.0, float(cost.get("currentness_binding_wall_seconds", 0.0))
        - currentness_wall_seconds)
    return replace(result, realized_cost=cost)


def execute_accepted_priority_candidate(selection, source_context,
        atlas_artifact_path, feature_artifact_path, *, teacher_hparams, observation,
        optimizer_step_seed, max_norm, memory_budget=None, salience_provider=None,
        capture_diagnostics=False, candidate=None, finalize_candidate=True,
        prepared_source_rows=None, prepared_enrichment_rows=(),
        prepared_rehearsal_rows=(), rehearsal_by_id=None, rehearsal_bindings=None,
        rehearsal_authorities=None, prepared_fresh_support_rows=(),
        fresh_support_by_id=None, fresh_support_binding=None, fresh_support_authority=None,
        fresh_support_unavailable_reason=None, fresh_support_depth_control=None,
        candidate_step_started_at=None, source_prepare_wall_seconds=0.0,
        source_lane_wait_wall_seconds=0.0, source_lesson_materialization_wall_seconds=0.0,
        mentor_observation_wall_seconds=0.0, progress_emission_wall_seconds=0.0,
        observer_begin_step_wall_seconds=0.0, candidate_visit=None,
        distributed_profile=None, distributed_executor=None):
    _require_issued(selection)
    if selection.status != 'TEACHER_SELECTED':
        return selection
    started = time.perf_counter() if candidate_step_started_at is None else candidate_step_started_at
    (planning_generation, parent, cache, currentness_step, semantic_context,
     prepared_source, timings, visit_binding) = _candidate_visit_inputs(
        selection, source_context, prepared_source_rows, candidate_visit)
    fresh = dict(
        prepared_fresh_support_rows=prepared_fresh_support_rows,
        fresh_support_by_id=fresh_support_by_id, fresh_support_binding=fresh_support_binding,
        fresh_support_authority=fresh_support_authority,
        fresh_support_unavailable_reason=fresh_support_unavailable_reason,
        fresh_support_depth_control=fresh_support_depth_control)
    policy, hparams, inputs, setup_seconds = _candidate_delivery_setup(
        selection, source_context, prepared_source_rows, prepared_enrichment_rows,
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_bindings,
        rehearsal_authorities, observation, teacher_hparams, **fresh)
    currentness_seconds, timings = _currentness_for_step(
        visit_binding, currentness_step, planning_generation, parent, timings)
    return _strict_candidate_result(
        selection, source_context, atlas_artifact_path, feature_artifact_path, parent,
        planning_generation, cache, semantic_context, prepared_source, inputs, policy,
        hparams, (cache if visit_binding is not None else None), observation,
        optimizer_step_seed, max_norm, memory_budget,
        salience_provider, capture_diagnostics, candidate, finalize_candidate, started,
        currentness_seconds, timings, float(source_prepare_wall_seconds) + setup_seconds,
        source_lane_wait_wall_seconds, source_lesson_materialization_wall_seconds,
        mentor_observation_wall_seconds, progress_emission_wall_seconds,
        observer_begin_step_wall_seconds, setup_seconds, distributed_profile,
        distributed_executor)


__all__ = (
    "_candidate_delivery_inputs", "_candidate_delivery_setup",
    "execute_accepted_priority_candidate",
)
