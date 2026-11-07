"""BAMF pre-RoPE QKV projection and boundary-aware causal convolution."""
from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version as _package_version
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, SHA256_HEX_LENGTH,
    expected_bamf_shapes, validate_bamf_parameters,
)


WIDTH = ModelTopologySpecV2.width
HEAD_DIMENSION = ModelTopologySpecV2.head_dimension
QUERY_HEADS = ModelTopologySpecV2.query_heads
KV_HEADS = ModelTopologySpecV2.kv_heads
KERNEL_SIZE = ModelTopologySpecV2.convolution_kernel
HISTORY_SIZE = KERNEL_SIZE - 1
HIDDEN_RANK = 3
BATCH_SEQUENCE_AXES = 2
HEAD_ARRAY_RANK = 4
QKV_LAYOUT = (("query", "conv_q", QUERY_HEADS),
              ("key", "conv_k", KV_HEADS), ("value", "conv_v", KV_HEADS))
ATTENTION_PARAMETER_NAMES = (
    "query", "key", "value", "output", "conv_q", "conv_k", "conv_v",
)


def attention_parameter_view(
    parameters: Mapping[str, mx.array], *, spec: ModelTopologySpecV2,
    extents: GenerationExtents, layer: int,
) -> dict[str, mx.array]:
    """Borrow only this block's declared attention tensors from a full B01 tree.

    The normative ledger validates the *entire* tree before exposing references.
    This view creates no trainable arrays, aliases no shared feature/depth
    tensors, and leaves optimizer and checkpoint custody with their owners.
    """
    if (type(spec) is not ModelTopologySpecV2 or
            type(extents) is not GenerationExtents or
            type(layer) is not int or not 0 <= layer < spec.layers):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    validate_bamf_parameters(spec, extents, parameters)
    prefix = f"blocks.{layer}."
    declared = {item.name: item for item in expected_bamf_shapes(spec, extents)}
    names = tuple(prefix + suffix for suffix in ATTENTION_PARAMETER_NAMES)
    if any(name not in declared for name in names):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    return {suffix: parameters[prefix + suffix]
            for suffix in ATTENTION_PARAMETER_NAMES}


@dataclass(frozen=True)
class QKVConvolutionCache:
    """Last two pre-convolution values, oldest first, within the final scope.

    Each history has shape [batch, heads, 2, 24]. A boundary clears earlier
    entries. This derived cache contains no rotated or convolved values.
    """

    query: mx.array
    key: mx.array
    value: mx.array
    last_scope: mx.array


def _array_matches(value, shape, dtype) -> bool:
    return isinstance(value, mx.array) and value.shape == shape and value.dtype == dtype


def _validate_inputs(params, hidden, scope, cache, sequence_starts) -> None:
    if (not isinstance(hidden, mx.array) or hidden.ndim != HIDDEN_RANK or
            hidden.shape[-1] != WIDTH or hidden.dtype != mx.float32 or
            min(hidden.shape[:BATCH_SEQUENCE_AXES]) < 1):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    batch, length, _ = hidden.shape
    if (not isinstance(scope, mx.array) or scope.shape != (batch, length) or
            not mx.issubdtype(scope.dtype, mx.integer) or not isinstance(params, Mapping)):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    if sequence_starts is not None and not _array_matches(sequence_starts, (batch, length), mx.bool_):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    for name, kernel, heads in QKV_LAYOUT:
        channels = heads * HEAD_DIMENSION
        if (not _array_matches(params.get(name), (channels, WIDTH), mx.float32) or
                not _array_matches(params.get(kernel), (channels, KERNEL_SIZE), mx.float32)):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    if cache is not None:
        if (type(cache) is not QKVConvolutionCache or
                not _array_matches(cache.last_scope, (batch,), scope.dtype)):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        for name, _, heads in QKV_LAYOUT:
            if not _array_matches(getattr(cache, name), (batch, heads, HISTORY_SIZE, HEAD_DIMENSION), mx.float32):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _convolve(projected, kernel, history, same_previous):
    """Apply independent oldest-to-current taps; never read across a boundary."""
    batch, heads, length, channels = projected.shape
    if history is None:
        history = mx.zeros((batch, heads, HISTORY_SIZE, channels), dtype=mx.float32)
    padded = mx.concatenate((history, projected), axis=2)
    previous_same = mx.concatenate((mx.ones((batch, 1), dtype=mx.bool_), same_previous[:, :-1]), axis=1)
    one_back = mx.where(same_previous[:, None, :, None], padded[:, :, 1:-1], 0)
    two_back = mx.where((same_previous & previous_same)[:, None, :, None], padded[:, :, :-2], 0)
    taps = kernel.reshape(heads, channels, KERNEL_SIZE)
    output = (two_back * taps[None, :, None, :, 0] +
              one_back * taps[None, :, None, :, 1] +
              projected * taps[None, :, None, :, 2])
    older = mx.where(same_previous[:, -1, None, None], padded[:, :, -2], 0)
    next_history = mx.stack((older, projected[:, :, -1]), axis=2)
    return output, next_history


def project_convolved_qkv(params: Mapping[str, mx.array], hidden: mx.array, scope: mx.array,
                          *, cache: QKVConvolutionCache | None = None,
                          sequence_starts: mx.array | None = None
                          ) -> tuple[tuple[mx.array, mx.array, mx.array], QKVConvolutionCache]:
    """Project a block's local parameter mapping, then convolve before RoPE.

    Hidden is [B,T,768]; integer scope IDs and optional explicit sequence starts
    are [B,T]. A scope change or sequence start resets history in that batch row.
    When continuing decode, pass the previous returned cache. A new sequence
    starts with no cache, or marks its first token in sequence_starts even if its
    scope ID equals the preceding sequence's. Return Q/K/V in [B,H,T,24] order.
    No normalization, RoPE, attention, padding mask or optimizer update occurs here.
    """
    _validate_inputs(params, hidden, scope, cache, sequence_starts)
    batch, length, _ = hidden.shape
    first = (mx.zeros((batch, 1), dtype=mx.bool_) if cache is None else
             cache.last_scope[:, None] == scope[:, :1])
    same_previous = mx.concatenate((first, scope[:, 1:] == scope[:, :-1]), axis=1)
    if sequence_starts is not None:
        same_previous = same_previous & ~sequence_starts
    values, histories = [], []
    for name, kernel, heads in QKV_LAYOUT:
        projected = (hidden @ params[name].T).reshape(batch, length, heads, HEAD_DIMENSION).transpose(0, 2, 1, 3)
        value, history = _convolve(projected, params[kernel],
                                   None if cache is None else getattr(cache, name), same_previous)
        values.append(value)
        histories.append(history)
    return tuple(values), QKVConvolutionCache(*histories, last_scope=scope[:, -1])


# Persist the observed installed kernel identity with every derived cache receipt.
MLX_VERSION = _package_version("mlx")
ROPE_VARIANT = (ModelTopologySpecV2.rope_dimensions, ModelTopologySpecV2.rope_base,
                ModelTopologySpecV2.rope_traditional, ModelTopologySpecV2.rope_scale)
CACHE_SCHEMA = "bilqis.mlx.bamf-attention-cache/v1"


def _valid_digest(value) -> bool:
    return (isinstance(value, str) and len(value) == SHA256_HEX_LENGTH and
            all(character in "0123456789abcdef" for character in value))


@dataclass(frozen=True)
class AttentionScope:
    """Source scope coordinates and caller-bound identity of the resulting prefix."""

    ids: mx.array
    layer: int
    generation: str
    prefix_digest: str
    parent_prefix_digest: str | None = None
    sequence_starts: mx.array | None = None

    def __post_init__(self) -> None:
        if (type(self.layer) is not int or not 0 <= self.layer < ModelTopologySpecV2.layers or
                not _valid_digest(self.generation) or not _valid_digest(self.prefix_digest) or
                (self.parent_prefix_digest is not None and not _valid_digest(self.parent_prefix_digest))):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class AttentionCache:
    """Derived eight-head KV arrays and convolution history for one exact prefix."""

    key: mx.array
    value: mx.array
    convolution: QKVConvolutionCache
    scope_ids: mx.array
    sequence_ids: mx.array
    valid: mx.array
    layer: int
    generation: str
    prefix_digest: str
    start_offset: int
    rope_variant: tuple = ROPE_VARIANT
    mlx_version: str = MLX_VERSION

    def to_record(self) -> dict:
        dimensions, base, traditional, scale = self.rope_variant
        return {
            "schema": CACHE_SCHEMA, "layer": self.layer, "generation": self.generation,
            "prefix_digest": self.prefix_digest, "prefix_length": self.key.shape[2],
            "start_offset": self.start_offset,
            "scope": self.scope_ids.tolist(), "sequence": self.sequence_ids.tolist(),
            "rope": {"dimensions": dimensions, "base": base, "traditional": traditional, "scale": scale},
            "mlx_version": self.mlx_version,
        }


def _validate_attention(params, hidden, mask, scope, cache, offset) -> None:
    if type(scope) is not AttentionScope or type(offset) is not int or offset < 0:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    _validate_inputs(params, hidden, scope.ids, None, scope.sequence_starts)
    batch, length, _ = hidden.shape
    if (not _array_matches(mask, (batch, length), mx.bool_) or
            not _array_matches(params.get("output"), (WIDTH, QUERY_HEADS * HEAD_DIMENSION), mx.float32)):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    if cache is None:
        if scope.parent_prefix_digest is not None:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
        return
    if (type(cache) is not AttentionCache or cache.layer != scope.layer or
            cache.generation != scope.generation or cache.prefix_digest != scope.parent_prefix_digest or
            cache.rope_variant != ROPE_VARIANT or cache.mlx_version != MLX_VERSION or
            type(cache.convolution) is not QKVConvolutionCache or
            not isinstance(cache.key, mx.array) or cache.key.ndim != HEAD_ARRAY_RANK or
            type(cache.start_offset) is not int or cache.start_offset < 0):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
    previous_length = cache.key.shape[2]
    if (previous_length < 1 or offset != cache.start_offset + previous_length or
            not _array_matches(cache.key, (batch, KV_HEADS, previous_length, HEAD_DIMENSION), mx.float32) or
            not _array_matches(cache.value, cache.key.shape, mx.float32) or
            not _array_matches(cache.scope_ids, (batch, previous_length), scope.ids.dtype) or
            not _array_matches(cache.sequence_ids, (batch, previous_length), mx.int32) or
            not _array_matches(cache.valid, (batch, previous_length), mx.bool_)):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.MISMATCH)
    _validate_inputs(params, hidden, scope.ids, cache.convolution, scope.sequence_starts)


def ccgqa(params: Mapping[str, mx.array], h: mx.array, mask: mx.array, scope: AttentionScope,
          cache: AttentionCache | None = None, offset: int = 0) -> tuple[mx.array, AttentionCache]:
    """Native 16:8 GQA on normalized hidden input, with source/causal/padding masks.

    mask is boolean [B,T] validity for the new chunk. AttentionScope carries its
    source IDs, sequence boundaries and resulting canonical prefix digest. Cache
    continuation requires its parent digest, layer, generation and next offset.
    A fresh call can start at a nonzero RoPE offset. Cache receipts describe
    derived state; they do not admit source meanings or publish a model generation.
    """
    _validate_attention(params, h, mask, scope, cache, offset)
    batch, length, _ = h.shape
    starts = ~mask
    if scope.sequence_starts is not None:
        starts = starts | scope.sequence_starts
    (q, k, v), convolution = project_convolved_qkv(
        params, mx.where(mask[:, :, None], h, 0), scope.ids,
        cache=None if cache is None else cache.convolution, sequence_starts=starts)
    rope = dict(dims=ROPE_VARIANT[0], base=ROPE_VARIANT[1], traditional=ROPE_VARIANT[2],
                scale=ROPE_VARIANT[3], offset=offset)
    q, k = mx.fast.rope(q, **rope), mx.fast.rope(k, **rope)
    sequence_ids = mx.cumsum(starts.astype(mx.int32), axis=1)
    scope_ids, valid = scope.ids, mask
    previous_length = 0
    if cache is not None:
        previous_length = cache.key.shape[2]
        sequence_ids = sequence_ids + cache.sequence_ids[:, -1:]
        k, v = mx.concatenate((cache.key, k), axis=2), mx.concatenate((cache.value, v), axis=2)
        scope_ids = mx.concatenate((cache.scope_ids, scope_ids), axis=1)
        valid = mx.concatenate((cache.valid, valid), axis=1)
        all_sequences = mx.concatenate((cache.sequence_ids, sequence_ids), axis=1)
    else:
        all_sequences = sequence_ids
    key_positions = mx.arange(previous_length + length)
    causal = key_positions[None, :] <= (previous_length + mx.arange(length))[:, None]
    allowed = (causal[None] & mask[:, :, None] & valid[:, None, :] &
               (scope.ids[:, :, None] == scope_ids[:, None, :]) &
               (sequence_ids[:, :, None] == all_sequences[:, None, :]))
    has_key = mx.any(allowed, axis=-1, keepdims=True)
    # A harmless first-key fallback prevents undefined all-masked softmax rows.
    safe_mask = allowed | (~has_key & (key_positions[None, None, :] == 0))
    attended = mx.fast.scaled_dot_product_attention(q, k, v, scale=HEAD_DIMENSION ** -0.5,
                                                  mask=safe_mask[:, None])
    attended = mx.where(has_key[:, None], attended, 0)
    joined = attended.transpose(0, 2, 1, 3).reshape(batch, length, QUERY_HEADS * HEAD_DIMENSION)
    output = joined @ params["output"].T
    next_cache = AttentionCache(k, v, convolution, scope_ids, all_sequences, valid,
                                scope.layer, scope.generation, scope.prefix_digest,
                                offset if cache is None else cache.start_offset)
    return output, next_cache
