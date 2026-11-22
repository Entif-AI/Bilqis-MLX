"""Execution half of one accepted C03 priority visit."""
from dataclasses import dataclass, field, replace
import math
from pathlib import Path
import time

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.atlas_training_contracts import BamfVisitProvenance
from bilqis_mlx.runtime.factory_candidate_training import execute_factory_candidate_step

from .accepted_priority_visit_contracts import _require_issued
from .accepted_teacher_custody import _require_current_visit


_VISIT_CANDIDATE_ISSUER = object()


def _invalid(reason):
    ErrorBus.Raise(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


@dataclass(frozen=True, init=False, eq=False)
class AcceptedPriorityCandidateVisit:
    """Visit-bound immutable authority reused by steady-state candidate steps."""

    selection: object = field(repr=False, compare=False)
    source_context: object = field(repr=False, compare=False)
    planning_generation: object = field(repr=False, compare=False)
    parent: object = field(repr=False, compare=False)
    cache: object = field(repr=False, compare=False)
    semantic_context: object = field(repr=False, compare=False)
    prepared_source: object = field(repr=False, compare=False)
    release_sha256: str
    _issuance: object = field(repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid('BAMF_PRIORITY_CANDIDATE_VISIT_CALLER_CONSTRUCTION_FORBIDDEN')


def _rehearsal_inputs(rows, bindings, authorities):
    rehearsal = tuple(rows)
    by_id = {} if bindings is None else dict(bindings)
    source_bindings = {} if authorities is None else dict(authorities)
    roles = {row.get("id") for row in rehearsal}
    if set(by_id) != roles:
        _invalid('BAMF_PRIORITY_REHEARSAL_BINDING_DRIFT')
    return rehearsal, by_id, source_bindings


def _candidate_delivery_inputs(
        selection, source_context, prepared_source_rows, prepared_enrichment_rows,
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_bindings,
        rehearsal_authorities, observation):
    offer = selection.offer
    rows = offer.rows() if prepared_source_rows is None else tuple(prepared_source_rows)
    enrichment = tuple(prepared_enrichment_rows)
    rehearsal, role_bindings, source_authorities = _rehearsal_inputs(
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_authorities)
    binding_records = {} if rehearsal_bindings is None else dict(rehearsal_bindings)
    if set(binding_records) != set(role_bindings) or set(source_authorities) != set(role_bindings):
        _invalid('BAMF_PRIORITY_REHEARSAL_AUTHORITY_DRIFT')
    capability = offer.capability_id
    execution = source_context.release.execution_plan.capability_map[capability]
    delivery = describe_delivered_teaching(
        source_context.release, capability, execution.teaching_option_ids[0], rows)
    observation = replace(
        observation, option_rows=rows, seed=offer.source_seed,
        **({"enrichment": enrichment} if enrichment else {}))
    return (offer, rows, enrichment, rehearsal, role_bindings, binding_records,
            source_authorities, capability, delivery, observation)


def _candidate_currentness(selection, source_context, prepared_source_rows):
    planning_generation = selection.offer._planning_generation
    from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
        refresh_accepted_currentness,
    )
    stage_started = time.perf_counter()
    currentness_step = refresh_accepted_currentness(
        planning_generation._accepted_currentness, planning_generation._parent)
    timings = {
        "accepted_currentness_refresh_wall_seconds": (
            time.perf_counter() - stage_started),
    }
    stage_started = time.perf_counter()
    parent, cache = selection.offer.require_current_parent(source_context)
    timings["accepted_parent_currentness_wall_seconds"] = (
        time.perf_counter() - stage_started)
    lawful_frontier = selection._lawful_frontier
    if (lawful_frontier is None
            or getattr(lawful_frontier, '_planning_generation', None)
               is not planning_generation):
        _invalid('BAMF_PRIORITY_LAWFUL_FRONTIER_BINDING_DRIFT')
    from bilqis_mlx.runtime.lawful_teaching_frontier import (
        require_bound_lawful_teaching_frontier,
    )
    stage_started = time.perf_counter()
    require_bound_lawful_teaching_frontier(
        lawful_frontier, source_context, parent, currentness_step=currentness_step)
    timings["lawful_frontier_currentness_wall_seconds"] = (
        time.perf_counter() - stage_started)
    if selection.offer.capability_id not in set(lawful_frontier.ready_capability_ids):
        _invalid('BAMF_PRIORITY_SELECTION_OUTSIDE_LAWFUL_FRONTIER')
    stage_started = time.perf_counter()
    _require_current_visit(
        parent, cache, selection.visit,
        candidate_identity_sha256=planning_generation.parent_candidate_identity_sha256,
        currentness_step=currentness_step,
        currentness_transaction=planning_generation._accepted_currentness)
    timings["teacher_visit_currentness_wall_seconds"] = (
        time.perf_counter() - stage_started)
    stage_started = time.perf_counter()
    prepared_source = (
        selection.offer.require_current(source_context, parent)
        if prepared_source_rows is None else
        selection.offer.require_current(
            source_context, parent, prepared_rows=prepared_source_rows))
    timings["source_currentness_wall_seconds"] = (
        time.perf_counter() - stage_started)
    source_observation = getattr(prepared_source, "_performance_observation", {})
    if isinstance(source_observation, dict):
        timings.update({
            name: float(value)
            for name, value in source_observation.items()
            if name.startswith("source_currentness_")
            and name != "source_currentness_wall_seconds"
        })
    return (
        planning_generation, parent, cache, currentness_step,
        planning_generation._authenticated_features, prepared_source, timings,
    )


def _require_live_currentness_fence(
        currentness_step, planning_generation, parent, currentness_timings):
    from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
        require_live_accepted_currentness_step,
    )
    stage_started = time.perf_counter()
    require_live_accepted_currentness_step(
        currentness_step, planning_generation._accepted_currentness, parent)
    currentness_timings["accepted_currentness_live_fence_wall_seconds"] = (
        time.perf_counter() - stage_started)
    return sum(currentness_timings[name] for name in (
        "accepted_currentness_refresh_wall_seconds",
        "accepted_parent_currentness_wall_seconds",
        "lawful_frontier_currentness_wall_seconds",
        "teacher_visit_currentness_wall_seconds",
        "source_currentness_wall_seconds",
        "accepted_currentness_live_fence_wall_seconds",
    ))


def _issue_candidate_visit(
        selection, source_context, planning_generation, parent, cache,
        semantic_context, prepared_source):
    binding = object.__new__(AcceptedPriorityCandidateVisit)
    release_sha256 = source_context.release.release_sha256
    for name, value in (
            ('selection', selection), ('source_context', source_context),
            ('planning_generation', planning_generation), ('parent', parent),
            ('cache', cache), ('semantic_context', semantic_context),
            ('prepared_source', prepared_source),
            ('release_sha256', release_sha256),
            ('_issuance', _VISIT_CANDIDATE_ISSUER)):
        object.__setattr__(binding, name, value)
    return binding


def _require_candidate_visit(binding, selection, source_context):
    if (type(binding) is not AcceptedPriorityCandidateVisit
            or getattr(binding, '_issuance', None) is not _VISIT_CANDIDATE_ISSUER
            or binding.selection is not selection
            or binding.source_context is not source_context
            or binding.planning_generation is not selection.offer._planning_generation
            or binding.parent is not binding.planning_generation._parent
            or binding.prepared_source.offer is not selection.offer
            or source_context.release.release_sha256 != binding.release_sha256):
        _invalid('BAMF_PRIORITY_CANDIDATE_VISIT_DRIFT')
    return binding


def prepare_accepted_priority_candidate_visit(selection, source_context):
    """Pay static source/frontier/visit authority once before the step loop."""
    _require_issued(selection)
    if selection.status != 'TEACHER_SELECTED':
        _invalid('BAMF_PRIORITY_CANDIDATE_VISIT_REQUIRED')
    (planning_generation, parent, cache, currentness_step, semantic_context,
     prepared_source, currentness_timings) = _candidate_currentness(
        selection, source_context, None)
    _require_live_currentness_fence(
        currentness_step, planning_generation, parent, currentness_timings)
    return _issue_candidate_visit(
        selection, source_context, planning_generation, parent, cache,
        semantic_context, prepared_source)


def _refresh_candidate_step(binding):
    """Fence only mutable accepted/source authority at candidate-step cadence."""
    from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
        refresh_accepted_currentness,
    )
    started = time.perf_counter()
    refresh_accepted_currentness(
        binding.planning_generation._accepted_currentness, binding.parent)
    elapsed = time.perf_counter() - started
    return elapsed, {
        'accepted_currentness_refresh_wall_seconds': elapsed,
    }


def _candidate_visit_inputs(
        selection, source_context, prepared_source_rows, candidate_visit):
    visit_binding = (
        None if candidate_visit is None else
        _require_candidate_visit(candidate_visit, selection, source_context))
    if visit_binding is None:
        values = _candidate_currentness(
            selection, source_context, prepared_source_rows)
        return (*values, None)
    if (prepared_source_rows is not None
            and tuple(prepared_source_rows) != visit_binding.prepared_source.rows):
        _invalid('BAMF_PRIORITY_CANDIDATE_SOURCE_ROWS_DRIFT')
    return (
        visit_binding.planning_generation,
        visit_binding.parent,
        visit_binding.cache,
        None,
        visit_binding.semantic_context,
        visit_binding.prepared_source,
        {},
        visit_binding,
    )


def _candidate_delivery_setup(
        selection, source_context, prepared_source_rows,
        prepared_enrichment_rows, prepared_rehearsal_rows, rehearsal_by_id,
        rehearsal_bindings, rehearsal_authorities, observation, teacher_hparams):
    started = time.perf_counter()
    policy = selection.policy
    lr = policy.get('lr') if isinstance(policy, dict) else None
    if (type(teacher_hparams) is not AdamWHyperparameters
            or type(lr) not in (int, float) or not math.isfinite(lr) or lr <= 0):
        _invalid('BAMF_PRIORITY_TEACHER_RATE_INVALID')
    hparams = replace(teacher_hparams, learning_rate=float(lr))
    delivery_inputs = _candidate_delivery_inputs(
        selection, source_context, prepared_source_rows, prepared_enrichment_rows,
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_bindings,
        rehearsal_authorities, observation)
    return policy, hparams, delivery_inputs, time.perf_counter() - started


def execute_accepted_priority_candidate(selection, source_context,
        atlas_artifact_path, feature_artifact_path, *, teacher_hparams, observation,
        optimizer_step_seed, max_norm, memory_budget=None, salience_provider=None,
        capture_diagnostics=False, candidate=None, finalize_candidate=True,
        prepared_source_rows=None, prepared_enrichment_rows=(),
        prepared_rehearsal_rows=(), rehearsal_by_id=None,
        rehearsal_bindings=None, rehearsal_authorities=None,
        candidate_step_started_at=None,
        source_prepare_wall_seconds=0.0,
        source_lane_wait_wall_seconds=0.0,
        source_lesson_materialization_wall_seconds=0.0,
        mentor_observation_wall_seconds=0.0,
        progress_emission_wall_seconds=0.0,
        observer_begin_step_wall_seconds=0.0,
        candidate_visit=None,
        distributed_profile=None, distributed_executor=None):
    _require_issued(selection)
    if selection.status != 'TEACHER_SELECTED':
        return selection
    if candidate_step_started_at is None:
        candidate_step_started_at = time.perf_counter()
    (planning_generation, parent, cache, currentness_step, semantic_context,
     prepared_source, currentness_timings, visit_binding) = _candidate_visit_inputs(
        selection, source_context, prepared_source_rows, candidate_visit)
    (policy, hparams, delivery_inputs,
     candidate_delivery_setup_wall_seconds) = _candidate_delivery_setup(
        selection, source_context, prepared_source_rows, prepared_enrichment_rows,
        prepared_rehearsal_rows, rehearsal_by_id, rehearsal_bindings,
        rehearsal_authorities, observation, teacher_hparams)
    (offer, rows, enrichment, rehearsal, rehearsal_by_id, rehearsal_bindings,
     rehearsal_authorities, capability, delivery, observation) = delivery_inputs
    delivered_rows = (*rows, *rehearsal, *enrichment)
    provenance = BamfVisitProvenance.from_c03_record(selection.visit.identity.to_record())
    caller_pre_neural_wall_seconds = (
        float(source_prepare_wall_seconds)
        + candidate_delivery_setup_wall_seconds)
    if visit_binding is None:
        currentness_wall_seconds = _require_live_currentness_fence(
            currentness_step, planning_generation, parent, currentness_timings)
    else:
        currentness_wall_seconds, currentness_timings = _refresh_candidate_step(
            visit_binding)
    result = execute_factory_candidate_step(
        Path(selection._run_dir), source_context, parent,
        atlas_artifact_path, feature_artifact_path, delivered_rows,
        capability=capability, delivery=delivery, requested_count=len(delivered_rows),
        source_seed=offer.source_seed, source_each=len(rows) + len(enrichment),
        optimizer_step_seed=optimizer_step_seed, visit_provenance=provenance,
        teacher_strategy=policy, teacher_hparams=hparams, max_norm=max_norm,
        observation=observation, memory_budget=memory_budget,
        rehearsal_by_id=rehearsal_by_id,
        rehearsal_bindings=rehearsal_bindings,
        rehearsal_authorities=rehearsal_authorities,
        salience_provider=salience_provider, capture_diagnostics=capture_diagnostics,
        candidate=candidate, finalize_candidate=finalize_candidate,
        currentness_transaction=planning_generation._accepted_currentness,
        candidate_step_started_at=candidate_step_started_at,
        currentness_binding_wall_seconds=currentness_wall_seconds,
        upstream_pre_neural_source_compile_wall_seconds=caller_pre_neural_wall_seconds,
        source_lane_wait_wall_seconds=source_lane_wait_wall_seconds,
        source_lesson_materialization_wall_seconds=(
            source_lesson_materialization_wall_seconds),
        mentor_observation_wall_seconds=mentor_observation_wall_seconds,
        progress_emission_wall_seconds=progress_emission_wall_seconds,
        observer_begin_step_wall_seconds=observer_begin_step_wall_seconds,
        candidate_delivery_setup_wall_seconds=candidate_delivery_setup_wall_seconds,
        semantic_context=semantic_context,
        prepared_source=(prepared_source if not enrichment and not rehearsal else None),
        accepted_cache=(cache if visit_binding is not None else None),
        distributed_profile=distributed_profile,
        distributed_executor=distributed_executor)
    if not hasattr(result, "realized_cost"):
        return result
    cost = dict(result.realized_cost)
    cost.update(currentness_timings)
    cost["candidate_binding_wall_seconds"] = max(
        0.0, float(cost.get("currentness_binding_wall_seconds", 0.0))
        - currentness_wall_seconds)
    return replace(result, realized_cost=cost)


__all__ = (
    "AcceptedPriorityCandidateVisit",
    "execute_accepted_priority_candidate",
    "prepare_accepted_priority_candidate_visit",
)
