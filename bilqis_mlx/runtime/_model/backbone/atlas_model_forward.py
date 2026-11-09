"""Source-owned B11 forward execution and participation capture."""
from __future__ import annotations

from dataclasses import replace

import mlx.core as mx

from bilqis_mlx.learning.atlas_engram_reads.source_owner import _B13_EXECUTION_SEAL
from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, DecoderMemory, DecisionKind, ExecutionMode, ModelOutput,
    ReadoutSemantics, predict_typed,
)
from bilqis_mlx.learning.atlas_readout.decoder.feedback import role_id_vector
from bilqis_mlx.learning.frame_embeddings.banks import SemanticBankView
from bilqis_mlx.learning.source_atoms.backbone import (
    finalize_source_backbone_hidden,
    start_retained_source_backbone_producer,
    start_source_backbone_producer,
)
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
    bind_motif_artifact_owner, require_accepted_execution_cache,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    ModelTopologySpecV2, expected_bamf_shapes, validate_bamf_parameters,
)
from bilqis_mlx.runtime.atlas_training_authority import extend_training_dependencies
from bilqis_mlx.runtime.atlas_refinement import (
    _refine_frame, refinement_parameter_view,
)
from bilqis_mlx.runtime.refinement_policy import select_prediction_refinements
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextHold,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.frame_compiler import PositionKind

from .atlas_model_backend import Backend, model_backend
from .atlas_model_contracts import (
    BamfCompiledBatch, _FORWARD_ISSUANCE, _ForwardRecord, _invalid,
)


def _active_banks(parameters, batch: BamfCompiledBatch, plan: AnswerPlan):
    source = batch.sources[0]
    snapshot = load_pinned_atlas_snapshot(source.selection)
    if (
        snapshot != plan.snapshot
        or snapshot.release_sha256 != batch.compiled.features.semantic_release
        or snapshot.active_set_sha256
        != batch.compiled.extents.active_semantic_digest
    ):
        _invalid("B11_SEMANTIC_SNAPSHOT_MISMATCH")
    rows = [[] for _ in range(batch.compiled.extents.semantic_bank_count)]
    for entry in snapshot.abi_entries:
        if entry.active:
            if not 0 <= entry.bank < len(rows):
                _invalid("B11_ACTIVE_BANK_OUT_OF_RANGE")
            rows[entry.bank].append(entry.row)
    banks = []
    for bank_index, active_rows in enumerate(rows):
        name = f"identity.bank.{bank_index}"
        banks.append(SemanticBankView(
            bank_index,
            parameters.get(name),
            tuple(sorted(active_rows)),
            snapshot.release_sha256,
            snapshot.active_set_sha256,
        ))
    return tuple(banks)


def _executed_readout_parameters(plan, output):
    """Return only readout tensors whose decoder branches actually executed."""
    dense = {
        "readout.state_norm", "readout.output_norm", "readout.query",
        "readout.key", "readout.value", "readout.output",
    }
    executed_ids = {decision.decision_id for decision in output.decisions}
    kinds = {decision.kind for decision in output.decisions}
    if DecisionKind.CONTROL in kinds:
        dense.update(("readout.control", "readout.control_bias"))
    if DecisionKind.ROLE in kinds:
        dense.add("readout.role_query")
    if DecisionKind.EPISTEMIC in kinds:
        dense.update(("readout.epistemic", "readout.epistemic_bias"))
    if any(
        decision.decision_id in executed_ids and decision.depends_on
        for decision in plan.decisions
    ):
        dense.add("readout.feedback")
    return dense


def _execution_dependencies(batch, producer, accepted_cache):
    """Capture source-owned correction premises that actually fed this B11 step.

    Capability support owns its own dependency index, so it must not retain a
    dangling ARTIFACT ref to a foreign owner.  Instead it freezes the concrete
    source/release/operator/policy/rights/time premises of each consumed
    physical artifact.  A correction to any such premise can then reach both
    the physical owner and the learned support directly.
    """
    dependencies = set()
    feature = batch.atlas_feature_artifact_owner.current_node
    dependencies.update(
        ref for ref in feature.immediate_dependencies
        if ref.kind is not DependencyKind.ARTIFACT)
    row = batch.compiled.compiled.rows[0]
    for node in batch.compiled.packed_frame_artifact_owner.require_row(row):
        dependencies.update(
            ref for ref in node.immediate_dependencies
            if ref.kind is not DependencyKind.ARTIFACT)
    motif = producer._motif_read
    if (accepted_cache is not None and motif is not None
            and motif.participating_slots):
        owner = bind_motif_artifact_owner(accepted_cache, batch.compiled)
        node = owner.current_node
        dependencies.update(
            ref for ref in node.immediate_dependencies
            if ref.kind is not DependencyKind.ARTIFACT)
        dependencies.update(owner.source_dependencies)
    return tuple(sorted(dependencies))


def _forward_participation(
    params, batch, plan, output, producer, accepted_cache,
    refinement_roles=(), refinement_executed=False,
):
    source = batch.sources[0]
    snapshot = load_pinned_atlas_snapshot(source.selection)
    row = batch.compiled.compiled.rows[0]
    visible = []
    feature_rows = set()
    for abi_index in tuple(source.source_row.get("tokens", ()))[:row.visible_end]:
        entry = snapshot.abi(abi_index)
        visible.append((entry.bank, entry.row))
        factors = batch.compiled.features.features_for(
            entry.semantic_id, "NONE", "NONE",
            batch.compiled.compiler_configs[0].task.scope,
        )
        feature_rows.update(("type", item) for item in factors.type_rows)
        feature_rows.add(("role", factors.role_row))
        feature_rows.add(("schema", factors.schema_row))
    feature_rows.add(("role", dict(batch.compiled.features.role_map)["NONE"]))

    dense = {
        item.name for item in expected_bamf_shapes(
            ModelTopologySpecV2(), batch.compiled.extents)
        if item.name.startswith(("blocks.", "depth.", "plastic.group."))
    }
    dense.update((
        "features.gates", "features.project_type", "features.project_role",
        "features.project_schema", "features.project_graph", "features.norm",
    ))
    dense.update(_executed_readout_parameters(plan, output))
    if refinement_roles:
        feature_rows.update(
            ("role", dict(batch.compiled.features.role_map)[role])
            for role in refinement_roles
        )
    if refinement_executed:
        dense.update(
            item.name for item in expected_bamf_shapes(
                ModelTopologySpecV2(), batch.compiled.extents)
            if item.name.startswith("refine.")
            and item.name not in ("refine.route", "refine.route_bias")
        )
    if not dense <= set(params):
        _invalid("B11_EXECUTED_PARAMETER_CENSUS_MISMATCH")
    return _ForwardRecord(
        plan.generation_binding,
        None if accepted_cache is None else accepted_cache.run_id,
        None if accepted_cache is None else accepted_cache.generation,
        None if accepted_cache is None else accepted_cache.accepted_manifest_sha256,
        tuple(sorted(set(visible))),
        tuple(sorted(feature_rows)),
        (0,),
        tuple(sorted(dense)),
        (() if producer._motif_read is None else (producer._motif_read,)),
        batch.compiled.features.role_map,
        (None if batch.training_authority is None else extend_training_dependencies(
            batch.training_authority,
            _execution_dependencies(batch, producer, accepted_cache))),
    )


def _refinement_role_vector(request, semantics, params):
    """Project only an already-defined single requested role into B06 width.

    B10 can legitimately report multiple requested roles, but no reviewed owner
    defines a tuple-to-one-vector pooling rule.  B11 therefore consumes the
    existing canonical NONE/single-role projection and fails closed rather than
    inventing mean/sum/priority semantics.
    """
    roles = request.requested_roles
    if len(roles) > 1:
        _invalid("B11_REFINEMENT_MULTI_ROLE_UNRESOLVED")
    identifier = roles[0] if roles else "NONE"
    return role_id_vector(identifier, semantics, params), (identifier,)


def _selected_frame_index(row, encoded, config, choice):
    matches = tuple(
        (index, position) for index, position in enumerate(row.positions)
        if position.kind is PositionKind.CLOSURE
        and position.frame_handle == choice.frame_handle
    )
    if len(matches) != 1:
        _invalid("B11_REFINEMENT_FRAME_BINDING_INVALID")
    index, position = matches[0]
    position.__post_init__()
    if (
        position.packed is None
        or position.packed.sidecar.occurrence_id != choice.occurrence_id
        or encoded.handles[0][index] != position
        or config.approved is None
    ):
        _invalid("B11_REFINEMENT_FRAME_BINDING_INVALID")
    envelope = next(
        (item for item in config.approved.envelopes
         if item.frame_handle == choice.frame_handle),
        None,
    )
    if (
        envelope is None
        or envelope.frame.occurrence_id != choice.occurrence_id
        or encoded.global_seeds[0, index].shape != (ModelTopologySpecV2.width,)
        or encoded.members[0][index].ndim != 2
        or encoded.members[0][index].shape[1] != ModelTopologySpecV2.width
        or encoded.members[0][index].shape[0] != len(envelope.members)
    ):
        _invalid("B11_REFINEMENT_FRAME_BINDING_INVALID")
    return index


def _prediction_local_refinement(
    params, compiled_batch, answer_plan, generation, producer, row_hidden, semantics,
):
    request = answer_plan.refinement_request
    if request is None:
        return row_hidden, (), False
    row = compiled_batch.compiled.compiled.rows[0]
    if not any(position.kind is PositionKind.CLOSURE for position in row.positions):
        return row_hidden, (), False
    compiled = compiled_batch.compiled
    config = compiled.compiler_configs[0]
    source_asts = compiled.source_asts
    if (
        source_asts is None
        or len(source_asts) != 1
        or config.approved is None
        or producer._encoded.compiled != compiled.compiled
    ):
        _invalid("B11_REFINEMENT_SOURCE_CUSTODY_REQUIRED")
    task = replace(config.task, causal_prefix_end=row.visible_end)
    visit = compiled_batch.visit_provenance
    training = visit is not None
    selection = select_prediction_refinements(
        frames=config.approved.envelopes,
        source_ast=source_asts[0],
        compiler_config=config,
        task_scope=task,
        source_frontier=config.frontier,
        policy=config.policy,
        input_generation=generation,
        query_id=compiled_batch.sources[0].source_row["id"],
        requested_roles=request.requested_roles,
        run_seed=None if visit is None else visit.run_seed,
        visit_id=None if visit is None else visit.visit_id,
        training=training,
        explicit_member_question=request.explicit_member_question,
        unresolved_nested_query=request.unresolved_nested_query,
    )
    if isinstance(selection, ContextHold):
        _invalid("B11_REFINEMENT_CONTEXT_HELD")
    if not selection.selected:
        return row_hidden, (), False
    role, roles = _refinement_role_vector(request, semantics, params)
    parameters = refinement_parameter_view(
        params, spec=ModelTopologySpecV2(), extents=compiled.extents)
    values = [row_hidden[index] for index in range(row_hidden.shape[0])]
    executed = False
    for choice in selection.selected:
        index = _selected_frame_index(row, producer._encoded, config, choice)
        if choice.passes == 0:
            continue
        members = producer._encoded.members[0][index]
        if members.shape[0] == 0:
            _invalid("B11_REFINEMENT_MEMBER_INPUT_REQUIRED")
        result = _refine_frame(
            values[index], producer._encoded.global_seeds[0, index],
            members, role, choice.passes, parameters)
        values[index] = result.hidden
        executed = True
    return (mx.stack(tuple(values)) if executed else row_hidden), roles, executed


def _source_producer(params, compiled_batch, generation, cache):
    if cache is None:
        return start_source_backbone_producer(
            compiled_batch.compiled,
            params,
            compiled_batch.sources,
            compiled_batch.feature_schema,
            compiled_batch.atlas_feature_artifact_owner,
        ), None
    accepted_cache = require_accepted_execution_cache(cache)
    if (
        accepted_cache.generation_binding != generation
        or accepted_cache.motif_manifest.digest
        != compiled_batch.compiled.extents.motif_key_map_digest
    ):
        _invalid("B11_ACCEPTED_CACHE_GENERATION_MISMATCH")
    if not accepted_cache.motif_manifest.slots:
        return start_source_backbone_producer(
            compiled_batch.compiled,
            params,
            compiled_batch.sources,
            compiled_batch.feature_schema,
            compiled_batch.atlas_feature_artifact_owner,
        ), accepted_cache
    bind_motif_artifact_owner(accepted_cache, compiled_batch.compiled)
    return start_retained_source_backbone_producer(
        compiled_batch.compiled,
        params,
        compiled_batch.sources,
        compiled_batch.feature_schema,
        accepted_cache.motif_manifest,
        compiled_batch.atlas_feature_artifact_owner,
        seal=_B13_EXECUTION_SEAL,
    ), accepted_cache


def _forward_bamf_impl(
    backend: Backend,
    params,
    compiled_batch: BamfCompiledBatch,
    answer_plan: AnswerPlan,
    mode: ExecutionMode,
    cache,
) -> ModelOutput:
    """Run the source-backed BAMF forward and typed decoder once."""
    if (
        type(compiled_batch) is not BamfCompiledBatch
        or type(answer_plan) is not AnswerPlan
        or mode is not ExecutionMode.INFERENCE
    ):
        _invalid("B11_FORWARD_INPUT_INVALID")
    compiled_batch.__post_init__()
    answer_plan.__post_init__()
    backend.__post_init__()
    spec = backend.topology
    extents = compiled_batch.compiled.extents
    validate_bamf_parameters(spec, extents, params)
    generation = execution_generation_digest(
        params, spec=spec, extents=extents)
    if answer_plan.generation_binding != generation:
        _invalid("B11_GENERATION_BINDING_MISMATCH")
    if (compiled_batch.training_authority is not None
            and compiled_batch.training_authority.generation_binding != generation):
        _invalid("B11_TRAINING_AUTHORITY_GENERATION_MISMATCH")

    producer, accepted_cache = _source_producer(
        params, compiled_batch, generation, cache)
    hidden = finalize_source_backbone_hidden(producer)
    if hidden.shape[0] != 1:
        _invalid("B11_SINGLE_ROW_FORWARD_REQUIRED")
    row = compiled_batch.compiled.compiled.rows[0]
    projection = compiled_batch.compiled._projections[0]
    if (
        projection is not None
        and type(projection) is not ApprovedContextProjection
    ):
        _invalid("B11_APPROVED_CONTEXT_REQUIRED")
    row_hidden = hidden[0]
    if row_hidden.shape[0] != len(row.positions):
        _invalid("B11_HIDDEN_POSITION_MISMATCH")
    semantics = ReadoutSemantics(
        compiled_batch.compiled.features,
        _active_banks(params, compiled_batch, answer_plan),
        extents,
    )
    row_hidden, refinement_roles, refinement_executed = _prediction_local_refinement(
        params, compiled_batch, answer_plan, generation, producer, row_hidden, semantics)
    memory = DecoderMemory(
        row_hidden,
        tuple(item.cache_identity for item in row.positions),
        row,
        generation,
    )
    output = predict_typed(
        memory, projection, answer_plan, semantics, params)
    if type(output) is not ModelOutput or output.execution_mode is not mode:
        _invalid("B11_TYPED_OUTPUT_INVALID")
    return _FORWARD_ISSUANCE.issue(
        output, _forward_participation(
            params, compiled_batch, answer_plan, output, producer, accepted_cache,
            refinement_roles, refinement_executed))


def forward_bamf(
    params,
    compiled_batch: BamfCompiledBatch,
    answer_plan: AnswerPlan,
    mode: ExecutionMode,
    cache,
) -> ModelOutput:
    """Public inference entrypoint through the single BAMF backend selector."""
    return model_backend(ModelTopologySpecV2()).forward(
        params, compiled_batch, answer_plan, mode, cache)


__all__ = ("forward_bamf",)
