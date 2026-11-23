"""Candidate neural execution and optimizer admission."""
from __future__ import annotations

from pathlib import Path
import time

from bilqis_mlx.runtime.bamf_bundle import is_authenticated_generation_feature_context
from bilqis_mlx.runtime.bamf_bundle.admission import (
    admit_uninterrupted_candidate_step, derive_participation_inputs,
)
from bilqis_mlx.runtime.atlas_resources import (
    DistributedExecutionProfile, persist_distributed_manifest,
)
from bilqis_mlx.runtime.factory_candidate_cost import realized_candidate_cost
from bilqis_mlx.runtime.factory_candidate_microbatch import (
    bind_factory_distributed_outcome, execute_factory_logical_batch,
    execute_factory_training_row,
)
from bilqis_mlx.runtime.c08_distributed_manifest import issue_distributed_step_manifest
from bilqis_mlx.runtime.c08_distributed_outcome import DistributedStepOutcome
from bilqis_mlx.runtime.c08_distributed_executor import DistributedExecutorBinding

from ..factory_candidate_components import _invalid


def _learning_first_admit(parent, cache, candidate, gradient, teacher_hparams,
                          max_norm, prepared):
    from bilqis_mlx.learning._atlas_candidate.step import (
        learning_first_candidate_step,
    )
    from bilqis_mlx.learning._atlas_candidate.transaction import (
        _begin_learning_first_candidate,
    )
    if candidate is None:
        parent_identity = getattr(cache, "_candidate_identity_sha256", None)
        candidate = _begin_learning_first_candidate(
            parent.retained_state, parent_identity)
    elif not getattr(candidate, "learning_first", False):
        _invalid("FACTORY_LEARNING_FIRST_CANDIDATE_REQUIRED")
    group_eligible, _active_admitted = derive_participation_inputs(parent)
    loss_executions = (
        (gradient.execution,)
        if hasattr(gradient, "execution")
        else tuple(gradient.loss_executions)
    )
    from bilqis_mlx.runtime.atlas_training_contracts import BamfLearningRowMetadata
    capability = prepared.training_batch.delivery_capability
    coordinates = []
    for row in prepared.training_batch.rows:
        metadata = row.provenance
        if (type(metadata) is not BamfLearningRowMetadata
                or not isinstance(metadata.source_family_id, str)
                or not metadata.source_family_id
                or not isinstance(metadata.episode_id, str)
                or not metadata.episode_id):
            _invalid("FACTORY_LEARNING_FIRST_SOURCE_COORDINATES_REQUIRED")
        coordinates.append((capability, metadata.source_family_id, metadata.episode_id))
    return learning_first_candidate_step(
        candidate, gradient.gradients, loss_executions, group_eligible,
        teacher_hparams, training_source_coordinates=tuple(sorted(set(coordinates))),
        spec=parent.topology, extents=parent.extents,
        max_norm=max_norm)


def _realized_candidate_cost(*args, **kwargs):
    """Compatibility seam for the reporting contract after structural extraction."""
    return realized_candidate_cost(*args, **kwargs, invalid=_invalid)


def _prepared_feature_context(prepared, semantic_context):
    feature_context = prepared.semantic_context if semantic_context is None else semantic_context
    if not is_authenticated_generation_feature_context(feature_context):
        _invalid("FACTORY_CANDIDATE_SEMANTIC_CONTEXT_INVALID")
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    if strict_evidence_enabled():
        feature_context.__post_init__()
    return feature_context


def _candidate_parameters(parent, candidate):
    optimizer = parent.retained_state.optimizer if candidate is None else candidate.optimizer
    return optimizer.parameters


def _execute_distributed_batch(
        run_dir, source_context, parent, prepared, feature_context, generation, parameters,
        neural_cache, resource_plan, salience_supervision, mentor_supervision,
        distributed_profile, distributed_executor):
    if (type(distributed_profile) is not DistributedExecutionProfile
            or type(distributed_executor) is not DistributedExecutorBinding
            or distributed_executor.profile != distributed_profile):
        _invalid("FACTORY_DISTRIBUTED_CONFIGURATION_INVALID")
    distributed_started = time.perf_counter()
    manifest = issue_distributed_step_manifest(
        parent, prepared.training_batch, resource_plan, distributed_profile)
    persist_distributed_manifest(Path(run_dir), manifest)
    outcome = distributed_executor.execute(
        parameters=parameters, prepared=prepared,
        source_context=source_context, feature_snapshot=feature_context.snapshot,
        generation=generation, cache=neural_cache, resource_plan=resource_plan,
        manifest=manifest, salience_supervision=salience_supervision,
        mentor_supervision=mentor_supervision)
    if type(outcome) is not DistributedStepOutcome:
        _invalid("FACTORY_DISTRIBUTED_OUTCOME_REQUIRED")
    gradient, authorities, target_rows = bind_factory_distributed_outcome(
        prepared, source_context, feature_context.snapshot, generation,
        resource_plan, manifest, outcome)
    return (gradient, authorities, target_rows,
            time.perf_counter() - distributed_started)


def _execute_training_and_admission(
        run_dir, source_context, parent, prepared, feature_context, generation, cache, resource_plan,
        teacher_hparams, max_norm, candidate, currentness_transaction,
        salience_supervision, mentor_supervision, distributed_profile, distributed_executor):
    parameters = _candidate_parameters(parent, candidate)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import strict_evidence_enabled
    strict = strict_evidence_enabled()
    neural_cache = cache if strict or distributed_profile is not None else None
    if len(prepared.compiled_rows) == 1:
        gradient, authority, targets = execute_factory_training_row(
            parameters, prepared.compiled_rows[0], source_context,
            feature_context.snapshot, generation, neural_cache,
            salience_supervision=salience_supervision,
            mentor_supervision=mentor_supervision,
            learning_first_cache=getattr(prepared, "learning_first_cache", None),
            row_cache_key=(
                None if getattr(prepared, "learning_first_cache", None) is None else
                prepared.learning_first_cache.key(
                    prepared.compiled_rows[0].sources[0].source_row,
                    prepared.training_batch.rows[0].model_input.eligibility_digest)))
        authorities, target_rows = (authority,), (targets,)
        optimizer_started = time.perf_counter() if strict else None
        transaction = (
            admit_uninterrupted_candidate_step(
                Path(run_dir), parent, loss_bearing_target=True,
                gradient_execution=gradient, teacher_hparams=teacher_hparams,
                max_norm=max_norm, candidate=candidate, execution_cache=cache,
                currentness_transaction=currentness_transaction)
            if strict else
            _learning_first_admit(
                parent, cache, candidate, gradient, teacher_hparams, max_norm,
                prepared)
        )
        loss_total = gradient.loss_total
        c08_metrics = (1, 0, 1, 0, None)
    else:
        if (distributed_profile is None) != (distributed_executor is None):
            _invalid("FACTORY_DISTRIBUTED_CONFIGURATION_INCOMPLETE")
        if distributed_profile is None:
            gradient, authorities, target_rows = execute_factory_logical_batch(
                parameters, prepared, source_context, feature_context.snapshot,
                generation, neural_cache, resource_plan,
                salience_supervision=salience_supervision,
                mentor_supervision=mentor_supervision)
            logical_batch_wall_seconds = gradient.wall_seconds if strict else 0.0
        else:
            gradient, authorities, target_rows, logical_batch_wall_seconds = (
                _execute_distributed_batch(
                    run_dir, source_context, parent, prepared, feature_context,
                    generation, parameters, neural_cache, resource_plan, salience_supervision,
                    mentor_supervision, distributed_profile, distributed_executor))
        optimizer_started = time.perf_counter() if strict else None
        transaction = (
            admit_uninterrupted_candidate_step(
                Path(run_dir), parent, loss_bearing_target=True,
                logical_batch_execution=gradient,
                training_batch=prepared.training_batch,
                logical_batch_plan=resource_plan,
                teacher_hparams=teacher_hparams, max_norm=max_norm,
                candidate=candidate, execution_cache=cache,
                currentness_transaction=currentness_transaction)
            if strict or distributed_profile is not None else
            _learning_first_admit(
                parent, cache, candidate, gradient, teacher_hparams, max_norm,
                prepared)
        )
        loss_total = gradient.weighted_mean_loss
        c08_metrics = (gradient.gradient_launches, gradient.vectorized_microbatches,
                       gradient.materialization_barriers, gradient.scalar_fallback_rows,
                       logical_batch_wall_seconds)
    return (gradient, authorities, target_rows, transaction, loss_total, c08_metrics,
            time.perf_counter() - optimizer_started if strict else 0.0)
