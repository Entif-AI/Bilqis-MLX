#!/usr/bin/env python3
"""Isolated #1615 differentiable prefix-trie block witness, not a production path."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.atlas_attention import AttentionScope, ccgqa
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2

SPEC = ModelTopologySpecV2()
ATTENTION = ("query", "key", "value", "output", "conv_q", "conv_k", "conv_v")


@dataclass(frozen=True)
class TrieLayout:
    tokens: mx.array
    depth: mx.array
    parent: mx.array
    grandparent: mx.array
    allowed: mx.array | None
    row_nodes: mx.array
    row_tokens: mx.array
    valid: mx.array
    representative: mx.array
    ancestors: mx.array | None
    ancestor_valid: mx.array | None

    @classmethod
    def build(cls, rows, *, gathered=False):
        lookup = {}
        tokens, depths, parents, chains = [], [], [], []
        width = max(len(row) for _, row in rows)
        node_rows, token_rows, masks, representatives = [], [], [], []
        for row_index, (scope, row) in enumerate(rows):
            prefix, chain, previous = (scope,), [], -1
            for depth, token in enumerate(row):
                prefix += (token,)
                if prefix not in lookup:
                    lookup[prefix] = len(tokens)
                    tokens.append(token)
                    depths.append(depth)
                    parents.append(previous)
                    chains.append((*chain, lookup[prefix]))
                    representatives.append(row_index * width + depth)
                previous = lookup[prefix]
                chain.append(previous)
            pad = width - len(row)
            node_rows.append(chain + [0] * pad)
            token_rows.append(list(row) + [0] * pad)
            masks.append([True] * len(row) + [False] * pad)
        allowed = None if gathered else mx.array(
            [[j in chain for j in range(len(tokens))] for chain in chains])
        ancestors = (mx.array([list(chain) + [0] * (width - len(chain)) for chain in chains])
                     if gathered else None)
        ancestor_valid = (mx.array([[True] * len(chain) + [False] * (width - len(chain))
                                    for chain in chains]) if gathered else None)
        return cls(mx.array(tokens), mx.array(depths),
                   mx.array(parents),
                   mx.array([parents[p] if p >= 0 else -1 for p in parents]),
                   allowed, mx.array(node_rows), mx.array(token_rows),
                   mx.array(masks), mx.array(representatives),
                   ancestors, ancestor_valid)


def norm(hidden, scale):
    return hidden * mx.rsqrt(mx.mean(hidden * hidden, axis=-1, keepdims=True)
                             + SPEC.rms_norm_epsilon) * scale


def project(params, hidden, name, conv, heads, layout):
    value = hidden @ params[name].T
    kernel = params[conv]
    parent = mx.where(layout.parent[:, None] >= 0,
                      value[mx.maximum(layout.parent, 0)], 0)
    grandparent = mx.where(layout.grandparent[:, None] >= 0,
                           value[mx.maximum(layout.grandparent, 0)], 0)
    value = grandparent * kernel[:, 0] + parent * kernel[:, 1] + value * kernel[:, 2]
    return value.reshape(len(layout.tokens), heads, 1, SPEC.head_dimension)


def shared_attention(params, hidden, layout, *, gathered=False):
    q = project(params, hidden, "query", "conv_q", SPEC.query_heads, layout)
    k = project(params, hidden, "key", "conv_k", SPEC.kv_heads, layout)
    v = project(params, hidden, "value", "conv_v", SPEC.kv_heads, layout)
    rope = dict(dims=SPEC.rope_dimensions, traditional=SPEC.rope_traditional,
                base=SPEC.rope_base, scale=SPEC.rope_scale, offset=layout.depth)
    q, k = mx.fast.rope(q, **rope), mx.fast.rope(k, **rope)
    if gathered:
        # One query per node, only its ancestral K/V. No cross-branch attention.
        k = k[:, :, 0, :][layout.ancestors].transpose(0, 2, 1, 3)
        v = v[:, :, 0, :][layout.ancestors].transpose(0, 2, 1, 3)
        out = mx.fast.scaled_dot_product_attention(
            q, k, v, scale=SPEC.head_dimension ** -0.5,
            mask=layout.ancestor_valid[:, None, None, :])
    else:
        out = mx.fast.scaled_dot_product_attention(
            q.transpose(2, 1, 0, 3), k.transpose(2, 1, 0, 3),
            v.transpose(2, 1, 0, 3), scale=SPEC.head_dimension ** -0.5,
            mask=layout.allowed[None, None]).transpose(0, 2, 1, 3)
    return out.reshape(
        len(layout.tokens), SPEC.query_heads * SPEC.head_dimension) @ params["output"].T


def block(params, hidden, layout, *, shared, gathered=False):
    hidden_norm = norm(hidden, params["attn_norm"])
    attention_params = {name: params[name] for name in ATTENTION}
    if shared:
        attended = shared_attention(attention_params, hidden_norm, layout, gathered=gathered)
    else:
        scope = AttentionScope(mx.zeros(layout.valid.shape, dtype=mx.int32),
                               0, "a" * 64, "b" * 64)
        attended, _ = ccgqa(attention_params, hidden_norm, layout.valid, scope)
    hidden = hidden + attended
    activated = mx.maximum(norm(hidden, params["ffn_norm"]) @ params["ffn_in"].T, 0)
    return hidden + (activated * activated) @ params["ffn_out"].T


def parameters():
    mx.random.seed(1615)
    width, head_dim = SPEC.width, SPEC.head_dimension
    q, kv = SPEC.query_heads * head_dim, SPEC.kv_heads * head_dim
    shape = {"query": (q, width), "key": (kv, width), "value": (kv, width),
             "output": (width, q), "ffn_in": (SPEC.ffn_dimension, width),
             "ffn_out": (width, SPEC.ffn_dimension), "input": (16, width)}
    p = {key: mx.random.normal(value) * .02 for key, value in shape.items()}
    p.update(attn_norm=mx.ones((width,)), ffn_norm=mx.ones((width,)))
    for key, channels in (("conv_q", q), ("conv_k", kv), ("conv_v", kv)):
        p[key] = mx.random.normal((channels, 3)) * .1 + mx.array([0., 0., 1.])
    mx.eval(p)
    return p


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--gathered", action="store_true")
    args = parser.parse_args()
    mx.set_default_device(mx.cpu if args.device == "cpu" else mx.gpu)
    # Distinct suffixes, mixed lengths, duplicate logical rows, incompatible scope.
    rows = (("a", (1, 2, 3, 4)), ("a", (1, 2, 5)), ("a", (1, 2, 3, 4)),
            ("b", (1, 2, 3)), ("a", (1, 6, 7, 8, 9)))
    layout = TrieLayout.build(rows, gathered=args.gathered)
    assert len(layout.tokens) == 12
    p = parameters()
    target = mx.random.normal((*layout.valid.shape, SPEC.width)) * .1
    mx.eval(target)

    def output(current, shared):
        index = layout.tokens if shared else layout.row_tokens
        hidden = block(current, current["input"][index], layout, shared=shared, gathered=args.gathered)
        return hidden[layout.row_nodes] if shared else hidden

    def loss(current, shared):
        prediction = output(current, shared)
        squared = mx.where(layout.valid[..., None], (prediction - target)**2, 0)
        return mx.sum(squared) / (sum(len(row) for _, row in rows) * SPEC.width)

    results = []
    for shared in (False, True):
        started = time.perf_counter()
        value, gradients = mx.value_and_grad(lambda current: loss(current, shared))(p)
        hidden = output(p, shared)
        mx.eval(value, gradients, hidden)
        results.append((value, gradients, hidden, time.perf_counter() - started))
    independent, trie = results
    mask = np.asarray(layout.valid)
    np.testing.assert_allclose(np.asarray(independent[2])[mask],
                               np.asarray(trie[2])[mask], rtol=2e-5, atol=2e-6)
    np.testing.assert_allclose(np.asarray(independent[0]), np.asarray(trie[0]),
                               rtol=2e-5, atol=2e-6)
    differences = {}
    for key in p:
        a, b = np.asarray(independent[1][key]), np.asarray(trie[1][key])
        np.testing.assert_allclose(a, b, rtol=2e-5, atol=2e-6, err_msg=key)
        differences[key] = float(np.max(np.abs(a-b)))
    print(json.dumps({"schema": "bilqis.bamf.issue1615-block-preflight/v1",
                      "device": args.device, "logical_positions": int(mask.sum()),
                      "unique_positions": len(layout.tokens),
                      "losses": [float(x[0]) for x in results],
                      "gradient_max_abs_error_by_leaf": differences,
                      "wall_seconds": [x[3] for x in results],
                      "passed": True, "authorizing": False}), flush=True)


if __name__ == "__main__":
    main()
