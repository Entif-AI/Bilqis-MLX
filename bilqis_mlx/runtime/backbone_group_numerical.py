"""B11.1a fixed four-layer numerical group; deliberately not a producer seal.

This module executes the selected B01/B04 equations. It does not authenticate
source h0, model generation, motif ordering or B13 custody. B05 must not
accept its result as completed-backbone provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .atlas_attention import AttentionCache, AttentionScope, ccgqa
from .model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)


UNADMITTED_NUMERICAL = "UNADMITTED_NUMERICAL"
HIDDEN_TENSOR_RANK = 3
_ATTENTION_PARAMETERS = (
    "query", "key", "value", "output", "conv_q", "conv_k", "conv_v")


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _norm(hidden: mx.array, scale: mx.array, epsilon: float) -> mx.array:
    return (hidden * mx.rsqrt(
        mx.mean(hidden * hidden, axis=-1, keepdims=True) + epsilon)
        * scale)


@dataclass(frozen=True)
class UnadmittedGroupNumerical:
    hidden: mx.array
    group_index: int
    layer_start: int
    layer_end: int
    attention_caches: tuple[AttentionCache, ...]
    admission_status: str = UNADMITTED_NUMERICAL

    def __post_init__(self) -> None:
        if (type(self.hidden) is not mx.array
                or self.hidden.dtype != mx.float32
                or self.hidden.ndim != HIDDEN_TENSOR_RANK
                or type(self.group_index) is not int
                or type(self.layer_start) is not int
                or type(self.layer_end) is not int
                or self.layer_start < 0
                or self.layer_end <= self.layer_start
                or type(self.attention_caches) is not tuple
                or len(self.attention_caches)
                != self.layer_end - self.layer_start
                or self.admission_status != UNADMITTED_NUMERICAL):
            _invalid()


def run_backbone_group_numerical(
    hidden: mx.array,
    parameters: Mapping[str, mx.array],
    *,
    group_index: int,
    spec: ModelTopologySpecV2,
    extents: GenerationExtents,
    scope_ids: mx.array,
    valid: mx.array,
    generation: str,
    prefix_digest: str,
) -> UnadmittedGroupNumerical:
    """Execute B01/B04 layers. The output is numerical evidence, not authority."""
    if (type(spec) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or type(group_index) is not int
            or not 1 <= group_index <= spec.depth_groups
            or type(hidden) is not mx.array
            or hidden.dtype != mx.float32
            or hidden.ndim != HIDDEN_TENSOR_RANK
            or hidden.shape[-1] != spec.width
            or not 1 <= hidden.shape[1] <= spec.context
            or type(scope_ids) is not mx.array
            or scope_ids.dtype != mx.int32
            or scope_ids.shape != hidden.shape[:-1]
            or type(valid) is not mx.array
            or valid.dtype != mx.bool_
            or valid.shape != hidden.shape[:-1]
            or not isinstance(parameters, Mapping)
            or spec.layers % spec.depth_groups):
        _invalid()
    group_size = spec.layers // spec.depth_groups
    start = (group_index - 1) * group_size
    end = start + group_size
    required = {
        item.name: item.shape for item in expected_bamf_shapes(spec, extents)
        if item.name.startswith("blocks.")
        and start <= int(item.name.split(".")[1]) < end}
    for name, shape in required.items():
        value = parameters.get(name)
        if (type(value) is not mx.array or value.dtype != mx.float32
                or value.shape != shape):
            _invalid()
    caches = []
    current = hidden
    for layer in range(start, end):
        prefix = f"blocks.{layer}."
        attn_input = _norm(
            current, parameters[prefix + "attn_norm"],
            spec.rms_norm_epsilon)
        scope = AttentionScope(
            scope_ids, layer, generation, prefix_digest)
        attention, cache = ccgqa({
                name: parameters[prefix + name]
                for name in _ATTENTION_PARAMETERS},
            attn_input, valid, scope)
        current = current + attention
        feed_input = _norm(
            current, parameters[prefix + "ffn_norm"],
            spec.rms_norm_epsilon)
        activated = mx.maximum(
            feed_input @ parameters[prefix + "ffn_in"].T, 0)
        current = current + (
            (activated * activated) @ parameters[prefix + "ffn_out"].T)
        caches.append(cache)
    return UnadmittedGroupNumerical(
        current, group_index, start, end, tuple(caches))
