"""Source/context preparation owned by the Factory training bridge."""
from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from bilqis_mlx.factory.generation import runtime_adapter_for_release
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms import SourceAtomRow
from bilqis_mlx.runtime.atlas_model_contracts import (
    BamfCompiledBatch, bind_candidate_active_semantic_rows,
)
from bilqis_mlx.runtime.atlas_training_authority import bind_compiled_training_batch
from bilqis_mlx.runtime.b11_source_execution_authority import (
    _bind_prepared_b11_source_execution_authority, _issue_prepared_b11_source_proof,
)
from bilqis_mlx.semantics.frame_adapters.registry import source_frame_strategy
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.frame_compiler import (
    CompiledFrameBatch, CompiledFrameRows, FrameCompilerConfig, compile_prefix,
    validate_partial_visible_forest,
)
from bilqis_mlx.semantics.released_frame_schemas import (
    _load_pinned_released_frame_schemas_from_snapshot,
)
from bilqis_mlx.source_adapters.atoms.admission import authorize_public_formal_prefix
from bilqis_mlx.runtime.source_execution import SourceBatchAuthority
from .atlas_training_contracts import _invalid
from .factory_training_source_rows import (
    _FactoryMotifPlanningInput, _FactorySourceRow, _PreparedB11SourceBinding,
    _prepare_source_row, _prepared_b11_compiled_input,
)


def _motif_planning_input(source_context, authenticated, adapter, profile, item, *,
                          source_seed, source_each):
    result = _FactoryMotifPlanningInput(
        adapter, item.row, authenticated.selection,
        Path(source_context.source_root), item.source_graph,
        item.task, item.frontier, item.policy,
        source_seed, source_each, profile, source_context.release.curriculum,
        item.formal_projection, item.formal_frontier)
    result.__post_init__()
    return result


def _prepare_b11_source_binding(
        source_context, authenticated, profile, item, prefix, config, *,
        source_seed, source_each):
    if item.b11_proof is None:
        _invalid("FACTORY_TRAINING_PREPARED_B11_PROOF_REQUIRED")
    source = SourceAtomRow(
        authenticated.selection, item.row, item.source_graph,
        Path(source_context.source_root), source_seed, source_each,
        source_context.release.curriculum, profile)
    authority = _bind_prepared_b11_source_execution_authority(
        prefix, config, source, item.source_adapter, authenticated.snapshot,
        authenticated.features, item.b11_proof)
    prepared = _PreparedB11SourceBinding(prefix, config, source, authority)
    prepared.require_current()
    return prepared


def _bind_b11_rows(source_context, candidate, authenticated, training, source_rows,
                   profile, *, source_seed, source_each, prepared_b11=None,
                   packed_owner=None):
    compiled_rows = []
    if prepared_b11 is not None and (
            type(prepared_b11) is not tuple
            or len(prepared_b11) != len(source_rows)
            or any(type(item) is not _PreparedB11SourceBinding
                   for item in prepared_b11)):
        _invalid("FACTORY_TRAINING_PREPARED_B11_INVALID")
    active_semantic_rows = bind_candidate_active_semantic_rows(candidate, authenticated)
    for index, item in enumerate(source_rows):
        prefix = training.rows[index].model_input.prefix
        if prepared_b11 is None:
            approved_config = (item.config if item.projection is None
                               else replace(item.config, approved=item.projection))
            approved_config = authorize_public_formal_prefix(
                item.ast, prefix, approved_config)
            prepared = _prepare_b11_source_binding(
                source_context, authenticated, item.profile, item, prefix,
                approved_config, source_seed=item.source_seed,
                source_each=item.source_each)
        else:
            prepared = prepared_b11[index]
            if prepared.prefix is not prefix:
                _invalid("FACTORY_TRAINING_PREPARED_B11_PREFIX_DRIFT")
            # _prepared_source_inputs() immediately required the containing
            # PreparedPrioritySourceMaterialization in this same bridge call.
            # That owner check already required every prepared B11 binding,
            # including A13 rights/currentness. Repeating it here only
            # re-hashes the identical source/config before B11 binding; C02
            # binding and the launch epoch still verify exact source custody.
            approved_config = prepared.config
        if prepared_b11 is not None and packed_owner is not None:
            compiled = _prepared_b11_compiled_input(
                prepared, authenticated.features, candidate.extents, packed_owner,
                source_ast=(None if item.projection is None else item.ast))
        else:
            compiled_frame_rows = CompiledFrameRows(
                (prefix,), (prefix.positions,), ((True,) * len(prefix.positions),))
            if item.projection is None:
                compiled = CompiledEncoderInput(
                    compiled_frame_rows, (approved_config,), authenticated.features,
                    candidate.extents)
            else:
                receipt = validate_partial_visible_forest(prefix, item.ast, approved_config)
                compiled = CompiledEncoderInput(
                    compiled_frame_rows, (approved_config,), authenticated.features,
                    candidate.extents, source_asts=(item.ast,),
                    partial_forest_receipts=(receipt,))
        if (compiled.compiled.rows[0] is not prepared.prefix
                or compiled.compiler_configs[0] is not prepared.config):
            _invalid("FACTORY_TRAINING_PREPARED_B11_COMPILED_DRIFT")
        source = prepared.source
        source_execution_authority = prepared.authority
        batch = bind_compiled_training_batch(
            training, compiled, (source,), authenticated.schema,
            active_semantic_rows=active_semantic_rows, row_index=index,
            source_execution_authority=source_execution_authority)
        source_context.register_compiled_batch(batch)
        compiled_rows.append(batch)
    return tuple(compiled_rows)


def _prepare_learning_first_model_sources(authenticated, source_rows):
    """Build only the model inputs needed for learning.

    This deliberately skips the strict source inventory, lineage, semantic-authority,
    B11 proof and currentness ceremony. The already-selected source rows and the
    planning generation's authenticated feature context remain the inputs.
    """
    from bilqis_mlx.runtime.atlas_training_adapter import (
        PreparedModelSourceInput, _source_features as source_features,
    )
    prepared = []
    for item in source_rows:
        visible = tuple(item.row["tokens"])
        config = (item.config if item.projection is None
                  else replace(item.config, approved=item.projection))
        prefix = compile_prefix(
            item.ast, len(visible), item.task.semantic_release, config)
        features = (() if item.projection is None else
                    source_features(
                        item.projection, authenticated.features,
                        authenticated.selection))
        eligibility_digest = (
            item.projection.digest if item.projection is not None else
            contract_digest({
                "schema": "bilqis.mlx.c02-atomic-eligibility/v1",
                "task": asdict(item.task),
                "frontier": asdict(item.frontier),
                "policy": asdict(item.policy),
                "source_instance_id": item.ast.source_instance_id,
                "visible_end": len(visible),
            }))
        model = PreparedModelSourceInput(
            item.row["id"], visible, prefix, features, eligibility_digest)
        model.__post_init__()
        prepared.append(model)
    return tuple(prepared)


def _bind_learning_first_rows(
        source_context, candidate, authenticated, training, source_rows, profile, *,
        source_seed, source_each):
    """Bind neural rows without B11 source-execution or artifact-owner authority."""
    active_semantic_rows = bind_candidate_active_semantic_rows(candidate, authenticated)
    compiled_rows = []
    for index, item in enumerate(source_rows):
        prefix = training.rows[index].model_input.prefix
        config = (item.config if item.projection is None
                  else replace(item.config, approved=item.projection))
        rows = CompiledFrameRows(
            (prefix,), (prefix.positions,), ((True,) * len(prefix.positions),))
        if item.projection is None:
            compiled = CompiledEncoderInput(
                rows, (config,), authenticated.features, candidate.extents)
        else:
            receipt = validate_partial_visible_forest(prefix, item.ast, config)
            compiled = CompiledEncoderInput(
                rows, (config,), authenticated.features, candidate.extents,
                source_asts=(item.ast,), partial_forest_receipts=(receipt,))
        source = SourceAtomRow(
            authenticated.selection, item.row, item.source_graph,
            Path(source_context.source_root),
            item.source_seed, item.source_each,
            source_context.release.curriculum, profile)
        batch = BamfCompiledBatch(
            compiled, (source,), authenticated.schema, active_semantic_rows)
        batch.__post_init__()
        compiled_rows.append(batch)
    return tuple(compiled_rows)


def _prepare_factory_source_rows(source_context, authenticated, rows, *, capability,
                                 source_seed, source_each, source_authority=None,
                                 source_authorities_by_id=None,
                                 source_bindings_by_id=None,
                                 issue_b11_proofs=True):
    """Prepare the same source-owned AST and eligibility inputs for C02 or an offer."""
    execution = source_context.release.execution_plan.capability_map[capability]
    adapter = runtime_adapter_for_release(
        source_context.source_root, source_context.graph, source_context.release,
        source_context.source_registry, execution)
    strategy = source_frame_strategy(adapter.descriptor.adapter_id)
    manifest = (None if strategy.source_family is None else
                _load_pinned_released_frame_schemas_from_snapshot(
                    strategy.source_family, authenticated.selection,
                    authenticated.snapshot).manifest)
    profile = (dict(execution.provider_parameters)
               if execution.provider_parameters else None)
    source_authorities_by_id = source_authorities_by_id or {}
    source_bindings_by_id = source_bindings_by_id or {}
    target_rows = tuple(
        row for row in rows if row.get("id") not in source_authorities_by_id)
    prequalified = source_authority is not None or bool(source_authorities_by_id)
    if source_authority is not None:
        if (type(source_authority) is not SourceBatchAuthority
                or source_authority.capability_id != capability
                or source_authority.seed != source_seed
                or source_authority.each != source_each
                or source_authority.provider_id != adapter.descriptor.adapter_id):
            _invalid("FACTORY_TRAINING_SOURCE_AUTHORITY_INVALID")
        source_context.require_bound_rows(target_rows, source_authority)
    source_rows = []
    for row in rows:
        row_capability = row.get("capability")
        row_execution = source_context.release.execution_plan.capability_map.get(row_capability)
        if row_execution is None:
            _invalid("FACTORY_TRAINING_CAPABILITY_MISMATCH")
        row_adapter = runtime_adapter_for_release(
            source_context.source_root, source_context.graph, source_context.release,
            source_context.source_registry, row_execution)
        row_strategy = source_frame_strategy(row_adapter.descriptor.adapter_id)
        row_manifest = (None if row_strategy.source_family is None else
                        _load_pinned_released_frame_schemas_from_snapshot(
                            row_strategy.source_family, authenticated.selection,
                            authenticated.snapshot).manifest)
        row_profile = (dict(row_execution.provider_parameters)
                       if row_execution.provider_parameters else None)
        row_binding = source_bindings_by_id.get(row.get("id"), {})
        row_seed = row_binding.get("seed", source_seed)
        row_each = row_binding.get("each", source_each)
        rehearsal_authority = source_authorities_by_id.get(row.get("id"))
        row_authority = rehearsal_authority or source_authority
        if rehearsal_authority is not None:
            source_context.require_bound_rows((row,), row_authority)
        source_rows.append(_prepare_source_row(
            source_context, authenticated, row_manifest, row_profile, row,
            capability=row_capability, source_seed=row_seed, source_each=row_each,
            prequalified=row_authority is not None))
    source_rows = tuple(source_rows)
    if prequalified and issue_b11_proofs:
        source_rows = tuple(replace(
            item,
            b11_proof=_issue_prepared_b11_source_proof(
                source_context,
                ((item.row,) if item.row["id"] in source_authorities_by_id else target_rows),
                source_authorities_by_id.get(item.row["id"], source_authority), item.row,
                item.source_witness, item.formal_projection,
                item.formal_frontier)) for item in source_rows)
    return adapter, manifest, profile, source_rows
