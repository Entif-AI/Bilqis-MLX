"""B11.1a fixed group execution, without producer admission."""
from dataclasses import replace
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.backbone_group_numerical import (
    UnadmittedGroupNumerical, run_backbone_group_numerical,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)


SPEC = ModelTopologySpecV2()
EXTENTS = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)


def _params():
    rng = np.random.default_rng(587)
    values = {}
    for item in expected_bamf_shapes(SPEC, EXTENTS):
        if not item.name.startswith("blocks."):
            continue
        if int(item.name.split(".")[1]) >= 8:
            continue
        if item.name.endswith("_norm"):
            values[item.name] = mx.ones(item.shape, dtype=mx.float32)
        else:
            values[item.name] = mx.array(
                rng.normal(0, 0.01, item.shape).astype(np.float32))
    return values


def _run(hidden, params, group_index=1, sequence_starts=None):
    return run_backbone_group_numerical(
        hidden, params, group_index=group_index,
        spec=SPEC, extents=EXTENTS,
        scope_ids=mx.zeros(hidden.shape[:2], dtype=mx.int32),
        valid=mx.ones(hidden.shape[:2], dtype=mx.bool_),
        generation="d" * 64, prefix_digest="e" * 64,
        sequence_starts=sequence_starts)


class BackboneGroupNumericalTests(unittest.TestCase):
    def test_internal_sequence_boundary_blocks_cross_sequence_history(self):
        params = _params()
        hidden = mx.arange(4 * SPEC.width, dtype=mx.float32).reshape(
            1, 4, SPEC.width) / 1000
        starts = mx.array([[False, False, True, False]])
        changed = mx.concatenate((
            mx.ones((1, 2, SPEC.width), dtype=mx.float32) * 100,
            hidden[:, 2:]), axis=1)
        original = _run(
            hidden, params, sequence_starts=starts).hidden
        altered = _run(
            changed, params, sequence_starts=starts).hidden
        self.assertTrue(bool(mx.all(
            mx.abs(original[:, 2:] - altered[:, 2:]) < 1e-4)))
        with self.assertRaises(BilqisError):
            _run(hidden, params, sequence_starts=mx.zeros(
                (1, 3), dtype=mx.bool_))

    def test_four_real_layers_emit_only_unadmitted_numerical_result(self):
        params = _params()
        hidden = mx.arange(4 * SPEC.width, dtype=mx.float32).reshape(
            1, 4, SPEC.width) / 1000
        first = _run(hidden, params)
        self.assertIs(type(first), UnadmittedGroupNumerical)
        self.assertEqual(first.admission_status, "UNADMITTED_NUMERICAL")
        self.assertEqual((first.group_index, first.layer_start, first.layer_end),
                         (1, 0, 4))
        self.assertEqual(first.hidden.shape, hidden.shape)
        self.assertEqual(len(first.attention_caches), 4)
        self.assertTrue(bool(mx.all(mx.isfinite(first.hidden))))
        self.assertGreater(float(mx.sum(mx.abs(first.hidden-hidden))), 0)
        second = _run(first.hidden, params, group_index=2)
        self.assertEqual((second.layer_start, second.layer_end), (4, 8))
        self.assertEqual(len(second.attention_caches), 4)
        self.assertTrue(bool(mx.all(mx.isfinite(second.hidden))))

    def test_causal_prefix_isolation_and_source_gradients(self):
        params = _params()
        hidden = mx.arange(4 * SPEC.width, dtype=mx.float32).reshape(
            1, 4, SPEC.width) / 1000
        future = mx.ones((1, 1, SPEC.width), dtype=mx.float32) * 100
        prefix = _run(hidden, params).hidden
        extended = _run(mx.concatenate((hidden, future), axis=1), params).hidden
        self.assertTrue(bool(mx.all(mx.abs(prefix-extended[:, :4]) < 1e-4)))
        def loss(input_hidden):
            return mx.sum(_run(input_hidden, params).hidden
                          * mx.arange(SPEC.width, dtype=mx.float32))
        derivative = mx.grad(loss)(hidden)
        self.assertTrue(bool(mx.all(mx.isfinite(derivative))))
        self.assertGreater(float(mx.sum(mx.abs(derivative))), 0)
        for name in ("blocks.0.query", "blocks.0.ffn_in"):
            with self.subTest(parameter=name):
                def parameter_loss(value):
                    changed = dict(params)
                    changed[name] = value
                    return mx.sum(_run(hidden, changed).hidden
                                  * mx.arange(
                                      SPEC.width, dtype=mx.float32))
                parameter_grad = mx.grad(parameter_loss)(params[name])
                self.assertTrue(bool(mx.all(mx.isfinite(parameter_grad))))
                self.assertGreater(
                    float(mx.sum(mx.abs(parameter_grad))), 0)

    def test_wrong_group_and_parameter_geometry_reject(self):
        params = _params()
        hidden = mx.zeros((1, 4, SPEC.width), dtype=mx.float32)
        with self.assertRaises(BilqisError):
            _run(hidden, params, group_index=0)
        with self.assertRaises(BilqisError):
            _run(hidden, params, group_index=4)
        with self.assertRaises(BilqisError):
            _run(hidden, {
                name: value for name, value in params.items()
                if name != "blocks.0.query"})
        wrong = dict(params)
        wrong["blocks.0.query"] = mx.zeros((1, 1), dtype=mx.float32)
        with self.assertRaises(BilqisError):
            _run(hidden, wrong)


if __name__ == "__main__":
    unittest.main()
