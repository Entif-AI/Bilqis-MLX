"""C08 execution of source-bound Factory rows as scalar or true MLX microbatches."""
from __future__ import annotations

from dataclasses import replace
import time

import mlx.core as mx

from bilqis_mlx.b11_observation import attach_performance_observation
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.atlas_model import (
    bamf_microbatch_value_and_grad, bamf_value_and_grad, microbatch_compatible,
)
from bilqis_mlx.runtime.factory_task_authority import (
    _bind_validated_factory_task_compiled_batch, factory_task_authority,
    factory_task_training_goal,
)
from bilqis_mlx.runtime.factory_task_template import _source_view
from bilqis_mlx.runtime.task_goal_readout import (
    task_goal_route_plan, task_goal_training_targets,
)
from bilqis_mlx.source_adapters.task_goal_registry import (
    learning_first_task_goal_lowerer,
)
from bilqis_mlx.runtime.atlas_resources import validate_runtime_rank

from .c08_gradient_accumulation import (
    DistributedLogicalBatchMetadata, accumulate_logical_batch_gradients,
)
from .c08_distributed_gradient import (
    execute_distributed_rank, reduce_distributed_rank_gradients,
)
from .c08_distributed_coordinator import logical_batch_from_distributed_outcome
from .c08_distributed_outcome import (
    DistributedRuntimeAttestation, DistributedStepOutcome,
    all_gather_runtime_attestation,
)
from .c08_distributed_collective import all_reduce_fp32_rank_mean
from .c08_distributed_evidence import (
    all_gather_b11_evidence, evidence_training_extension,
)
from bilqis_mlx.runtime.atlas_training_authority import extend_training_dependencies
from bilqis_mlx.runtime.atlas_resources import partition_logical_batch


def _learning_first_task_goals(source_context, compiled):
    row = compiled.sources[0].source_row
    capability = source_context.release.execution_plan.capability_map.get(
        row.get("capability"))
    if capability is None:
        ErrorBus.raise_(
            SCHOOL.BAMF_TRAINING_ADAPTER.INVALID,
            reason="FACTORY_TRAINING_CAPABILITY_MISMATCH")
    lower, resolve = learning_first_task_goal_lowerer(capability.provider_id)
    kwargs = {
        "semantic_release": compiled.compiled.features.semantic_release,
        "source_root": source_context.source_root,
        "graph": source_context.graph,
        "release": source_context.release,
        "capability": capability,
    }
    goal, binding = lower(_source_view(row), **kwargs)
    return goal, resolve(row, goal, binding, **kwargs)


def _row_execution_inputs(
        source_context, compiled, feature_snapshot, generation,
        learning_first_cache=None, row_cache_key=None):
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    if not strict_evidence_enabled():
        row = compiled.sources[0].source_row
        cache_key = None
        if learning_first_cache is not None:
            cache_key = (
                learning_first_cache.key(row) if row_cache_key is None
                else row_cache_key)
        cached = (
            None if learning_first_cache is None
            else learning_first_cache.get_task_inputs(cache_key))
        if cached is None:
            goal, resolved = _learning_first_task_goals(source_context, compiled)
            targets, mask = task_goal_training_targets(goal, resolved)
            plan = task_goal_route_plan(
                goal, compiled, feature_snapshot, generation)
            if learning_first_cache is not None:
                learning_first_cache.put_task_inputs(
                    cache_key, (goal, resolved, targets, mask, plan))
        else:
            goal, resolved, targets, mask, plan = cached
            plan = replace(plan, generation_binding=generation)
        return compiled, None, targets, mask, plan
    authority = factory_task_authority(
        source_context, compiled, generation_binding=generation)
    bound = _bind_validated_factory_task_compiled_batch(compiled, authority)
    resolved = factory_task_training_goal(source_context, bound, authority)
    targets, mask = task_goal_training_targets(authority.goal, resolved)
    plan = task_goal_route_plan(
        authority.goal, bound, feature_snapshot, generation)
    return bound, authority, targets, mask, plan


def _mentor_multiplier(mentor_supervision, compiled):
    if mentor_supervision is None:
        return 1.0
    from bilqis_mlx.learning._championship.adviser_supervision import MentorSupervision
    if type(mentor_supervision) is not MentorSupervision:
        ErrorBus.raise_(
            SCHOOL.BAMF_TRAINING_ADAPTER.INVALID,
            reason="FACTORY_MENTOR_SUPERVISION_TYPE_INVALID")
    return 1.0 + mentor_supervision.influence_for(compiled)


def execute_factory_training_row(
        parameters, compiled, source_context, feature_snapshot, generation, cache, *,
        salience_supervision=None, mentor_supervision=None,
        learning_first_cache=None, row_cache_key=None):
    """Preserve the scalar B11 path as correctness oracle and fallback."""
    bound, authority, targets, mask, plan = _row_execution_inputs(
        source_context, compiled, feature_snapshot, generation,
        learning_first_cache=learning_first_cache, row_cache_key=row_cache_key)
    multiplier = _mentor_multiplier(mentor_supervision, compiled)
    gradient = bamf_value_and_grad(
        parameters, bound, plan, targets, mask, cache,
        salience_supervision=salience_supervision,
        source_loss_multiplier=multiplier)
    return gradient, authority, targets


def execute_factory_logical_batch(
        parameters, prepared, source_context, feature_snapshot, generation, cache,
        resource_plan, *, salience_supervision=None, mentor_supervision=None):
    """Execute each compatible C08 group with one MLX gradient launch."""
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    strict = strict_evidence_enabled()
    learning_first_cache = getattr(prepared, "learning_first_cache", None)
    task_hits_before = int(getattr(learning_first_cache, "task_hits", 0)) if strict else 0
    task_misses_before = int(getattr(learning_first_cache, "task_misses", 0)) if strict else 0
    row_inputs_started = time.perf_counter() if strict else None
    rows = tuple(_row_execution_inputs(
        source_context, compiled, feature_snapshot, generation,
        learning_first_cache=learning_first_cache,
        row_cache_key=(
            None if learning_first_cache is None else learning_first_cache.key(
                compiled.sources[0].source_row,
                prepared.training_batch.rows[index].model_input.eligibility_digest)))
        for index, compiled in enumerate(prepared.compiled_rows))
    row_execution_inputs_wall_seconds = (
        time.perf_counter() - row_inputs_started if strict else 0.0)
    bound = tuple(item[0] for item in rows)
    authorities = tuple(item[1] for item in rows)
    targets = tuple(item[2] for item in rows)
    masks = tuple(item[3] for item in rows)
    plans = tuple(item[4] for item in rows)

    def execute_row(index):
        multiplier = _mentor_multiplier(
            mentor_supervision, prepared.compiled_rows[index])
        return bamf_value_and_grad(
            parameters, bound[index], plans[index], targets[index], masks[index], cache,
            salience_supervision=salience_supervision,
            source_loss_multiplier=multiplier)

    def execute_group(group):
        if mentor_supervision is not None:
            # R05 row influence is source-row specific. Preserve the scalar B11
            # oracle until the microbatch kernel grows explicit per-row weights.
            return None
        group_rows = tuple(bound[index] for index in group)
        group_plans = tuple(plans[index] for index in group)
        group_targets = tuple(targets[index] for index in group)
        group_masks = tuple(masks[index] for index in group)
        if not microbatch_compatible(
                group_rows, group_plans, group_targets, group_masks):
            return None
        return bamf_microbatch_value_and_grad(
            parameters,
            group_rows,
            group_plans,
            group_targets,
            group_masks,
            cache,
            salience_supervision=salience_supervision)

    gradient = accumulate_logical_batch_gradients(
        resource_plan, execute_row, execute_group=execute_group)
    if strict:
        observation = dict(
            getattr(gradient, "_performance_observation", {}) or {})
        observation["c08_row_execution_inputs_wall_seconds"] = float(
            row_execution_inputs_wall_seconds)
        observation["learning_first_task_cache_hits"] = int(
            getattr(learning_first_cache, "task_hits", 0)) - task_hits_before
        observation["learning_first_task_cache_misses"] = int(
            getattr(learning_first_cache, "task_misses", 0)) - task_misses_before
        attach_performance_observation(gradient, observation)
    return gradient, authorities, targets


from .factory_candidate_distributed import (
    bind_factory_distributed_outcome, execute_factory_distributed_group,
    execute_factory_distributed_rank, execute_factory_distributed_rank_collective,
    execute_factory_distributed_rows_group,
)


__all__ = (
    "bind_factory_distributed_outcome", "execute_factory_distributed_rank",
    "execute_factory_distributed_group", "execute_factory_distributed_rank_collective",
    "execute_factory_distributed_rows_group",
    "execute_factory_logical_batch",
    "execute_factory_training_row",
)
