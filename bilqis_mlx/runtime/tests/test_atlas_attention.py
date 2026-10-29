"""Literal disposable witnesses for BAMF causal QKV convolution."""
from dataclasses import replace
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_attention import project_convolved_qkv
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


if __name__ == "__main__":
    unittest.main()
