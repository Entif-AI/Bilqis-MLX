"""Literal disposable witnesses for BAMF causal convolution and native GQA."""
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


class AtlasConvolutionTests(unittest.TestCase):
    @staticmethod
    def parameters(identity=False):
        ledger = expected_bamf_shapes(ModelTopologySpecV2(),
                                     GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64))
        parameters = {}
        for suffix, factor in (("query", 1), ("key", 2), ("value", 3)):
            channels = 384 if suffix == "query" else 192
            weight = np.zeros((channels, 768), dtype=np.float32)
            weight[0, 0] = factor
            weight[24, 1] = -factor
            parameters[suffix] = mx.array(weight)
        for suffix in ("conv_q", "conv_k", "conv_v"):
            row = next(item for item in ledger if item.name == "blocks.0." + suffix)
            kernel = initialize_bamf_parameter(row, run_seed=0)
            if not identity:
                kernel[:] = [2, 3, 5]
            parameters[suffix] = mx.array(kernel)
        return parameters

    @staticmethod
    def hidden(values):
        values = np.asarray(values, dtype=np.float32)
        hidden = np.zeros((*values.shape, 768), dtype=np.float32)
        hidden[..., 0] = values
        hidden[..., 1] = values + 10
        return mx.array(hidden)

    def test_identity_initializer_preserves_independent_projected_heads(self):
        parameters = self.parameters(identity=True)
        hidden = self.hidden([[1, 2, 3]])
        (q, k, v), cache = project_convolved_qkv(parameters, hidden, mx.array([[7, 7, 7]]))
        self.assertEqual(q.shape, (1, 16, 3, 24))
        self.assertEqual(k.shape, (1, 8, 3, 24))
        self.assertEqual(v.shape, (1, 8, 3, 24))
        for value, factor in ((q, 1), (k, 2), (v, 3)):
            np.testing.assert_array_equal(np.asarray(value[0, 0, :, 0]), np.array([1, 2, 3]) * factor)
            np.testing.assert_array_equal(np.asarray(value[0, 1, :, 0]), -np.array([11, 12, 13]) * factor)
            self.assertEqual(float(mx.sum(mx.abs(value[:, :, :, 1:])).item()), 0)
        self.assertEqual(cache.query.shape, (1, 16, 2, 24))
        np.testing.assert_array_equal(np.asarray(cache.query[0, 0, :, 0]), [2, 3])

    def test_literal_left_only_convolution_resets_within_each_batch_row(self):
        parameters = self.parameters()
        hidden = self.hidden([[1, 2, 3, 4], [10, 20, 30, 40]])
        scope = mx.array([[7, 7, 9, 9], [7, 9, 7, 7]])
        (q, k, v), cache = project_convolved_qkv(parameters, hidden, scope)
        expected = np.array([[5, 13, 15, 29], [50, 100, 150, 290]], dtype=np.float32)
        for value, factor in ((q, 1), (k, 2), (v, 3)):
            np.testing.assert_array_equal(np.asarray(value[:, 0, :, 0]), expected * factor)
        np.testing.assert_array_equal(np.asarray(cache.query[:, 0, :, 0]), [[3, 4], [30, 40]])
        np.testing.assert_array_equal(np.asarray(cache.last_scope), [9, 7])
        changed = hidden.at[:, -1, :].add(100)
        (future, _, _), _ = project_convolved_qkv(parameters, changed, scope)
        np.testing.assert_array_equal(np.asarray(future[:, :, :-1]), np.asarray(q[:, :, :-1]))

    def test_sequence_boundary_and_chunked_decode_match_full_pass(self):
        parameters = self.parameters()
        hidden = self.hidden([[1, 2, 3, 4, 5]])
        scope = mx.array([[7, 7, 7, 8, 8]])
        starts = mx.array([[False, False, True, False, False]])
        full, full_cache = project_convolved_qkv(parameters, hidden, scope, sequence_starts=starts)
        np.testing.assert_array_equal(np.asarray(full[0][0, 0, :, 0]), [5, 13, 15, 20, 37])
        for cuts in ((1, 2, 3, 4, 5), (2, 5), (3, 4, 5)):
            cache, left, chunks = None, 0, []
            for right in cuts:
                before = None if cache is None else np.asarray(cache.query).copy()
                values, next_cache = project_convolved_qkv(
                    parameters, hidden[:, left:right], scope[:, left:right], cache=cache,
                    sequence_starts=starts[:, left:right])
                if cache is not None:
                    np.testing.assert_array_equal(np.asarray(cache.query), before)
                chunks.append(values)
                cache, left = next_cache, right
            for index in range(3):
                np.testing.assert_array_equal(np.asarray(mx.concatenate([x[index] for x in chunks], axis=2)),
                                              np.asarray(full[index]))
            for name in ("query", "key", "value", "last_scope"):
                np.testing.assert_array_equal(np.asarray(getattr(cache, name)),
                                              np.asarray(getattr(full_cache, name)))

    def test_gradients_obey_literal_taps_and_boundary(self):
        parameters = self.parameters()
        hidden = self.hidden([[1, 2, 3, 4]])
        scope = mx.array([[7, 7, 9, 9]])
        def objective(params, inputs):
            (q, _, _), _ = project_convolved_qkv(params, inputs, scope)
            return q[0, 0, 3, 0]
        parameter_gradients, input_gradients = mx.grad(objective, argnums=(0, 1))(parameters, hidden)
        np.testing.assert_array_equal(np.asarray(input_gradients[0, :, 0]), [0, 0, 3, 5])
        np.testing.assert_array_equal(np.asarray(parameter_gradients["conv_q"][0]), [0, 3, 4])
        self.assertEqual(float(parameter_gradients["query"][0, 0].item()), 29)
        for name in ("key", "value", "conv_k", "conv_v"):
            self.assertEqual(float(mx.sum(mx.abs(parameter_gradients[name])).item()), 0)

    def test_independent_numpy_oracle_with_distinct_channel_taps(self):
        rng = np.random.default_rng(445)
        hidden = rng.normal(0, .1, (2, 6, 768)).astype(np.float32)
        scope = np.array([[1, 1, 2, 1, 1, 1], [1, 1, 1, 1, 2, 2]], dtype=np.int32)
        starts = np.array([[False, False, False, False, False, False],
                           [False, False, True, False, False, False]])
        params, expected = {}, []
        for name, kernel_name, heads in (("query", "conv_q", 16), ("key", "conv_k", 8),
                                         ("value", "conv_v", 8)):
            weight = rng.normal(0, .1, (heads * 24, 768)).astype(np.float32)
            kernel = rng.normal(0, .2, (heads * 24, 3)).astype(np.float32)
            params[name], params[kernel_name] = mx.array(weight), mx.array(kernel)
            projected = hidden @ weight.T
            result = np.zeros_like(projected)
            for batch in range(2):
                history = []
                for token in range(6):
                    if starts[batch, token] or (token and scope[batch, token] != scope[batch, token - 1]):
                        history = []
                    history.append(projected[batch, token])
                    for lag in range(min(3, len(history))):
                        result[batch, token] += history[-1-lag] * kernel[:, 2-lag]
            expected.append(result.reshape(2, 6, heads, 24).transpose(0, 2, 1, 3))
        actual, _ = project_convolved_qkv(params, mx.array(hidden), mx.array(scope),
                                         sequence_starts=mx.array(starts))
        for value, oracle in zip(actual, expected):
            np.testing.assert_allclose(np.asarray(value), oracle, rtol=2e-5, atol=2e-6)

    def test_invalid_shapes_types_and_cache_fail_with_catalog_error(self):
        parameters = self.parameters()
        hidden, scope = self.hidden([[1, 2]]), mx.array([[7, 7]])
        _, cache = project_convolved_qkv(parameters, hidden, scope)
        calls = [
            lambda: project_convolved_qkv(parameters, hidden.astype(mx.float16), scope),
            lambda: project_convolved_qkv(parameters, hidden[..., :-1], scope),
            lambda: project_convolved_qkv(parameters, hidden, scope.astype(mx.float32)),
            lambda: project_convolved_qkv(parameters, hidden, scope[:, :1]),
            lambda: project_convolved_qkv(parameters, hidden, scope, sequence_starts=scope),
            lambda: project_convolved_qkv({**parameters, "query": parameters["query"].T}, hidden, scope),
            lambda: project_convolved_qkv({**parameters, "conv_k": mx.zeros((192, 2))}, hidden, scope),
            lambda: project_convolved_qkv(parameters, hidden, scope,
                                          cache=replace(cache, query=cache.query[:, :, :1])),
        ]
        for call in calls:
            with self.assertRaises(BilqisError) as error:
                call()
            self.assertEqual(error.exception.code, "SCHOOL.MODEL_TOPOLOGY.INVALID")


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


class AtlasGQATests(unittest.TestCase):
    def setUp(self):
        self.params, self.hidden = fixture()
        self.ids = mx.array([[7, 7, 9, 9, 9], [7, 7, 7, 7, 7]])
        self.valid = mx.array([[True, True, True, True, True], [True, True, True, False, False]])
        self.starts = mx.array([[False]*5, [False, False, True, False, False]])

    def scope(self, ids=None, starts=None, prefix="full", parent=None):
        return AttentionScope(ids=self.ids if ids is None else ids, layer=0,
                              generation=digest("generation"), prefix_digest=digest(prefix),
                              parent_prefix_digest=None if parent is None else digest(parent),
                              sequence_starts=self.starts if starts is None else starts)

    def test_native_production_geometry_matches_independent_rope_gqa_oracle(self):
        native = mx.fast.scaled_dot_product_attention
        shapes = []
        def observed(q, k, v, **kwargs):
            shapes.append((q.shape, k.shape, v.shape))
            return native(q, k, v, **kwargs)
        with patch("mlx.core.fast.scaled_dot_product_attention", side_effect=observed):
            actual, cache = ccgqa(self.params, self.hidden, self.valid, self.scope())
        expected = oracle(self.params, self.hidden, np.asarray(self.valid), np.asarray(self.ids),
                          np.asarray(self.starts))
        np.testing.assert_allclose(np.asarray(actual), expected, atol=2e-6, rtol=3e-5)
        self.assertEqual(shapes, [((2, 16, 5, 24), (2, 8, 5, 24), (2, 8, 5, 24))])
        self.assertEqual(cache.key.shape, (2, 8, 5, 24))
        self.assertEqual(cache.value.shape, (2, 8, 5, 24))
        manifest = cache.to_record()
        self.assertEqual(manifest["layer"], 0)
        self.assertEqual(manifest["generation"], digest("generation"))
        self.assertEqual(manifest["prefix_digest"], digest("full"))
        self.assertEqual(manifest["scope"], np.asarray(self.ids).tolist())
        self.assertEqual(manifest["rope"], {"dimensions": 24, "base": 10000, "traditional": False, "scale": 1.0})
        self.assertTrue(manifest["mlx_version"])

    def test_chunked_and_single_token_outputs_match_fresh_prefix(self):
        full, _ = ccgqa(self.params, self.hidden, self.valid, self.scope())
        for cuts in ((1, 2, 3, 4, 5), (2, 5), (3, 4, 5)):
            left, cache, chunks, parent = 0, None, [], None
            for right in cuts:
                scope = self.scope(self.ids[:, left:right], self.starts[:, left:right], str(right), parent)
                values, cache = ccgqa(self.params, self.hidden[:, left:right], self.valid[:, left:right],
                                      scope, cache=cache, offset=left)
                chunks.append(values)
                left, parent = right, str(right)
            np.testing.assert_allclose(np.asarray(mx.concatenate(chunks, axis=1)), np.asarray(full),
                                       atol=2e-6, rtol=3e-5)

    def test_zero_safe_padding_causality_and_nonzero_rope_offset(self):
        scope = self.scope()
        zero, _ = ccgqa(self.params, self.hidden, mx.zeros((2, 5), dtype=mx.bool_), scope)
        np.testing.assert_array_equal(np.asarray(zero), np.zeros((2, 5, 768)))
        full, _ = ccgqa(self.params, self.hidden, self.valid, scope)
        np.testing.assert_array_equal(np.asarray(full[1, 3:]), np.zeros((2, 768)))
        perturbed, _ = ccgqa(self.params, self.hidden.at[:, 3:].add(4), self.valid, scope)
        np.testing.assert_allclose(np.asarray(full[:, :3]), np.asarray(perturbed[:, :3]), atol=0, rtol=0)
        # A fresh prefix at offset 11 exercises the installed RoPE offset contract.
        shifted, _ = ccgqa(self.params, self.hidden, self.valid, scope, offset=11)
        expected = oracle(self.params, self.hidden, np.asarray(self.valid), np.asarray(self.ids),
                          np.asarray(self.starts), offset=11)
        np.testing.assert_allclose(np.asarray(shifted), expected, atol=2e-6, rtol=3e-5)

    def test_real_backward_reaches_all_projection_and_convolution_parameters(self):
        def objective(params):
            output, _ = ccgqa(params, self.hidden, self.valid, self.scope())
            return mx.sum(output * output)
        gradients = mx.grad(objective)(self.params)
        for name in self.params:
            value = np.asarray(gradients[name])
            self.assertTrue(np.isfinite(value).all(), name)
            self.assertGreater(float(np.abs(value).sum()), 0, name)

    def test_stale_cache_and_incompatible_context_reject_then_fresh_prefix_agrees(self):
        _, cache = ccgqa(self.params, self.hidden, self.valid, self.scope())
        short_scope = self.scope(self.ids[:, :2], self.starts[:, :2], "short")
        with self.assertRaises(BilqisError):
            ccgqa(self.params, self.hidden[:, :2], self.valid[:, :2], short_scope, cache=cache)
        fresh, _ = ccgqa(self.params, self.hidden[:, :2], self.valid[:, :2], short_scope)
        full, _ = ccgqa(self.params, self.hidden, self.valid, self.scope())
        np.testing.assert_allclose(np.asarray(fresh), np.asarray(full[:, :2]), atol=2e-6, rtol=3e-5)
        next_scope = self.scope(self.ids[:, :1], self.starts[:, :1], "next", "full")
        for changed in (replace(next_scope, generation=digest("other")),
                        replace(next_scope, layer=1), replace(next_scope, parent_prefix_digest=digest("wrong"))):
            with self.assertRaises(BilqisError):
                ccgqa(self.params, self.hidden[:, :1], self.valid[:, :1], changed, cache=cache, offset=5)

    def test_zero_mask_backward_and_malformed_cache_fail_closed(self):
        empty = mx.zeros((2, 5), dtype=mx.bool_)
        def objective(params):
            output, _ = ccgqa(params, self.hidden, empty, self.scope())
            return mx.sum(output)
        for gradient in mx.grad(objective)(self.params).values():
            np.testing.assert_array_equal(np.asarray(gradient), np.zeros(gradient.shape))
        _, cache = ccgqa(self.params, self.hidden, self.valid, self.scope())
        next_scope = self.scope(self.ids[:, :1], self.starts[:, :1], "next", "full")
        for changed in (replace(cache, convolution=None),
                        replace(cache, key=cache.key[:, :4]),
                        replace(cache, rope_variant=(24, 10000, True, 1.0)),
                        replace(cache, mlx_version="incompatible")):
            with self.assertRaises(BilqisError):
                ccgqa(self.params, self.hidden[:, :1], self.valid[:, :1], next_scope,
                       cache=changed, offset=5)

    def test_attention_view_borrows_exact_b01_tensor_prefix_without_new_parameters(self):
        spec = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
        ledger = expected_bamf_shapes(spec, extents)
        parameters = {
            item.name: mx.zeros(item.shape, dtype=mx.float32)
            for item in ledger
        }
        first = attention_parameter_view(
            parameters, spec=spec, extents=extents, layer=0)
        second = attention_parameter_view(
            parameters, spec=spec, extents=extents, layer=1)
        self.assertEqual(tuple(first), ATTENTION_PARAMETER_NAMES)
        self.assertEqual(tuple(second), ATTENTION_PARAMETER_NAMES)
        for suffix in ATTENTION_PARAMETER_NAMES:
            self.assertIs(first[suffix], parameters["blocks.0." + suffix])
            self.assertIs(second[suffix], parameters["blocks.1." + suffix])
            self.assertIsNot(first[suffix], second[suffix])
        self.assertEqual(first["query"].shape, (384, 768))
        self.assertEqual(first["key"].shape, (192, 768))
        self.assertEqual(first["conv_q"].shape, (384, 3))
        self.assertNotIn("features.norm", first)
        self.assertNotIn("attn_norm", first)
        self.assertEqual(len(parameters), len(ledger))
        output, _ = ccgqa(
            first, self.hidden[:, :2], self.valid[:, :2],
            self.scope(self.ids[:, :2], self.starts[:, :2]))
        np.testing.assert_array_equal(
            np.asarray(output), np.zeros((2, 2, 768), dtype=np.float32))

    def test_attention_view_rejects_missing_extra_or_malformed_b01_tensors(self):
        spec = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
        parameters = {
            item.name: mx.zeros(item.shape, dtype=mx.float32)
            for item in expected_bamf_shapes(spec, extents)
        }
        changes = (
            {"blocks.0.output": None},
            {"blocks.0.conv_q": mx.zeros((384, 2), dtype=mx.float32)},
            {"features.norm": mx.zeros((768,), dtype=mx.float16)},
            {"unexpected.trainable": mx.zeros((1,), dtype=mx.float32)},
        )
        for change in changes:
            malformed = dict(parameters)
            malformed.update(change)
            if "blocks.0.output" in change:
                malformed.pop("blocks.0.output")
            with self.subTest(change=tuple(change)), self.assertRaises(BilqisError):
                attention_parameter_view(
                    malformed, spec=spec, extents=extents, layer=0)
        for layer in (-1, 12, True):
            with self.assertRaises(BilqisError):
                attention_parameter_view(
                    parameters, spec=spec, extents=extents, layer=layer)


if __name__ == "__main__":
    unittest.main()
