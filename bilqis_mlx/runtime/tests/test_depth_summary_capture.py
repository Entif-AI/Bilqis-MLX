"""B05.4 process-local summary custody and relabel/cross-boundary negatives."""
from __future__ import annotations

from dataclasses import replace
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.block_attnres import depth_parameter_view, depth_select
from bilqis_mlx.runtime.depth_summary_capture import (
    _begin_backbone_capture, SealedDepthSummary,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.runtime.tests.test_block_attnres import (
    _hidden, _params, _released_features, _summaries,
)


def _fixture():
    spec = ModelTopologySpecV2()
    features = _released_features()
    extents = GenerationExtents(
        1, 1, "a" * 64, "b" * 64, features.features.digest)
    parameters = {
        item.name: mx.zeros(item.shape, dtype=mx.float32)
        for item in expected_bamf_shapes(spec, extents)
    }
    for local, value in _params().items():
        path = {
            "gate_vector": "depth.gate.0.vector",
            "gate_bias": "depth.gate.0.bias",
        }.get(local, "depth." + local)
        parameters[path] = value
    capture = _begin_backbone_capture(
        parameters, spec=spec, extents=extents,
        generation_digest="d" * 64, implementation_digest="e" * 64,
        prediction_digest="f" * 64, feature_digest=features.features.digest)
    for item in _summaries(3):
        capture.capture(item.hidden)
    view = depth_parameter_view(
        parameters, spec=spec, extents=extents, boundary_group=1)
    current = _hidden([[1, 3, 2], [2, 4, 1]])
    return capture, view, features, current, parameters, extents


class DepthSummaryCaptureTests(unittest.TestCase):
    def test_exact_completed_prefix_is_accepted(self):
        capture, view, features, current, _, _ = _fixture()
        self.assertEqual(
            tuple(item.source_id for item in capture.available(3)),
            ("h0", "g1", "g2", "g3"))
        output = depth_select(
            current, capture.available(1), features, view)
        self.assertEqual(output.shape, current.shape)

    def test_g2_to_g1_relabel_and_copy_cannot_mint_custody(self):
        capture, view, features, current, _, _ = _fixture()
        h0, g1, g2 = capture.available(2)
        relabelled = replace(
            g2, source_id="g1", completed_layer=4,
            provenance=replace(
                g2.provenance, source_id="g1", completed_layer=4,
                prefix_order=("h0", "g1"),
                prior_summary_digest=h0.provenance.digest))
        for candidate in (relabelled, replace(g1)):
            with self.assertRaises(BilqisError):
                depth_select(current, (h0, candidate), features, view)
        with self.assertRaises(BilqisError):
            depth_select(current, (g1, h0), features, view)

    def test_cross_prediction_and_generation_receipts_do_not_mix(self):
        capture, view, features, current, parameters, extents = _fixture()
        for generation, prediction in (("9" * 64, "f" * 64),
                                       ("d" * 64, "9" * 64)):
            other = _begin_backbone_capture(
                parameters, spec=ModelTopologySpecV2(), extents=extents,
                generation_digest=generation,
                implementation_digest="e" * 64,
                prediction_digest=prediction,
                feature_digest=features.features.digest)
            for item in _summaries(1):
                other.capture(item.hidden)
            with self.assertRaises(BilqisError):
                depth_select(
                    current,
                    (capture.available(1)[0], other.available(1)[1]),
                    features, view)

    def test_cross_parameter_tree_and_future_boundary_reject(self):
        capture, view, features, current, parameters, extents = _fixture()
        altered = dict(parameters)
        altered["depth.query"] = mx.zeros(
            (128, 768), dtype=mx.float32)
        other_view = depth_parameter_view(
            altered, spec=ModelTopologySpecV2(),
            extents=extents, boundary_group=1)
        with self.assertRaises(BilqisError):
            depth_select(current, capture.available(1), features, other_view)
        with self.assertRaises(BilqisError):
            depth_select(
                current, (capture.available(2)[0], capture.available(2)[2]),
                features, view)
        with self.assertRaises(BilqisError):
            capture.available(4)

    def test_mutated_hidden_receipt_and_raw_summary_reject(self):
        capture, view, features, current, _, _ = _fixture()
        h0, g1 = capture.available(1)
        forged = replace(
            g1, hidden=g1.hidden.at[0, 0, 0].add(1))
        with self.assertRaises(BilqisError):
            depth_select(current, (h0, forged), features, view)
        with self.assertRaises(BilqisError):
            SealedDepthSummary(
                "g1", 4, g1.hidden, g1.provenance,
                "caller-minted", object())
        self.assertIsInstance(g1, SealedDepthSummary)
        np.testing.assert_array_equal(
            np.asarray(g1.hidden), np.asarray(_summaries(1)[1].hidden))

    def test_public_sealed_capture_preserves_source_state_gradients(self):
        _, view, features, current, parameters, extents = _fixture()
        source_h0, source_g1 = (
            item.hidden for item in _summaries(1))

        def objective(h0, g1):
            capture = _begin_backbone_capture(
                parameters, spec=ModelTopologySpecV2(), extents=extents,
                generation_digest="d" * 64, implementation_digest="e" * 64,
                prediction_digest="f" * 64,
                feature_digest=features.features.digest)
            capture.capture(h0)
            capture.capture(g1)
            output = depth_select(
                current, capture.available(1), features, view)
            return mx.sum(output * output)

        gradients = mx.grad(objective, argnums=(0, 1))(
            source_h0, source_g1)
        for gradient in gradients:
            array = np.asarray(gradient)
            self.assertTrue(np.isfinite(array).all())
            self.assertGreater(float(np.abs(array).sum()), 0)


if __name__ == "__main__":
    unittest.main()
