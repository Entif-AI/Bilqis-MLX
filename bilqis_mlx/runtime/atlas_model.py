"""Single B11 source-backed BAMF forward dispatch.

This owner composes the already-qualified A05/B01/B03/B05/B10 surfaces.  It
accepts no caller-authored hidden state, execution names, row participation,
motif-read facts, or update masks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
from weakref import WeakValueDictionary, finalize
import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, DecoderMemory, DecisionKind, DecisionOutput, ExecutionMode,
    LossParts, ModelOutput, ReadoutSemantics, answer_loss, predict_typed,
)
from bilqis_mlx.learning.frame_embeddings.banks import SemanticBankView
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms.backbone import (
    finalize_source_backbone_hidden,
    start_source_backbone_producer,
)
from bilqis_mlx.learning.source_atoms.inputs import SourceAtomRow
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.model_topology_v2 import (
    ModelTopologySpecV2, expected_bamf_shapes, validate_bamf_parameters,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.semantics.atlas_snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


@dataclass(frozen=True)
class _ForwardRecord:
    generation_binding: str
    visible_identity_rows: tuple[tuple[int, int], ...]
    feature_rows: tuple[tuple[str, int], ...]
    local_slot_rows: tuple[int, ...]
    dense_parameter_names: tuple[str, ...]


class _ForwardRegistry:
    def __init__(self):
        self.outputs = WeakValueDictionary()
        self.records = {}

    def issue(self, output, record):
        key = id(output)
        self.outputs[key] = output
        self.records[key] = record
        finalize(output, self.records.pop, key, None)
        return output

    def require(self, output):
        record = self.records.get(id(output))
        if self.outputs.get(id(output)) is not output or record is None:
            _invalid("B11_FORWARD_OUTPUT_NOT_ISSUED")
        return record


_FORWARD_ISSUANCE = _ForwardRegistry()
_LOSS_EXECUTION_ISSUER = object()


@dataclass(frozen=True, init=False)
class BamfLossExecution:
    """Exact B11 forward/loss witness accepted by the production B09 binder."""

    output: ModelOutput
    loss: LossParts
    visible_identity_rows: tuple[tuple[int, int], ...]
    feature_rows: tuple[tuple[str, int], ...]
    local_slot_rows: tuple[int, ...]
    dense_parameter_names: tuple[str, ...]
    schema_version: str = "bilqis.mlx.b11-loss-execution/v1"
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("B11_LOSS_EXECUTION_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (
            getattr(self, "_issuance", None) is not _LOSS_EXECUTION_ISSUER
            or type(self.output) is not ModelOutput
            or type(self.loss) is not LossParts
            or self.visible_identity_rows
            != tuple(sorted(set(self.visible_identity_rows)))
            or self.feature_rows != tuple(sorted(set(self.feature_rows)))
            or self.local_slot_rows != tuple(sorted(set(self.local_slot_rows)))
            or self.dense_parameter_names
            != tuple(sorted(set(self.dense_parameter_names)))
            or self.schema_version != "bilqis.mlx.b11-loss-execution/v1"
        ):
            _invalid("B11_LOSS_EXECUTION_INVALID")


@dataclass(frozen=True, init=False)
class BamfGradientExecution:
    """One exact MLX value-and-grad dispatch over one B11-issued loss."""

    execution: BamfLossExecution
    gradients: Mapping
    loss_total: mx.array
    schema_version: str = "bilqis.mlx.b11-gradient-execution/v1"
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("B11_GRADIENT_EXECUTION_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (
            getattr(self, "_issuance", None) is not _LOSS_EXECUTION_ISSUER
            or type(self.execution) is not BamfLossExecution
            or not isinstance(self.gradients, Mapping)
            or not isinstance(self.loss_total, mx.array)
            or self.loss_total.size != 1
            or not bool(mx.all(mx.isfinite(self.loss_total)))
            or self.schema_version != "bilqis.mlx.b11-gradient-execution/v1"
        ):
            _invalid("B11_GRADIENT_EXECUTION_INVALID")
        require_bamf_loss_execution(self.execution)


def _issue_loss_execution(output, loss, record):
    execution = object.__new__(BamfLossExecution)
    for name, value in (
        ("output", output),
        ("loss", loss),
        ("visible_identity_rows", record.visible_identity_rows),
        ("feature_rows", record.feature_rows),
        ("local_slot_rows", record.local_slot_rows),
        ("dense_parameter_names", record.dense_parameter_names),
        ("schema_version", "bilqis.mlx.b11-loss-execution/v1"),
        ("_issuance", _LOSS_EXECUTION_ISSUER),
    ):
        object.__setattr__(execution, name, value)
    execution.__post_init__()
    return execution


def require_bamf_loss_execution(execution):
    if type(execution) is not BamfLossExecution:
        _invalid("B11_LOSS_EXECUTION_REQUIRED")
    execution.__post_init__()
    record = _FORWARD_ISSUANCE.require(execution.output)
    if record.generation_binding != execution.output.generation_binding:
        _invalid("B11_LOSS_EXECUTION_GENERATION_MISMATCH")
    return execution


@dataclass(frozen=True)
class BamfCompiledBatch:
    """One source-qualified compiled row and the source inputs that created it."""

    compiled: CompiledEncoderInput
    sources: tuple[SourceAtomRow, ...]
    feature_schema: FeatureSchema
    schema_version: str = "bilqis.mlx.b11-compiled-batch/v1"

    def __post_init__(self) -> None:
        if (
            self.schema_version != "bilqis.mlx.b11-compiled-batch/v1"
            or type(self.compiled) is not CompiledEncoderInput
            or type(self.sources) is not tuple
            or len(self.sources) != len(self.compiled.compiled.rows)
            or len(self.sources) != 1
            or any(type(item) is not SourceAtomRow for item in self.sources)
            or type(self.feature_schema) is not FeatureSchema
        ):
            _invalid("B11_COMPILED_BATCH_INVALID")
        self.compiled.__post_init__()


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
        weights = parameters.get(name)
        banks.append(SemanticBankView(
            bank_index,
            weights,
            tuple(sorted(active_rows)),
            snapshot.release_sha256,
            snapshot.active_set_sha256,
        ))
    return tuple(banks)


def _forward_participation(params, batch, plan):
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
        "readout.state_norm", "readout.output_norm", "readout.query",
        "readout.key", "readout.value", "readout.output",
    ))
    kinds = {decision.kind for decision in plan.decisions}
    if DecisionKind.CONTROL in kinds:
        dense.update(("readout.control", "readout.control_bias"))
    if DecisionKind.ROLE in kinds:
        dense.add("readout.role_query")
    if DecisionKind.EPISTEMIC in kinds:
        dense.update(("readout.epistemic", "readout.epistemic_bias"))
    if any(decision.depends_on for decision in plan.decisions):
        dense.add("readout.feedback")
    if not dense <= set(params):
        _invalid("B11_EXECUTED_PARAMETER_CENSUS_MISMATCH")
    return _ForwardRecord(
        plan.generation_binding,
        tuple(sorted(set(visible))),
        tuple(sorted(feature_rows)),
        (0,),
        tuple(sorted(dense)),
    )


def forward_bamf(
    params,
    compiled_batch: BamfCompiledBatch,
    answer_plan: AnswerPlan,
    mode: ExecutionMode,
    cache,
) -> ModelOutput:
    """Run the source-backed 12-layer BAMF forward and typed decoder once.

    The current production dispatch admits inference without a retained-cache
    object.  Teacher-forced/loss execution is layered on this exact forward
    rather than opening a second direct model path.
    """
    if (
        type(compiled_batch) is not BamfCompiledBatch
        or type(answer_plan) is not AnswerPlan
        or mode is not ExecutionMode.INFERENCE
        or cache is not None
    ):
        _invalid("B11_FORWARD_INPUT_INVALID")
    compiled_batch.__post_init__()
    answer_plan.__post_init__()
    spec = ModelTopologySpecV2()
    extents = compiled_batch.compiled.extents
    validate_bamf_parameters(spec, extents, params)
    generation = execution_generation_digest(
        params, spec=spec, extents=extents)
    if answer_plan.generation_binding != generation:
        _invalid("B11_GENERATION_BINDING_MISMATCH")

    producer = start_source_backbone_producer(
        compiled_batch.compiled,
        params,
        compiled_batch.sources,
        compiled_batch.feature_schema,
    )
    hidden = finalize_source_backbone_hidden(producer)
    if hidden.shape[0] != 1:
        _invalid("B11_SINGLE_ROW_FORWARD_REQUIRED")
    row = compiled_batch.compiled.compiled.rows[0]
    projection = compiled_batch.compiled._projections[0]
    if (projection is not None
            and type(projection) is not ApprovedContextProjection):
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
        output, _forward_participation(params, compiled_batch, answer_plan))


def loss_bearing_bamf(
    output: ModelOutput,
    targets: tuple[DecisionOutput, ...],
    mask,
) -> BamfLossExecution:
    """Bind a nonempty B10 supervised loss to the exact live B11 forward."""
    record = _FORWARD_ISSUANCE.require(output)
    if (
        type(targets) is not tuple
        or not targets
        or not isinstance(mask, dict)
        or not any(mask.values())
    ):
        _invalid("B11_LOSS_TARGET_REQUIRED")
    loss = answer_loss(output, targets, mask)
    if not bool(mx.all(mx.isfinite(loss.total))):
        _invalid("B11_LOSS_NONFINITE")
    return _issue_loss_execution(output, loss, record)


def bamf_value_and_grad(
    params,
    compiled_batch: BamfCompiledBatch,
    answer_plan: AnswerPlan,
    targets: tuple[DecisionOutput, ...],
    mask,
    cache=None,
) -> BamfGradientExecution:
    """Run one exact forward/loss/gradient dispatch with one execution identity."""
    holder = {}

    def objective(current):
        output = forward_bamf(
            current, compiled_batch, answer_plan,
            ExecutionMode.INFERENCE, cache)
        execution = loss_bearing_bamf(output, targets, mask)
        holder["execution"] = execution
        return execution.loss.total

    loss_total, gradients = mx.value_and_grad(objective)(params)
    mx.eval(loss_total, gradients)
    execution = holder.get("execution")
    if type(execution) is not BamfLossExecution:
        _invalid("B11_GRADIENT_EXECUTION_MISSING")
    validate_bamf_parameters(
        ModelTopologySpecV2(), compiled_batch.compiled.extents, gradients)
    result = object.__new__(BamfGradientExecution)
    for name, value in (
        ("execution", execution),
        ("gradients", gradients),
        ("loss_total", loss_total),
        ("schema_version", "bilqis.mlx.b11-gradient-execution/v1"),
        ("_issuance", _LOSS_EXECUTION_ISSUER),
    ):
        object.__setattr__(result, name, value)
    result.__post_init__()
    return result


__all__ = (
    "BamfCompiledBatch", "BamfLossExecution", "BamfGradientExecution",
    "forward_bamf", "loss_bearing_bamf", "bamf_value_and_grad",
    "require_bamf_loss_execution",
)
