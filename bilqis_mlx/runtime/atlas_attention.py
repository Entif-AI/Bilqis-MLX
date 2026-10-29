"""BAMF pre-RoPE QKV projection and boundary-aware causal convolution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .model_topology_v2 import ModelTopologySpecV2


WIDTH = ModelTopologySpecV2.width
HEAD_DIMENSION = ModelTopologySpecV2.head_dimension
QUERY_HEADS = ModelTopologySpecV2.query_heads
KV_HEADS = ModelTopologySpecV2.kv_heads
KERNEL_SIZE = ModelTopologySpecV2.convolution_kernel
HISTORY_SIZE = KERNEL_SIZE - 1
QKV_LAYOUT = (("query", "conv_q", QUERY_HEADS),
              ("key", "conv_k", KV_HEADS), ("value", "conv_v", KV_HEADS))


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
    if (not isinstance(hidden, mx.array) or hidden.ndim != 3 or
            hidden.shape[-1] != WIDTH or hidden.dtype != mx.float32 or
            min(hidden.shape[:2]) < 1):
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
