"""Bounded C05 multi-row B11 execution without changing per-case solver semantics."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Callable

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.frame_embeddings import semantic_bank_views
from bilqis_mlx.learning.frame_encoder import (
    CompiledEncoderInput, _prevalidated_combined_encoder_input,
)
from bilqis_mlx.learning.source_atoms.backbone import (
    finalize_source_backbone_hidden,
    start_source_backbone_producer,
)
from bilqis_mlx.runtime.backbone_identity import require_execution_generation_binding
from bilqis_mlx.runtime.atlas_model_backend import model_backend
from bilqis_mlx.runtime.atlas_model_forward import _decode_bamf_producer_row
from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch
from bilqis_mlx.runtime.factory_task_authority import FactoryTaskAuthority
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.microbatch.route_kernel import (
    prepare_route_microbatch_inference_kernel,
    route_microbatch_trajectory,
)
from bilqis_mlx.runtime.microbatch.refinement_kernel import batched_refine_hidden
from bilqis_mlx.runtime.task_goal_readout import task_goal_route_decisions
from bilqis_mlx.semantics.frame_compiler import CompiledFrameRows
from bilqis_mlx.learning.atlas_readout import AnswerPlan, ModelOutput
from bilqis_mlx.learning.atlas_readout.decoder.prediction import (
    attest_issued_outputs, live_issued_output,
)
from bilqis_mlx.runtime.autodiff_trace import defer_host_tensor_validation
from bilqis_mlx.runtime.atlas_model_refinement import _prediction_refinement_selection
from bilqis_mlx.runtime.microbatch.route_evidence import (
    _route_output_from_materialized_logits,
)

from .capability_evaluation import _invalid


_LEGACY_BATCH_ROWS = 24
_LEGACY_POSITION_LIMIT = 96
_MIN_SHARED_BATCH_ROWS = 2
_ACTIVATION_POSITION_BUDGET = _LEGACY_BATCH_ROWS * _LEGACY_POSITION_LIMIT
_ATTENTION_POSITION_BUDGET = _LEGACY_BATCH_ROWS * _LEGACY_POSITION_LIMIT ** 2
_RAGGED_LINEAR_COST_RATIO = 0.90
_RAGGED_ATTENTION_COST_RATIO = 0.80


@dataclass(frozen=True)
class PreparedFactoryEvaluation:
    """One already validated C05 row, ready for scalar or shared B11 execution."""

    batch: BamfCompiledBatch
    plan: AnswerPlan
    authority: FactoryTaskAuthority

    def __post_init__(self):
        if (type(self.batch) is not BamfCompiledBatch
                or type(self.plan) is not AnswerPlan
                or type(self.authority) is not FactoryTaskAuthority
                or self.batch.task_authority != self.authority
                or self.plan.generation_binding != self.authority.generation_binding):
            _invalid("BAMF_C05_BATCH_PREPARATION_INVALID")
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_mode_enabled,
        )
        if strict_mode_enabled():
            self.batch.__post_init__()
            self.plan.__post_init__()
            self.authority.__post_init__()


def _issued_outputs_valid(outputs, *, numerically_finite: bool) -> bool:
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_mode_enabled,
    )
    if strict_mode_enabled():
        return attest_issued_outputs(outputs)
    return bool(numerically_finite) and all(live_issued_output(output) for output in outputs)


def _positions(item: PreparedFactoryEvaluation) -> int:
    return len(item.batch.compiled.compiled.rows[0].positions)


def _capacity(items: tuple[PreparedFactoryEvaluation, ...]) -> int:
    if not items:
        return 1
    longest = max(_positions(item) for item in items)
    if longest < 1 or longest > _LEGACY_POSITION_LIMIT:
        return 1
    return max(1, min(
        len(items),
        _ACTIVATION_POSITION_BUDGET // longest,
        _ATTENTION_POSITION_BUDGET // (longest ** 2),
    ))


def _learning_first_partition_indices(items) -> tuple[tuple[int, ...], ...]:
    """Split one ragged ordinary C05 chunk only when padding waste is substantial."""
    count = len(items)
    whole = (tuple(range(count)),)
    if count < 4:
        return whole
    widths = tuple(_positions(item) for item in items)
    if any(width < 1 for width in widths):
        return whole
    ordered = tuple(sorted(range(count), key=lambda index: (widths[index], index)))
    base_linear = count * max(widths)
    base_attention = count * max(widths) ** 2
    best = None
    for cut in range(_MIN_SHARED_BATCH_ROWS, count - _MIN_SHARED_BATCH_ROWS + 1):
        left = ordered[:cut]
        right = ordered[cut:]
        if len(left) < _MIN_SHARED_BATCH_ROWS or len(right) < _MIN_SHARED_BATCH_ROWS:
            continue
        linear = (
            len(left) * max(widths[index] for index in left)
            + len(right) * max(widths[index] for index in right)
        )
        attention = (
            len(left) * max(widths[index] for index in left) ** 2
            + len(right) * max(widths[index] for index in right) ** 2
        )
        score = (attention, linear, cut)
        if best is None or score < best[0]:
            best = (score, left, right)
    if best is None:
        return whole
    (attention, linear, _cut), left, right = best
    if (linear > base_linear * _RAGGED_LINEAR_COST_RATIO
            or attention > base_attention * _RAGGED_ATTENTION_COST_RATIO):
        return whole
    groups = (
        tuple(sorted(left)),
        tuple(sorted(right)),
    )
    return groups


def _batchable(item: PreparedFactoryEvaluation) -> bool:
    return bool(task_goal_route_decisions(item.authority.goal)) and _positions(item) <= _LEGACY_POSITION_LIMIT


def _compatible(left: PreparedFactoryEvaluation, right: PreparedFactoryEvaluation) -> bool:
    a, b = left.batch, right.batch
    return (
        left.plan.generation_binding == right.plan.generation_binding
        and a.compiled.features == b.compiled.features
        and a.compiled.extents == b.compiled.extents
        and a.feature_schema == b.feature_schema
        and a.active_semantic_rows == b.active_semantic_rows
    )


def _combine(items: tuple[PreparedFactoryEvaluation, ...]) -> CompiledEncoderInput:
    batches = tuple(item.batch.compiled for item in items)
    rows = tuple(compiled.compiled.rows[0] for compiled in batches)
    width = max(len(row.positions) for row in rows)
    compiled_rows = CompiledFrameRows(
        rows,
        tuple(row.positions + (None,) * (width - len(row.positions)) for row in rows),
        tuple((True,) * len(row.positions) + (False,) * (width - len(row.positions))
              for row in rows),
    )
    first = batches[0]
    source_asts = tuple(compiled.source_asts[0] for compiled in batches)
    receipts = tuple(compiled.partial_forest_receipts[0] for compiled in batches)
    configs = tuple(compiled.compiler_configs[0] for compiled in batches)
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    if not strict_evidence_enabled():
        return _prevalidated_combined_encoder_input(
            compiled_rows, configs, first.features, first.extents, batches,
            source_asts=source_asts, partial_forest_receipts=receipts)
    return CompiledEncoderInput(
        compiled_rows, configs, first.features, first.extents,
        source_asts=source_asts, partial_forest_receipts=receipts)


def _validate_chunk(items):
    if len(items) < _MIN_SHARED_BATCH_ROWS or any(not _batchable(item) for item in items):
        _invalid("BAMF_C05_BATCH_CHUNK_INVALID")
    if any(not _compatible(items[0], item) for item in items[1:]):
        _invalid("BAMF_C05_BATCH_CHUNK_INCOMPATIBLE")
    if _capacity(items) < len(items):
        _invalid("BAMF_C05_BATCH_CHUNK_OVER_BUDGET")


def _execute_chunk(
    parameters,
    items: tuple[PreparedFactoryEvaluation, ...],
    on_launch: Callable[[int, int], None] | None,
    execution_binding,
) -> tuple[ModelOutput, ...]:
    _validate_chunk(items)
    combined = _combine(items)
    first = items[0].batch
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
        strict_evidence_enabled,
    )
    strict = strict_evidence_enabled()
    if strict:
        first.atlas_feature_artifact_owner.require(combined.features)
    backend = model_backend(ModelTopologySpecV2())
    if strict:
        require_execution_generation_binding(
            execution_binding, parameters,
            spec=backend.topology, extents=combined.extents)
    numerical_scope = nullcontext() if strict else defer_host_tensor_validation()
    with numerical_scope:
        banks = semantic_bank_views(
            parameters, combined.extents, combined.features.semantic_release,
            first.active_semantic_rows.active_indices)
        producer = start_source_backbone_producer(
            combined,
            parameters,
            tuple(item.batch.sources[0] for item in items),
            first.feature_schema,
            banks,
            first.atlas_feature_artifact_owner,
            execution_binding=execution_binding,
            trace=not strict,
            snapshot=items[0].plan.snapshot,
        )
        hidden = finalize_source_backbone_hidden(producer)
        vector_route = not strict
        if vector_route:
            refinement_selections = tuple(
                _prediction_refinement_selection(
                    item.batch, item.plan, item.plan.generation_binding,
                    training=False,
                )
                for item in items
            )
            hidden = batched_refine_hidden(
                parameters, tuple(item.batch for item in items),
                producer, hidden, refinement_selections)
            kernel = prepare_route_microbatch_inference_kernel(
                tuple(item.batch for item in items),
                tuple(item.plan for item in items),
            )
            trajectory, route_logits = route_microbatch_trajectory(
                parameters, hidden, kernel)
            trajectory_tensor = mx.stack(trajectory)
            flat_logits = mx.concatenate(tuple(
                value.reshape(-1) for value in route_logits))
            route_finite_tensor = mx.all(mx.isfinite(flat_logits))
            mx.eval(trajectory_tensor, *route_logits, route_finite_tensor)
            route_finite = bool(route_finite_tensor)
            trajectory_indices = np.asarray(
                trajectory_tensor, dtype=np.int64)
    if on_launch is not None:
        on_launch(len(items), max(_positions(item) for item in items))
    route_finite = route_finite if vector_route else True
    if vector_route:
        with defer_host_tensor_validation():
            outputs = tuple(
                _route_output_from_materialized_logits(
                    item.plan, index, trajectory_indices, route_logits)
                for index, item in enumerate(items)
            )
    else:
        with defer_host_tensor_validation():
            outputs = tuple(
                _decode_bamf_producer_row(
                    backend, parameters, item.batch, item.plan,
                    producer, hidden, index, execution_binding=execution_binding)
                for index, item in enumerate(items)
            )
    if not _issued_outputs_valid(outputs, numerically_finite=route_finite):
        _invalid("BAMF_C05_BATCH_OUTPUT_ATTESTATION_FAILED")
    return outputs


def batched_factory_outputs(
    parameters,
    prepared: tuple[PreparedFactoryEvaluation, ...],
    *,
    on_launch: Callable[[int, int], None] | None = None,
    execution_binding=None,
) -> tuple[ModelOutput | None, ...]:
    """Return issued outputs where sharing is lawful; None selects the scalar path."""
    if (not isinstance(prepared, tuple) or not prepared
            or any(type(item) is not PreparedFactoryEvaluation for item in prepared)
            or (on_launch is not None and not callable(on_launch))):
        _invalid("BAMF_C05_BATCH_INPUT_INVALID")
    outputs: list[ModelOutput | None] = [None] * len(prepared)
    cursor = 0
    while cursor < len(prepared):
        first = prepared[cursor]
        if not _batchable(first):
            cursor += 1
            continue
        chunk = [first]
        index = cursor + 1
        while index < len(prepared):
            candidate = prepared[index]
            proposed = tuple((*chunk, candidate))
            if (not _batchable(candidate)
                    or not _compatible(first, candidate)
                    or _capacity(proposed) < len(proposed)):
                break
            chunk.append(candidate)
            index += 1
        if len(chunk) > 1:
            from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
                strict_mode_enabled,
            )
            partitions = (
                (tuple(range(len(chunk))),)
                if strict_mode_enabled()
                else _learning_first_partition_indices(tuple(chunk))
            )
            for partition in partitions:
                subchunk = tuple(chunk[index] for index in partition)
                issued = _execute_chunk(
                    parameters, subchunk, on_launch, execution_binding)
                for local_index, output in zip(partition, issued, strict=True):
                    outputs[cursor + local_index] = output
            cursor += len(chunk)
        else:
            cursor += 1
    return tuple(outputs)


__all__ = ("PreparedFactoryEvaluation", "batched_factory_outputs")
