"""Source-owned B11 forward execution and participation capture."""
from __future__ import annotations

from bilqis_mlx.learning.atlas_engram_reads.source_owner import _B13_EXECUTION_SEAL
from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, DecoderMemory, DecisionKind, ExecutionMode, ModelOutput,
    ReadoutSemantics, predict_typed,
)
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
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

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


def _forward_participation(params, batch, plan, output, producer, accepted_cache):
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
    memory = DecoderMemory(
        row_hidden,
        tuple(item.cache_identity for item in row.positions),
        row,
        generation,
    )
    semantics = ReadoutSemantics(
        compiled_batch.compiled.features,
        _active_banks(params, compiled_batch, answer_plan),
        extents,
    )
    output = predict_typed(
        memory, projection, answer_plan, semantics, params)
    if type(output) is not ModelOutput or output.execution_mode is not mode:
        _invalid("B11_TYPED_OUTPUT_INVALID")
    return _FORWARD_ISSUANCE.issue(
        output, _forward_participation(
            params, compiled_batch, answer_plan, output, producer, accepted_cache))


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
