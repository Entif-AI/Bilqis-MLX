"""B05 depth selection math and execution-owned producer qualification."""
from dataclasses import dataclass
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.learning.frame_embeddings import compose_factor_features
from .depth_contracts import (
    WIDTH, INNER, MIN_COMPLETED_GROUPS, MAX_COMPLETED_GROUPS, FRAME_RANK,
    BATCH_POSITION_AXES, PARAMETER_SHAPES, DIAGNOSTICS_SCHEMA, SOURCE_ORDER,
    DepthParameterView, _DepthFeatureValues, DepthFrameFeatures, DepthSummary,
    _invalid,
)
from .model_topology_v2 import ModelTopologySpecV2


def _validate(current, summaries, features, params) -> None:
    if (not isinstance(current, mx.array) or current.ndim != FRAME_RANK
            or current.shape[-1] != WIDTH or current.dtype != mx.float32
            or min(current.shape[:BATCH_POSITION_AXES]) < 1
            or not isinstance(summaries, tuple)
            or not MIN_COMPLETED_GROUPS + 1 <= len(summaries) <= MAX_COMPLETED_GROUPS + 1
            or any(type(value) is not DepthSummary
                   or not isinstance(value.hidden, mx.array)
                   or value.hidden.shape != current.shape
                   or value.hidden.dtype != mx.float32 for value in summaries)
            or type(features) is not _DepthFeatureValues
            or len(summaries) != features.boundary_group + 1
            or tuple(value.source_id for value in summaries) != SOURCE_ORDER[:len(summaries)]
            or not isinstance(features.frame_seed, mx.array)
            or features.frame_seed.shape != current.shape
            or features.frame_seed.dtype != mx.float32
            or not isinstance(features.type_role, mx.array)
            or features.type_role.shape != current.shape
            or features.type_role.dtype != mx.float32
            or not isinstance(params, Mapping) or set(params) != set(PARAMETER_SHAPES)):
        _invalid()
    for name, shape in PARAMETER_SHAPES.items():
        value = params[name]
        if (not isinstance(value, mx.array) or value.shape != shape
                or value.dtype != mx.float32):
            _invalid()
    finite = tuple(mx.all(mx.isfinite(value)) for value in (
        current, features.frame_seed, features.type_role,
        *(item.hidden for item in summaries), *params.values(),
    ))
    mx.eval(*finite)
    if not all(bool(flag) for flag in finite):
        _invalid()


def _rms_norm(values: mx.array, gamma: mx.array) -> mx.array:
    epsilon = ModelTopologySpecV2.rms_norm_epsilon
    return values * mx.rsqrt(
        mx.mean(values * values, axis=-1, keepdims=True) + epsilon) * gamma


def _depth_components(current, summaries, features, params):
    _validate(current, summaries, features, params)
    q = _rms_norm(current + features.frame_seed, params["norm"]) @ params["query"].T
    keys = mx.stack([
        _rms_norm(summary.hidden + features.type_role, params["norm"]) @ params["key"].T
        for summary in summaries
    ], axis=-2)
    values = mx.stack([summary.hidden @ params["value"].T for summary in summaries], axis=-2)
    scores = mx.sum(q[:, :, None, :] * keys, axis=-1) * (INNER ** -0.5)
    alpha = mx.softmax(scores, axis=-1)
    mix = mx.sum(alpha[:, :, :, None] * values, axis=-2)
    gate_logits = (
        mx.sum(params["gate_vector"] * _rms_norm(current, params["norm"]),
               axis=-1, keepdims=True) + params["gate_bias"])
    gate = 0.1 * mx.sigmoid(gate_logits)
    return current + gate * (mix @ params["output"].T), alpha, gate


@dataclass(frozen=True)
class DepthSelectionDiagnostics:
    output: mx.array
    alpha: mx.array
    gate: mx.array
    schema_version: str = DIAGNOSTICS_SCHEMA


def _numerical_depth_select(current, summaries, frame_features, params):
    return _numerical_depth_select_with_diagnostics(
        current, summaries, frame_features, params).output


def _numerical_depth_select_with_diagnostics(
    current, summaries, frame_features, params,
) -> DepthSelectionDiagnostics:
    if (type(params) is not DepthParameterView
            or type(frame_features) is not DepthFrameFeatures
            or params.boundary_group != frame_features.boundary_group
            or not isinstance(current, mx.array)
            or current.ndim != FRAME_RANK
            or current.shape[:BATCH_POSITION_AXES]
            != (len(frame_features.requests), len(frame_features.requests[0]))
            or type(summaries) is not tuple or not summaries
            or type(summaries[0]) is not DepthSummary):
        _invalid()
    type_role = mx.stack([mx.stack([
        mx.mean(compose_factor_features(
            params._feature_parameters, (members,), frame_features.features,
            extents=params._extents).type_role[0], axis=0)
        for members in row]) for row in frame_features.requests])
    numerical = _DepthFeatureValues(
        summaries[0].hidden, type_role, frame_features.features.semantic_release,
        frame_features.features.digest, frame_features.boundary_group)
    output, alpha, gate = _depth_components(current, summaries, numerical, params)
    return DepthSelectionDiagnostics(output, alpha, gate)


def _producer_summaries(producer, boundary_group, params):
    from bilqis_mlx.learning.source_atoms.backbone import _SourceBackboneProducerSession
    if (type(producer) is not _SourceBackboneProducerSession
            or type(params) is not DepthParameterView):
        _invalid()
    receipts = _SourceBackboneProducerSession._validated_receipts(
        producer, boundary_group)
    for index, item in enumerate(receipts):
        if (item.source_id != SOURCE_ORDER[index]
                or (index and item.predecessor_receipt_digest != receipts[index - 1].receipt_digest)
                or item.source_handoff_digest != receipts[0].source_handoff_digest
                or item.topology_digest != receipts[0].topology_digest
                or item.generation_digest != receipts[0].generation_digest
                or item.parameter_tree_digest != receipts[0].parameter_tree_digest
                or item.prefix_digest != receipts[0].prefix_digest
                or item.parameter_tree_digest != params.parameter_tree_digest
                or item.generation_digest != params.generation_digest):
            _invalid()
    summaries = tuple(DepthSummary(
        item.source_id, item.completed_layer,
        item.hidden if index == 0 else _rms_norm(item.hidden, params["norm"]),
    ) for index, item in enumerate(receipts))
    return summaries, receipts


def depth_select(producer, frame_features, params):
    return depth_select_with_diagnostics(
        producer, frame_features, params).output


def depth_select_with_diagnostics(producer, frame_features, params):
    if (type(frame_features) is not DepthFrameFeatures
            or type(params) is not DepthParameterView):
        _invalid()
    summaries, receipts = _producer_summaries(
        producer, frame_features.boundary_group, params)
    current = receipts[frame_features.boundary_group].hidden
    return _numerical_depth_select_with_diagnostics(
        current, summaries, frame_features, params)


DepthSelectionDiagnostics.__module__ = "bilqis_mlx.runtime.block_attnres"
