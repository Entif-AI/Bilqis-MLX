"""Join source-owned Factory delivery to C02 inputs and B11 row execution."""
from __future__ import annotations

from dataclasses import dataclass
import time

from bilqis_mlx.factory.teaching import DeliveredTeaching
from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch
from bilqis_mlx.runtime.bamf_bundle import (
    AuthenticatedCandidateFeatureContext, is_authenticated_generation_feature_context,
    BamfBundleCandidate,
    authenticate_bamf_execution_feature_context,
)
from bilqis_mlx.runtime.source_execution import SourceExecutionContext

from .atlas_training_contracts import BamfTrainingBatch, BamfVisitProvenance, _invalid
from .factory_training_compile import _compile_factory_training
from .factory_training_preparation import (
    LearningFirstPreparationCache,
    _prepared_source_inputs,
    _validated_training_request,
)
from .factory_training_source import (
    _FactoryMotifPlanningInput, _bind_b11_rows, _bind_learning_first_rows,
    _motif_planning_input, _prepare_b11_source_binding,
    _prepare_factory_source_rows,
)


@dataclass(frozen=True)
class PreparedFactoryTrainingBatch:
    """One source-owned C02 delivery plus exact row-scoped B11 inputs."""

    training_batch: BamfTrainingBatch
    compiled_rows: tuple[BamfCompiledBatch, ...]
    motif_inputs: tuple
    semantic_context: object
    learning_first_cache: object = None

    def __post_init__(self) -> None:
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_evidence_enabled,
        )
        strict = strict_evidence_enabled()
        if (not hasattr(self.training_batch, "rows")
                or type(self.compiled_rows) is not tuple
                or len(self.compiled_rows) != len(self.training_batch.rows)
                or type(self.motif_inputs) is not tuple
                or len(self.motif_inputs) != len(self.training_batch.rows)
                or not is_authenticated_generation_feature_context(
                    self.semantic_context)):
            _invalid("FACTORY_TRAINING_BRIDGE_INVALID")
        if strict and (
                type(self.training_batch) is not BamfTrainingBatch
                or any(type(item) is not _FactoryMotifPlanningInput
                       for item in self.motif_inputs)
                or any(type(item) is not BamfCompiledBatch
                       for item in self.compiled_rows)):
            _invalid("FACTORY_TRAINING_BRIDGE_INVALID")
        if strict:
            self.semantic_context.__post_init__()


def _authenticated_feature_context(
        source_context, candidate, atlas_artifact_path, semantic_context):
    authenticated = semantic_context
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    strict = strict_evidence_enabled()
    if authenticated is None:
        authenticated = authenticate_bamf_execution_feature_context(
            candidate, atlas_artifact_path, source_context.run_dir)
    elif not is_authenticated_generation_feature_context(authenticated):
        _invalid("FACTORY_TRAINING_SEMANTIC_CONTEXT_INVALID")
    if strict:
        authenticated.__post_init__()
    return authenticated, strict


def _bind_compiled_rows(
        strict, source_context, candidate, authenticated, training, source_rows,
        profile, source_seed, source_each, prepared_b11_sources, prepared_packed_owner):
    if strict:
        return _bind_b11_rows(
            source_context, candidate, authenticated, training, source_rows,
            profile, source_seed=source_seed, source_each=source_each,
            prepared_b11=prepared_b11_sources,
            packed_owner=prepared_packed_owner)
    return _bind_learning_first_rows(
        source_context, candidate, authenticated, training, source_rows,
        profile, source_seed=source_seed, source_each=source_each)


def _prepared_factory_result(
        training, compiled_rows, source_rows, authenticated, prepared_motif_inputs,
        source_context, *, request_validation_seconds, semantic_context_seconds,
        prepared_source_seconds, compile_seconds, b11_binding_seconds,
        learning_first_cache=None, source_cache_hits=0, source_cache_misses=0,
        ahead_preparation_used=False, ahead_preparation_discarded=False):
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    strict = strict_evidence_enabled()
    if strict:
        stage_started = time.perf_counter()
        motif_inputs = (
            prepared_motif_inputs if prepared_motif_inputs is not None else
            tuple(_motif_planning_input(
                source_context, authenticated, item.source_adapter, item.profile, item,
                source_seed=item.source_seed, source_each=item.source_each)
                for item in source_rows))
        motif_planning_seconds = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
    else:
        # Ordinary learning never stages retained motifs from this bridge.  Do
        # not manufacture motif-planning records solely for evidence/reporting.
        motif_inputs = (None,) * len(source_rows)
        motif_planning_seconds = 0.0
    prepared = PreparedFactoryTrainingBatch(
        training, compiled_rows, motif_inputs, authenticated, learning_first_cache)
    if strict:
        result_construction_seconds = time.perf_counter() - stage_started
        object.__setattr__(prepared, "_performance_observation", {
            "factory_request_validation_wall_seconds": float(request_validation_seconds),
            "factory_semantic_context_wall_seconds": float(semantic_context_seconds),
            "factory_prepared_source_validation_wall_seconds": float(prepared_source_seconds),
            "factory_training_compile_wall_seconds": float(compile_seconds),
            "factory_b11_binding_wall_seconds": float(b11_binding_seconds),
            "factory_motif_planning_wall_seconds": float(motif_planning_seconds),
            "factory_result_construction_wall_seconds": float(result_construction_seconds),
            "learning_first_source_cache_hits": int(source_cache_hits),
            "learning_first_source_cache_misses": int(source_cache_misses),
            "pipeline_prepared_ahead_used": int(bool(ahead_preparation_used)),
            "pipeline_discarded_prefetch_work": int(bool(ahead_preparation_discarded)),
        })
    return prepared


def _training_request_context(
        source_context, candidate, atlas_artifact_path, delivered_rows,
        generation_binding, *, capability, delivery, requested_count, source_seed,
        source_each, optimizer_step_seed, visit_provenance, teacher_strategy,
        rehearsal_by_id, fresh_support_by_id, semantic_context):
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    strict = strict_evidence_enabled()
    stage_started = time.perf_counter() if strict else None
    rows = _validated_training_request(
        source_context, candidate, delivered_rows, generation_binding,
        capability=capability, delivery=delivery, requested_count=requested_count,
        source_seed=source_seed, source_each=source_each,
        optimizer_step_seed=optimizer_step_seed,
        visit_provenance=visit_provenance, teacher_strategy=teacher_strategy,
        rehearsal_by_id=rehearsal_by_id,
        fresh_support_by_id=fresh_support_by_id)
    request_validation_seconds = (
        time.perf_counter() - stage_started if strict else 0.0)
    stage_started = time.perf_counter() if strict else None
    authenticated, strict_context = _authenticated_feature_context(
        source_context, candidate, atlas_artifact_path, semantic_context)
    if strict_context != strict:
        _invalid("FACTORY_TRAINING_EVIDENCE_MODE_DRIFT")
    semantic_context_seconds = (
        time.perf_counter() - stage_started if strict else 0.0)
    return (
        strict, rows, authenticated,
        request_validation_seconds, semantic_context_seconds)


def prepare_factory_training_batch(
    source_context: SourceExecutionContext, candidate: BamfBundleCandidate,
    atlas_artifact_path: str, feature_artifact_path: str,
    delivered_rows, generation_binding: str,
    *,
    capability: str, delivery: DeliveredTeaching, requested_count: int,
    source_seed: int, source_each: int,
    optimizer_step_seed: int = 0,
    visit_provenance: BamfVisitProvenance, teacher_strategy: dict,
    rehearsal_by_id: dict | None = None, rehearsal_bindings: dict | None = None,
    rehearsal_authorities: dict | None = None,
    fresh_support_by_id: dict | None = None,
    semantic_context=None, prepared_source=None, selected_source_authority=None,
    learning_first_cache=None, prepared_learning_first_source_inputs=None,
    prepared_learning_first_source_identity=None,
) -> PreparedFactoryTrainingBatch:
    """Compile one real Factory draw once, then bind each C02 row into B11.

    The bridge owns composition only. A05/A06/A13 remain source authority, B11
    remains the neural owner, and C16 remains the durable-student launch owner.
    """
    (strict, rows, authenticated, request_validation_seconds,
     semantic_context_seconds) = _training_request_context(
        source_context, candidate, atlas_artifact_path, delivered_rows,
        generation_binding, capability=capability, delivery=delivery,
        requested_count=requested_count, source_seed=source_seed,
        source_each=source_each, optimizer_step_seed=optimizer_step_seed,
        visit_provenance=visit_provenance, teacher_strategy=teacher_strategy,
        rehearsal_by_id=rehearsal_by_id, fresh_support_by_id=fresh_support_by_id,
        semantic_context=semantic_context)
    cache_hits_before = (
        int(getattr(learning_first_cache, "hits", 0)) if strict else 0)
    cache_misses_before = (
        int(getattr(learning_first_cache, "misses", 0)) if strict else 0)
    stage_started = time.perf_counter() if strict else None
    (source_authority, _adapter, manifest, profile, source_rows,
     prepared_model_sources, prepared_motif_inputs,
     prepared_b11_sources, prepared_packed_owner,
     ahead_preparation_used, ahead_preparation_discarded) = _prepared_source_inputs(
        prepared_source, source_context, authenticated, rows,
        capability=capability, source_seed=source_seed, source_each=source_each,
        delivery=delivery, rehearsal_by_id=rehearsal_by_id,
        rehearsal_bindings=rehearsal_bindings,
        rehearsal_authorities=rehearsal_authorities,
        selected_source_authority=selected_source_authority,
        learning_first_cache=learning_first_cache,
        prepared_learning_first_source_inputs=prepared_learning_first_source_inputs,
        prepared_learning_first_source_identity=prepared_learning_first_source_identity)
    prepared_source_seconds = (
        time.perf_counter() - stage_started if strict else 0.0)
    source_cache_hits = (
        int(getattr(learning_first_cache, "hits", 0)) - cache_hits_before
        if strict else 0)
    source_cache_misses = (
        int(getattr(learning_first_cache, "misses", 0)) - cache_misses_before
        if strict else 0)
    stage_started = time.perf_counter() if strict else None
    training = _compile_factory_training(
        rows, source_context, candidate, delivery, capability, teacher_strategy,
        requested_count, optimizer_step_seed, visit_provenance, source_authority,
        rehearsal_by_id, fresh_support_by_id, rehearsal_authorities, source_rows,
        feature_artifact_path, generation_binding,
        authenticated, manifest, prepared_model_sources)
    compile_seconds = time.perf_counter() - stage_started if strict else 0.0
    stage_started = time.perf_counter() if strict else None
    compiled_rows = _bind_compiled_rows(
        strict, source_context, candidate, authenticated, training, source_rows,
        profile, source_seed, source_each, prepared_b11_sources,
        prepared_packed_owner)
    b11_binding_seconds = time.perf_counter() - stage_started if strict else 0.0
    return _prepared_factory_result(
        training, compiled_rows, source_rows, authenticated, prepared_motif_inputs,
        source_context, request_validation_seconds=request_validation_seconds,
        semantic_context_seconds=semantic_context_seconds,
        prepared_source_seconds=prepared_source_seconds, compile_seconds=compile_seconds,
        b11_binding_seconds=b11_binding_seconds,
        learning_first_cache=learning_first_cache,
        source_cache_hits=source_cache_hits, source_cache_misses=source_cache_misses,
        ahead_preparation_used=ahead_preparation_used,
        ahead_preparation_discarded=ahead_preparation_discarded)


__all__ = (
    "LearningFirstPreparationCache", "PreparedFactoryTrainingBatch",
    "prepare_factory_training_batch",
)
