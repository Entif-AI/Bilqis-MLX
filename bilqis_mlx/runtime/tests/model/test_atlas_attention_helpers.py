"""Shared fixtures extracted structurally from test_atlas_attention.py."""
from dataclasses import replace
import hashlib
import unittest
from unittest.mock import patch
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_attention import (
    ATTENTION_PARAMETER_NAMES, AttentionScope, attention_parameter_view,
    ccgqa, project_convolved_qkv,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes, initialize_bamf_parameter,
)

def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()

def fixture():
    rng = np.random.default_rng(446)
    params = {}
    for name, shape in (("query", (384, 768)), ("key", (192, 768)),
                        ("value", (192, 768)), ("output", (768, 384))):
        params[name] = mx.array(rng.normal(0, .02, shape).astype(np.float32))
    for name, channels in (("conv_q", 384), ("conv_k", 192), ("conv_v", 192)):
        params[name] = mx.array(rng.normal(0, .2, (channels, 3)).astype(np.float32))
    hidden = mx.array(rng.normal(0, .1, (2, 5, 768)).astype(np.float32))
    return params, hidden

def oracle(params, hidden, valid, scopes, starts, offset=0):
    """Literal FP32 loops; no production projection, convolution, RoPE or GQA calls."""
    hidden = np.asarray(hidden)
    projected = []
    for name, kernel_name, heads in (("query", "conv_q", 16), ("key", "conv_k", 8),
                                     ("value", "conv_v", 8)):
        raw = hidden @ np.asarray(params[name]).T
        output = np.zeros_like(raw)
        kernel = np.asarray(params[kernel_name])
        for batch in range(2):
            history = []
            for t in range(5):
                if starts[batch, t] or (t and scopes[batch, t] != scopes[batch, t-1]):
                    history = []
                history.append(raw[batch, t])
                for lag in range(min(3, len(history))):
                    output[batch, t] += history[-1-lag] * kernel[:, 2-lag]
        projected.append(output.reshape(2, 5, heads, 24).transpose(0, 2, 1, 3))
    q, k, v = projected
    frequencies = np.power(np.float32(10000), -np.arange(12, dtype=np.float32) / np.float32(12))
    angles = np.arange(offset, offset+5, dtype=np.float32)[:, None] * frequencies
    for index, value in enumerate((q, k)):
        first, second = value[..., :12], value[..., 12:]
        projected[index] = np.concatenate((first * np.cos(angles) - second * np.sin(angles),
                                           first * np.sin(angles) + second * np.cos(angles)), axis=-1)
    q, k, v = projected
    sequences = np.cumsum(starts, axis=1)
    result = np.zeros((2, 16, 5, 24), dtype=np.float32)
    for batch in range(2):
        for head in range(16):
            for t in range(5):
                indices = [j for j in range(t+1) if valid[batch, t] and valid[batch, j] and
                           scopes[batch, t] == scopes[batch, j] and sequences[batch, t] == sequences[batch, j]]
                if not indices:
                    continue
                scores = (k[batch, head//2, indices] @ q[batch, head, t]) / np.float32(np.sqrt(24))
                weights = np.exp(scores - scores.max())
                weights /= weights.sum()
                result[batch, head, t] = weights @ v[batch, head//2, indices]
    return result.transpose(0, 2, 1, 3).reshape(2, 5, 384) @ np.asarray(params["output"]).T

if __name__ == "__main__":
    unittest.main()
