"""B05.1 shared depth selector over source-qualified, completed groups only.

The caller owns the A06 factor-composed type/role tensor and frame seed.
This module consumes those FP32 tensors without reading targets, future
summaries, source records or optimizer state.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .model_topology_v2 import ModelTopologySpecV2


WIDTH = ModelTopologySpecV2.width
INNER = 128
MIN_COMPLETED_GROUPS = 1
MAX_COMPLETED_GROUPS = ModelTopologySpecV2.depth_groups
FRAME_RANK = 3
_SHA = re.compile(r"[0-9a-f]{64}\Z")
PARAMETER_SHAPES = {
    "norm": (WIDTH,),
    "query": (INNER, WIDTH),
    "key": (INNER, WIDTH),
    "value": (INNER, WIDTH),
    "output": (WIDTH, INNER),
    "gate_vector": (WIDTH,),
    "gate_bias": (1,),
}
FEATURES_SCHEMA = "bilqis.mlx.depth-frame-features/v1"
SUMMARY_SCHEMA = "bilqis.mlx.depth-summary/v1"
SOURCE_ORDER = ("h0", "g1", "g2", "g3")
COMPLETED_LAYERS = (0, 4, 8, 12)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class DepthFrameFeatures:
    """A06-composed, source-visible features for one prediction boundary."""

    frame_seed: mx.array
    type_role: mx.array
    semantic_release: str
    source_evidence_digest: str
    boundary_group: int
    schema_version: str = FEATURES_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or not isinstance(self.source_evidence_digest, str)
                or not _SHA.fullmatch(self.source_evidence_digest)
                or type(self.boundary_group) is not int
                or not MIN_COMPLETED_GROUPS <= self.boundary_group <= MAX_COMPLETED_GROUPS
                or self.schema_version != FEATURES_SCHEMA):
            _invalid()


@dataclass(frozen=True)
class DepthSummary:
    source_id: str
    completed_layer: int
    hidden: mx.array
    schema_version: str = SUMMARY_SCHEMA

    def __post_init__(self) -> None:
        if (self.source_id not in SOURCE_ORDER
                or type(self.completed_layer) is not int
                or self.completed_layer != COMPLETED_LAYERS[
                    SOURCE_ORDER.index(self.source_id)]
                or self.schema_version != SUMMARY_SCHEMA):
            _invalid()


def _validate(current, available_summaries, frame_features, params) -> None:
    if (not isinstance(current, mx.array) or current.ndim != FRAME_RANK
            or current.shape[-1] != WIDTH or current.dtype != mx.float32
            or min(current.shape[:2]) < 1
            or not isinstance(available_summaries, tuple)
            or not MIN_COMPLETED_GROUPS + 1 <= len(available_summaries) <= MAX_COMPLETED_GROUPS + 1
            or any(type(value) is not DepthSummary
                   or not isinstance(value.hidden, mx.array)
                   or value.hidden.shape != current.shape
                   or value.hidden.dtype != mx.float32
                   for value in available_summaries)
            or type(frame_features) is not DepthFrameFeatures
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


def depth_select(
    current: mx.array, available_summaries: tuple[DepthSummary, ...],
    frame_features: DepthFrameFeatures, params: Mapping[str, mx.array],
) -> mx.array:
    """Merge h0 and completed group summaries in their fixed source order.

    The tuple must be (h0,g1,...,gk), k=1..3; future groups are not
    passed and cannot contribute to the source-axis softmax.
    """
    output, _, _ = _depth_components(
        current, available_summaries, frame_features, params)
    return output
