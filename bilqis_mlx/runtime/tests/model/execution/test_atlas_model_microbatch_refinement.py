"""#1236 batched B06 refinement parity witnesses."""
from __future__ import annotations

import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.atlas_refinement import _refine_frame, masked_routing_loss
from bilqis_mlx.runtime.autodiff_trace import defer_host_tensor_validation
from bilqis_mlx.runtime.microbatch.refinement_kernel import (
    _batched_refine_slot, batched_refinement_routing_loss,
)
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2


FP32_ATOL = 2e-5
FP32_RTOL = 3e-5


class MicrobatchRefinementKernelTests(unittest.TestCase):
    def _parameters(self):
        width, inner = ModelTopologySpecV2.width, 192
        return {
            "refine.norm": mx.ones((width,), dtype=mx.float32),
            "refine.query": mx.eye(inner, width, dtype=mx.float32) * 0.7,
            "refine.key": mx.eye(inner, width, dtype=mx.float32) * 0.8,
            "refine.value": mx.eye(inner, width, dtype=mx.float32) * 0.9,
            "refine.output": mx.eye(width, inner, dtype=mx.float32) * 0.6,
            "refine.gate_vector": mx.ones((width,), dtype=mx.float32) * 0.01,
            "refine.bias": mx.zeros((1,), dtype=mx.float32),
            "refine.route": mx.zeros((3, width), dtype=mx.float32),
            "refine.route_bias": mx.zeros((3,), dtype=mx.float32),
        }

    def _inputs(self):
        width, member_width = ModelTopologySpecV2.width, 3
        state = (mx.arange(3 * width, dtype=mx.float32)
                 .reshape(3, width) / 10000.0)
        seeds = mx.flip(state, axis=1) * 0.25
        role = mx.ones((3, width), dtype=mx.float32) * 0.02
        members = (mx.arange(3 * member_width * width, dtype=mx.float32)
                   .reshape(3, member_width, width) / 20000.0)
        counts = mx.array((2, 3, 1), dtype=mx.int32)
        passes = mx.array((0, 1, 2), dtype=mx.int32)
        return state, seeds, role, members, counts, passes

    def test_batched_refinement_matches_scalar_zero_one_two_pass_rows(self):
        params = self._parameters()
        state, seeds, role, members, counts, passes = self._inputs()

        def batched(values):
            return mx.sum(_batched_refine_slot(
                values, state, seeds, role, members, counts, passes))

        def scalar(values):
            total = mx.array(0.0, dtype=mx.float32)
            with defer_host_tensor_validation():
                for index, (member_count, pass_count) in enumerate(((2, 0), (3, 1), (1, 2))):
                    total = total + mx.sum(_refine_frame(
                        state[index], seeds[index], members[index, :member_count],
                        role[index], pass_count, values).hidden)
            return total

        batch_loss, batch_gradients = mx.value_and_grad(batched)(params)
        scalar_loss, scalar_gradients = mx.value_and_grad(scalar)(params)
        np.testing.assert_allclose(
            np.asarray(batch_loss), np.asarray(scalar_loss), atol=FP32_ATOL, rtol=FP32_RTOL)
        for name in params:
            with self.subTest(name=name):
                np.testing.assert_allclose(
                    np.asarray(batch_gradients[name]), np.asarray(scalar_gradients[name]),
                    atol=FP32_ATOL, rtol=FP32_RTOL)

    def test_batched_routing_loss_matches_scalar_per_row_mean(self):
        logits_one = mx.array((
            (0.2, 0.4, 0.1),
            (0.5, 0.1, 0.2),
            (0.3, 0.6, 0.4),
        ), dtype=mx.float32)
        logits_two = mx.array((
            (0.7, 0.2, 0.1),
            (0.2, 0.3, 0.8),
            (0.4, 0.1, 0.5),
        ), dtype=mx.float32)
        routing = (
            (logits_one, mx.array((0, 1, 2), dtype=mx.int32),
             mx.array((True, True, True), dtype=mx.bool_)),
            (logits_two, mx.array((2, 0, 1), dtype=mx.int32),
             mx.array((True, False, True), dtype=mx.bool_)),
        )

        observed = batched_refinement_routing_loss(routing, 3)
        expected = mx.stack((
            (masked_routing_loss(logits_one[0], 0)
             + masked_routing_loss(logits_two[0], 2)) / 2,
            masked_routing_loss(logits_one[1], 1),
            (masked_routing_loss(logits_one[2], 2)
             + masked_routing_loss(logits_two[2], 1)) / 2,
        ))
        np.testing.assert_allclose(
            np.asarray(observed), np.asarray(expected), atol=FP32_ATOL, rtol=FP32_RTOL)


if __name__ == "__main__":
    unittest.main()
