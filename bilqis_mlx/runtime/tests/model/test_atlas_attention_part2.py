"""Structural test shard from test_atlas_attention.py; assertions preserved."""
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
from bilqis_mlx.runtime.tests.model.test_atlas_attention_helpers import (digest, fixture, oracle)

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
