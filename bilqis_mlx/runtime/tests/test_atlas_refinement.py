"""B06.1 private numerical recurrence; no source/backbone assembly witness."""
import hashlib
import math
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_refinement import _refine_frame, refinement_parameter_view
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes


def _oracle(hidden, seed, members, role, passes, parameters):
    p = {name: np.asarray(value) for name, value in parameters.items()}
    def norm(x):
        return x / np.sqrt(np.mean(x*x) + 1e-5) * p["refine.norm"]
    state = np.asarray(hidden).copy()
    for _ in range(passes):
        q = norm(state+seed+role) @ p["refine.query"].T
        k = members @ p["refine.key"].T
        v = members @ p["refine.value"].T
        scores = q @ k.T / np.sqrt(192)
        weights = np.exp(scores - scores.max())
        weights /= weights.sum()
        gate = .1 / (1 + np.exp(-(np.sum(norm(state)*p["refine.gate_vector"])+p["refine.bias"])))
        state = state + gate * ((weights @ v) @ p["refine.output"].T)
    return state


class RefinementKernelTests(unittest.TestCase):
    def setUp(self):
        self.spec = ModelTopologySpecV2()
        self.extents = GenerationExtents(1, 1, hashlib.sha256(b"[11]").hexdigest(), "b"*64, "c"*64)
        rng = np.random.default_rng(452)
        self.params = {item.name: mx.array(rng.normal(0, .025, item.shape).astype(np.float32))
                       for item in expected_bamf_shapes(self.spec, self.extents)
                       if item.name.startswith("refine.")}
        self.params["refine.norm"] = mx.ones((768,), dtype=mx.float32)
        self.params["refine.gate_vector"] = mx.zeros((768,), dtype=mx.float32)
        self.params["refine.bias"] = mx.array([math.log(1/9)], dtype=mx.float32)
        self.hidden, self.seed, self.role = (mx.array(rng.normal(0, .1, 768).astype(np.float32))
                                            for _ in range(3))
        self.members = mx.array(rng.normal(0, .1, (3, 768)).astype(np.float32))

    def run_kernel(self, passes, **changes):
        values = dict(hidden=self.hidden, seed=self.seed, members=self.members, role=self.role,
                      passes=passes, parameters=self.params)
        values.update(changes)
        return _refine_frame(**values)

    def test_zero_identity_and_literal_one_two_pass_numpy_oracle(self):
        zero = self.run_kernel(0)
        self.assertIs(zero.hidden, self.hidden)
        self.assertIsNone(zero.route_logits)
        self.assertEqual(zero.passes, 0)
        originals = [np.asarray(x).copy() for x in (self.hidden, self.seed, self.members, self.role)]
        self.assertAlmostEqual(float(.1*mx.sigmoid(self.params["refine.bias"])[0]), .01, places=8)
        for passes in (1, 2):
            result = self.run_kernel(passes)
            expected = _oracle(*[np.asarray(x) for x in (self.hidden, self.seed, self.members, self.role)],
                               passes, self.params)
            np.testing.assert_allclose(np.asarray(result.hidden), expected, atol=1e-7, rtol=1e-5)
            np.testing.assert_allclose(np.asarray(result.route_logits),
                                       expected @ np.asarray(self.params["refine.route"]).T +
                                       np.asarray(self.params["refine.route_bias"]), atol=1e-7)
            self.assertGreater(float(mx.sum(mx.abs(result.hidden-self.hidden))), 0)
        for actual, original in zip((self.hidden, self.seed, self.members, self.role), originals):
            np.testing.assert_array_equal(np.asarray(actual), original)

    def test_original_seed_recalled_on_second_pass_and_single_member_attention(self):
        actual = self.run_kernel(2).hidden
        first = self.run_kernel(1).hidden
        forgotten = self.run_kernel(1, hidden=first, seed=mx.zeros_like(self.seed)).hidden
        recalled = self.run_kernel(1, hidden=first).hidden
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(recalled))
        self.assertGreater(float(mx.max(mx.abs(actual-forgotten))), 0)
        single = self.run_kernel(1, members=self.members[:1]).hidden
        expected = self.hidden + .01 * ((self.members[0] @ self.params["refine.value"].T) @
                                       self.params["refine.output"].T)
        np.testing.assert_allclose(np.asarray(single), np.asarray(expected), atol=1e-7)

    def test_two_pass_and_route_gradients_reach_shared_parameters_and_inputs(self):
        weights = mx.arange(768, dtype=mx.float32)
        def loss(parameters):
            result = self.run_kernel(2, parameters=parameters)
            return mx.sum(result.hidden*weights) + mx.sum(result.route_logits)
        gradient = mx.grad(loss)(self.params)
        for name, value in gradient.items():
            with self.subTest(name=name):
                self.assertTrue(bool(mx.all(mx.isfinite(value))))
                self.assertGreater(float(mx.sum(mx.abs(value))), 0)
        for key in ("hidden", "seed", "members", "role"):
            value = getattr(self, key)
            derivative = mx.grad(lambda x: mx.sum(self.run_kernel(2, **{key: x}).hidden*weights))(value)
            self.assertTrue(bool(mx.all(mx.isfinite(derivative))))
            self.assertGreater(float(mx.sum(mx.abs(derivative))), 0, key)

    def test_invalid_budget_tensor_or_parameter_prefix_rejects(self):
        for passes in (-1, 3, True, 1.0):
            with self.assertRaises(BilqisError):
                self.run_kernel(passes)
        for changes in ({"members": self.members[:0]}, {"seed": self.seed.astype(mx.float16)},
                        {"role": mx.zeros((1, 768))}, {"hidden": mx.full((768,), float("nan"))},
                        {"parameters": {k:v for k,v in self.params.items() if k != "refine.query"}},
                        {"parameters": {**self.params, "refine.query": mx.zeros((768, 192))}},
                        {"parameters": {**self.params, "refine.bias": mx.array([float("inf")])}}):
            with self.assertRaises(BilqisError):
                self.run_kernel(1, **changes)

    def test_full_tree_view_has_exact_refine_tensor_aliases(self):
        full = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                for item in expected_bamf_shapes(self.spec, self.extents)}
        view = refinement_parameter_view(full, spec=self.spec, extents=self.extents)
        self.assertEqual(set(view), set(self.params))
        for name in view:
            self.assertIs(view[name], full[name])
        with self.assertRaises(BilqisError):
            refinement_parameter_view({**full, "unregistered.head": mx.zeros((1,))},
                                       spec=self.spec, extents=self.extents)


if __name__ == "__main__":
    unittest.main()
