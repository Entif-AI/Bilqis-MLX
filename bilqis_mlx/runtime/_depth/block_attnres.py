"""Structural extraction from block_attnres.py; behavior preserved."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Mapping
import mlx.core as mx
from bilqis_mlx.learning.frame_embeddings import compose_factor_features
from bilqis_mlx.learning.atlas_plasticity import AdapterParameters, adapter_forward
from .model_topology_v2 import ModelTopologySpecV2
from .depth_contracts import BATCH_POSITION_AXES, COMPLETED_LAYERS, DIAGNOSTICS_SCHEMA, DepthFrameFeatures, DepthParameterView, DepthSummary, FRAME_RANK, INNER, MAX_COMPLETED_GROUPS, MIN_COMPLETED_GROUPS, PARAMETER_SHAPES, SOURCE_ORDER, WIDTH, _DepthFeatureValues, _invalid
from .depth_contracts import (BATCH_POSITION_AXES, COMPLETED_LAYERS, DIAGNOSTICS_SCHEMA, DepthFrameFeatures, DepthParameterView, DepthSummary, FEATURES_SCHEMA, FRAME_RANK, INNER, MAX_COMPLETED_GROUPS, MIN_COMPLETED_GROUPS, PARAMETER_SHAPES, PARAMETER_VIEW_SCHEMA, RELEASED_FEATURES_SCHEMA, SOURCE_ORDER, SUMMARY_SCHEMA, WIDTH, _DepthFeatureValues, _SHA, _VIEW_SEAL, _depth_names, _invalid, depth_parameter_view)

def _validate(current, available_summaries, frame_features, params) -> None:
    if (not isinstance(current, mx.array) or current.ndim != FRAME_RANK
            or current.shape[-1] != WIDTH or current.dtype != mx.float32
            or min(current.shape[:BATCH_POSITION_AXES]) < 1
            or not isinstance(available_summaries, tuple)
            or not MIN_COMPLETED_GROUPS + 1 <= len(available_summaries) <= MAX_COMPLETED_GROUPS + 1
            or any(type(value) is not DepthSummary
                   or not isinstance(value.hidden, mx.array)
                   or value.hidden.shape != current.shape
                   or value.hidden.dtype != mx.float32
                   for value in available_summaries)
            or type(frame_features) is not _DepthFeatureValues
            or len(available_summaries) != frame_features.boundary_group + 1
            or tuple(value.source_id for value in available_summaries)
            != SOURCE_ORDER[:len(available_summaries)]
            or not isinstance(frame_features.frame_seed, mx.array)
            or frame_features.frame_seed.shape != current.shape
            or frame_features.frame_seed.dtype != mx.float32
            or not isinstance(frame_features.type_role, mx.array)
            or frame_features.type_role.shape != current.shape
            or frame_features.type_role.dtype != mx.float32
            or not isinstance(params, Mapping)
            or set(params) != set(PARAMETER_SHAPES)):
        _invalid()
    for name, shape in PARAMETER_SHAPES.items():
        value = params[name]
        if (not isinstance(value, mx.array) or value.shape != shape
                or value.dtype != mx.float32):
            _invalid()
    finite_flags = tuple(mx.all(mx.isfinite(value)) for value in (
        current, frame_features.frame_seed, frame_features.type_role,
        *(item.hidden for item in available_summaries), *params.values(),
    ))
    mx.eval(*finite_flags)
    if not all(bool(flag) for flag in finite_flags):
        _invalid()

def _rms_norm(values: mx.array, gamma: mx.array) -> mx.array:
    epsilon = ModelTopologySpecV2.rms_norm_epsilon
    return values * mx.rsqrt(
        mx.mean(values * values, axis=-1, keepdims=True) + epsilon) * gamma

def _depth_components(current, available_summaries, frame_features, params):
    """Return output and proof-only alpha/gate values, without mutable caches."""
    _validate(current, available_summaries, frame_features, params)
    q = _rms_norm(current + frame_features.frame_seed, params["norm"]) @ params["query"].T
    keys = mx.stack([
        _rms_norm(summary.hidden + frame_features.type_role, params["norm"]) @ params["key"].T
        for summary in available_summaries
    ], axis=-2)
    values = mx.stack([
        summary.hidden @ params["value"].T for summary in available_summaries
    ], axis=-2)
    scores = mx.sum(q[:, :, None, :] * keys, axis=-1) * (INNER ** -0.5)
    alpha = mx.softmax(scores, axis=-1)
    mix = mx.sum(alpha[:, :, :, None] * values, axis=-2)
    gate_logits = (
        mx.sum(params["gate_vector"] * _rms_norm(current, params["norm"]),
               axis=-1, keepdims=True) + params["gate_bias"])
    gate = 0.1 * mx.sigmoid(gate_logits)
    output = current + gate * (mix @ params["output"].T)
    return output, alpha, gate

@dataclass(frozen=True)
class DepthSelectionDiagnostics:
    """Source-qualified selector output and optional source-axis weights."""

    output: mx.array
    alpha: mx.array
    gate: mx.array
    schema_version: str = DIAGNOSTICS_SCHEMA

def depth_select(
    current: mx.array, available_summaries: tuple[DepthSummary, ...],
    frame_features: DepthFrameFeatures, params: DepthParameterView,
) -> mx.array:
    """Merge h0 and completed group summaries in their fixed source order.

    The tuple is ordered (h0,g1,...,gk), k=1..3. Its actual backbone
    provenance must be qualified by the group-capture assembly owner.
    """
    return depth_select_with_diagnostics(
        current, available_summaries, frame_features, params).output

def depth_select_with_diagnostics(
    current: mx.array, available_summaries: tuple[DepthSummary, ...],
    frame_features: DepthFrameFeatures, params: DepthParameterView,
) -> DepthSelectionDiagnostics:
    """Expose alpha for inspection, without assigning roles to depth groups."""
    if (type(params) is not DepthParameterView
            or type(frame_features) is not DepthFrameFeatures
            or params.boundary_group != frame_features.boundary_group):
        _invalid()
    if (not isinstance(current, mx.array) or current.ndim != FRAME_RANK
            or current.shape[:BATCH_POSITION_AXES] != (len(frame_features.requests), len(frame_features.requests[0]))
            or type(available_summaries) is not tuple or not available_summaries
            or type(available_summaries[0]) is not DepthSummary):
        _invalid()
    type_role = mx.stack([mx.stack([
        mx.mean(compose_factor_features(params._feature_parameters, (members,), frame_features.features,
                                        extents=params._extents).type_role[0], axis=0)
        for members in row]) for row in frame_features.requests])
    numerical = _DepthFeatureValues(available_summaries[0].hidden, type_role,
                                     frame_features.features.semantic_release,
                                     frame_features.features.digest, frame_features.boundary_group)
    output, alpha, gate = _depth_components(
        current, available_summaries, numerical, params)
    return DepthSelectionDiagnostics(output, alpha, gate)

@dataclass(frozen=True)
class _NumericalGroupBoundary:
    """Private assembly proof; not a B08 source-authorized motif read."""

    captured: DepthSummary
    selected: mx.array
    adapted: mx.array
    alpha: mx.array
    gate: mx.array

def _group_boundary_numerical(
    current: mx.array, previous: tuple[DepthSummary, ...],
    features: _DepthFeatureValues, depth_params: Mapping[str, mx.array],
    adapter: AdapterParameters,
    *, second_motif_read: Callable[[mx.array], mx.array] | None = None,
) -> _NumericalGroupBoundary:
    """Prove B05 boundary ordering without granting a production motif reader.

    At group one, the caller-supplied private numerical motif read runs after
    layer four but before g1 is captured. At every group, the selector sees
    only h0 and already completed groups; the matching rank-eight adapter
    runs *after* selection. B08/B11 must later qualify the actual source
    read and backbone summary origin before this sequence is published.
    """
    if (type(features) is not _DepthFeatureValues
            or type(adapter) is not AdapterParameters
            or type(previous) is not tuple
            or len(previous) != features.boundary_group
            or adapter.group_index != features.boundary_group - 1
            or (features.boundary_group == 1) != (second_motif_read is not None)
            or (second_motif_read is not None and not callable(second_motif_read))
            or not isinstance(current, mx.array)
            or current.ndim != FRAME_RANK
            or current.shape[-1] != WIDTH
            or current.dtype != mx.float32
            or not isinstance(depth_params, Mapping)
            or "norm" not in depth_params
            or not isinstance(depth_params["norm"], mx.array)
            or depth_params["norm"].shape != (WIDTH,)
            or depth_params["norm"].dtype != mx.float32
            or not bool(mx.all(mx.isfinite(current)))):
        _invalid()
    post_motif = (second_motif_read(current)
                  if second_motif_read is not None else current)
    if (not isinstance(post_motif, mx.array)
            or post_motif.shape != current.shape
            or post_motif.dtype != mx.float32):
        _invalid()
    group = features.boundary_group
    captured = DepthSummary(
        SOURCE_ORDER[group], COMPLETED_LAYERS[group],
        _rms_norm(post_motif, depth_params["norm"]))
    selected, alpha, gate = _depth_components(
        post_motif, (*previous, captured), features, depth_params)
    adapted = adapter_forward(selected, adapter)
    return _NumericalGroupBoundary(captured, selected, adapted, alpha, gate)
