"""Source preparation and candidate-local reuse for Factory training."""
from __future__ import annotations

from bilqis_mlx.factory.teaching import DeliveredTeaching, content_digest
from bilqis_mlx.runtime.bamf_bundle import BamfBundleCandidate
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from .atlas_training_contracts import BamfVisitProvenance, _invalid
from .factory_training_source import (
    _prepare_factory_source_rows, _prepare_learning_first_model_sources,
)
from .learning_first_source import prepare_learning_first_source_rows
from .factory_training_preparation_cache import (
    LearningFirstPreparationCache, LearningFirstPreparedSourceInputs,
    _prepared_ahead_matches as _prepared_ahead_matches_impl,
    prepare_learning_first_source_inputs_ahead as _prepare_ahead_impl,
)


def prepare_learning_first_source_inputs_ahead(
        source_context, authenticated, rows, *, source_seed: int, source_each: int,
        source_identity: str | None = None):
    return _prepare_ahead_impl(
        source_context, authenticated, rows, source_seed=source_seed,
        source_each=source_each, source_identity=source_identity,
        content_digest_fn=content_digest)


def _prepared_ahead_matches(
        prepared, source_context, authenticated, rows, *, source_seed, source_each,
        source_identity=None):
    return _prepared_ahead_matches_impl(
        prepared, source_context, authenticated, rows, source_seed=source_seed,
        source_each=source_each, source_identity=source_identity,
        content_digest_fn=content_digest)

def _target_source_count(rows, rehearsal_by_id, fresh_support_by_id=None):
    return len(rows) - len(rehearsal_by_id) - len(fresh_support_by_id or {})


def _validated_training_request(
        source_context, candidate, delivered_rows, generation_binding, *,
        capability, delivery, requested_count, source_seed, source_each,
        optimizer_step_seed, visit_provenance, teacher_strategy,
        rehearsal_by_id=None, fresh_support_by_id=None):
    rows = tuple(delivered_rows) if isinstance(delivered_rows, (tuple, list)) else ()
    rehearsal_by_id = {} if rehearsal_by_id is None else dict(rehearsal_by_id)
    fresh_support_by_id = (
        {} if fresh_support_by_id is None else dict(fresh_support_by_id))
    target_source_count = _target_source_count(
        rows, rehearsal_by_id, fresh_support_by_id)
    if (set(rehearsal_by_id) & set(fresh_support_by_id)
            or any(value != "fresh_support" for value in fresh_support_by_id.values())):
        _invalid("FACTORY_TRAINING_FRESH_SUPPORT_ROLE_INVALID")
    if (type(source_context) is not SourceExecutionContext
            or not isinstance(candidate, BamfBundleCandidate)
            or not rows or any(type(row) is not dict for row in rows)
            or not isinstance(capability, str) or not capability
            or not isinstance(delivery, DeliveredTeaching)
            or type(requested_count) is not int or requested_count < len(rows)
            or type(source_seed) is not int or source_seed < 0
            or type(source_each) is not int or source_each != target_source_count
            or target_source_count < 1
            or type(optimizer_step_seed) is not int or optimizer_step_seed < 0
            or type(visit_provenance) is not BamfVisitProvenance
            or visit_provenance.capability_id != capability
            or not isinstance(teacher_strategy, dict)
            or not isinstance(generation_binding, str) or not generation_binding
            or source_context.source_root is None):
        _invalid("FACTORY_TRAINING_BRIDGE_INPUT_INVALID")
    return rows


def _learning_first_source_inputs(
        source_context, authenticated, rows, *, source_seed, source_each,
        learning_first_cache, prepared_ahead=None, prepared_source_identity=None):
    ahead_used = _prepared_ahead_matches(
        prepared_ahead, source_context, authenticated, rows,
        source_seed=source_seed, source_each=source_each,
        source_identity=prepared_source_identity)
    ahead_discarded = prepared_ahead is not None and not ahead_used
    if ahead_used:
        source_rows = prepared_ahead.source_rows
        prepared_model_sources = prepared_ahead.model_sources
        if learning_first_cache is not None:
            if type(learning_first_cache) is not LearningFirstPreparationCache:
                _invalid("LEARNING_FIRST_PREPARATION_CACHE_INVALID")
            learning_first_cache.bind(source_context, authenticated)
            for row, source_row, model_source in zip(
                    rows, source_rows, prepared_model_sources, strict=True):
                learning_first_cache.put(
                    row, source_row.projection.digest, model_source)
        return source_rows, prepared_model_sources, True, False
    source_rows = prepare_learning_first_source_rows(
        source_context, authenticated, rows,
        source_seed=source_seed, source_each=source_each)
    if learning_first_cache is None:
        return (source_rows, _prepare_learning_first_model_sources(
            authenticated, source_rows), False, ahead_discarded)
    if type(learning_first_cache) is not LearningFirstPreparationCache:
        _invalid("LEARNING_FIRST_PREPARATION_CACHE_INVALID")
    learning_first_cache.bind(source_context, authenticated)
    prepared_model_sources = []
    for row, source_row in zip(rows, source_rows, strict=True):
        eligibility_digest = source_row.projection.digest
        model_source = learning_first_cache.get(row, eligibility_digest)
        if model_source is None:
            model_source = _prepare_learning_first_model_sources(
                authenticated, (source_row,))[0]
            if model_source.eligibility_digest != eligibility_digest:
                _invalid("LEARNING_FIRST_PREPARATION_ELIGIBILITY_DRIFT")
            learning_first_cache.put(row, eligibility_digest, model_source)
        prepared_model_sources.append(model_source)
    return source_rows, tuple(prepared_model_sources), False, ahead_discarded


def _selected_delivery_authority(source_context, rows, authority, delivery,
                                 capability, source_seed):
    """Preserve the actual direct subset; revalidate only released enrichment."""
    if (authority.capability_id != capability or authority.seed != source_seed
            or authority.each > len(rows)
            or (delivery is not None and tuple(delivery.specimen_ids)
                != tuple(row["id"] for row in rows[:authority.each]))):
        _invalid("FACTORY_SELECTED_SOURCE_AUTHORITY_DRIFT")
    direct = rows[:authority.each]
    if len(direct) == len(rows):
        return source_context.require_bound_rows(direct, authority)
    if delivery is None:
        _invalid("FACTORY_SELECTED_SOURCE_AUTHORITY_DRIFT")
    from bilqis_mlx.factory.teaching import optional_teaching_rows
    enrichment = optional_teaching_rows(
        source_context.source_root, source_context.graph, source_context.release,
        source_context.source_registry, capability=capability, seed=source_seed,
        enabled=True)
    if rows[authority.each:] != enrichment:
        _invalid("FACTORY_SELECTED_SOURCE_ENRICHMENT_DRIFT")
    return source_context.bind_prequalified_delivery_rows(direct, rows, authority)


def _strict_source_inputs(
        source_context, authenticated, rows, *, capability, source_seed,
        source_each, delivery, rehearsal_by_id, rehearsal_bindings,
        rehearsal_authorities, selected_source_authority=None):
    target_rows = tuple(row for row in rows if row.get("id") not in rehearsal_by_id)
    if selected_source_authority is not None:
        source_authority = _selected_delivery_authority(
            source_context, target_rows, selected_source_authority, delivery,
            capability, source_seed)
    else:
        source_authority = (
            source_context.bind_rows(
                target_rows, seed=source_seed, capability=capability, each=source_each)
            if delivery is None or len(delivery.specimen_ids) == len(target_rows) else
            source_context.bind_delivery_rows(
                target_rows, seed=source_seed, capability=capability,
                direct_each=len(delivery.specimen_ids)))
    for identity, authority in rehearsal_authorities.items():
        row = next((item for item in rows if item.get("id") == identity), None)
        binding = rehearsal_bindings.get(identity)
        if (row is None or not isinstance(binding, dict)
                or authority.capability_id != binding.get("capability")
                or authority.seed != binding.get("seed")
                or authority.each != binding.get("each")):
            _invalid("FACTORY_REHEARSAL_SOURCE_AUTHORITY_INVALID")
        source_context.require_bound_rows((row,), authority)
    adapter, manifest, profile, source_rows = _prepare_factory_source_rows(
        source_context, authenticated, rows, capability=capability,
        source_seed=source_seed, source_each=source_each,
        source_authority=source_authority,
        source_authorities_by_id=rehearsal_authorities,
        source_bindings_by_id=rehearsal_bindings, issue_b11_proofs=True)
    from bilqis_mlx.runtime.priority_source_materialization import (
        _prepare_model_sources,
    )
    prepared_model_sources, _configs = _prepare_model_sources(
        source_context, authenticated, manifest, source_rows)
    return (
        source_authority, adapter, manifest, profile, source_rows,
        prepared_model_sources, None, None, None, False, False,
    )


def _prepared_source_inputs(
        prepared_source, source_context, authenticated, rows, *, capability,
        source_seed, source_each, delivery=None, rehearsal_by_id=None,
        rehearsal_bindings=None, rehearsal_authorities=None,
        selected_source_authority=None, learning_first_cache=None,
        prepared_learning_first_source_inputs=None,
        prepared_learning_first_source_identity=None):
    if prepared_source is None:
        rehearsal_by_id = rehearsal_by_id or {}
        rehearsal_bindings = rehearsal_bindings or {}
        rehearsal_authorities = rehearsal_authorities or {}
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_evidence_enabled,
        )
        if not strict_evidence_enabled():
            (source_rows, prepared_model_sources, ahead_used,
             ahead_discarded) = _learning_first_source_inputs(
                source_context, authenticated, rows,
                source_seed=source_seed, source_each=source_each,
                learning_first_cache=learning_first_cache,
                prepared_ahead=prepared_learning_first_source_inputs,
                prepared_source_identity=prepared_learning_first_source_identity)
            profile = source_rows[0].profile if len(source_rows) == 1 else None
            return (
                None, source_rows[0].source_adapter, None, profile, source_rows,
                prepared_model_sources, None, None, None,
                ahead_used, ahead_discarded,
            )
        return _strict_source_inputs(
            source_context, authenticated, rows, capability=capability,
            source_seed=source_seed, source_each=source_each, delivery=delivery,
            rehearsal_by_id=rehearsal_by_id,
            rehearsal_bindings=rehearsal_bindings,
            rehearsal_authorities=rehearsal_authorities,
            selected_source_authority=selected_source_authority)
    from bilqis_mlx.runtime.priority_source_materialization import (
        PreparedPrioritySourceMaterialization,
    )
    if (type(prepared_source) is not PreparedPrioritySourceMaterialization
            or prepared_source.semantic_context is not authenticated
            or prepared_source.offer.capability_id != capability
            or prepared_source.offer.source_seed != source_seed
            or prepared_source.offer.source_each != source_each
            or prepared_source.rows != rows):
        _invalid("FACTORY_TRAINING_PREPARED_SOURCE_INVALID")
    prepared_source.require_current()
    source_context.require_bound_rows(
        rows, prepared_source.offer.source_authority)
    return (
        prepared_source.offer.source_authority,
        prepared_source.adapter,
        prepared_source.manifest,
        prepared_source.profile,
        prepared_source.source_rows,
        prepared_source.model_sources,
        prepared_source.motif_inputs,
        prepared_source.b11_sources,
        prepared_source.packed_owner,
        False, False,
    )


__all__ = (
    "LearningFirstPreparationCache", "LearningFirstPreparedSourceInputs",
    "prepare_learning_first_source_inputs_ahead", "_prepared_source_inputs",
    "_validated_training_request",
)
