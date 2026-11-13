"""B05.1 independent FP32 depth-selector oracle and boundary/gradient witnesses."""
from dataclasses import replace
import math
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_plasticity import AdapterParameters, adapter_forward
from bilqis_mlx.learning.frame_embeddings import FeatureRequest
from bilqis_mlx.learning.tests.test_frame_embeddings import _context_for
from bilqis_mlx.semantics.tests.test_atlas_features import _features as _atlas_features
from bilqis_mlx.semantics.frame_schema import ConceptRef
from bilqis_mlx.runtime.block_attnres import (
    DepthFrameFeatures, DepthParameterView, DepthSummary, PARAMETER_SHAPES,
    _DepthFeatureValues, _depth_components, _group_boundary_numerical,
    depth_parameter_view, depth_select, depth_select_with_diagnostics,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    initialize_bamf_parameter,
)


RELEASE = "a" * 64
EVIDENCE = "b" * 64

from bilqis_mlx.runtime.tests.depth.depth_helpers import (
    _array, _hidden, _params, _features, _released_features, _summaries, _numpy_oracle,
)

class DepthSelectionTests(unittest.TestCase):
    def setUp(self):
        self.current = _hidden([[1, 3, 2], [2, 4, 1]])
        self.params = _params()
        self.features = _features()
        self.sources = _summaries()

    def test_three_group_boundaries_capture_after_motif_and_adapt_after_selection(self):
        """Exercise all three groups with the exact post-layer4 motif ordering."""
        previous = (_summaries(1)[0],)
        current = self.current
        observed = []
        for group in (1, 2, 3):
            features, params = _features(group), _params(group)
            adapter = AdapterParameters(
                group - 1, mx.ones((768,), dtype=mx.float32),
                mx.full((8, 768), .025, dtype=mx.float32),
                mx.full((768, 8), .015, dtype=mx.float32))

            def second_read(value):
                observed.append(np.asarray(value).copy())
                return value + .35

            result = _group_boundary_numerical(
                current, previous, features, params, adapter,
                second_motif_read=second_read if group == 1 else None)
            post_read = current + .35 if group == 1 else current
            expected_capture = mx.fast.rms_norm(
                post_read, params["norm"], ModelTopologySpecV2.rms_norm_epsilon)
            np.testing.assert_allclose(
                np.asarray(result.captured.hidden),
                np.asarray(expected_capture), rtol=1e-6, atol=1e-6)
            selected, alpha, gate = _depth_components(
                post_read, (*previous, result.captured), features, params)
            np.testing.assert_allclose(
                np.asarray(result.selected), np.asarray(selected), atol=2e-6)
            np.testing.assert_allclose(
                np.asarray(result.adapted),
                np.asarray(adapter_forward(selected, adapter)), atol=2e-6)
            self.assertEqual(result.captured.source_id, f"g{group}")
            self.assertEqual(result.captured.completed_layer, group * 4)
            self.assertEqual(result.alpha.shape, (2, 3, group + 1))
            np.testing.assert_allclose(
                np.asarray(result.alpha).sum(-1), np.ones((2, 3)), atol=1e-6)
            np.testing.assert_allclose(
                np.asarray(result.alpha), np.asarray(alpha), atol=1e-6)
            np.testing.assert_allclose(
                np.asarray(result.gate), np.asarray(gate), atol=1e-6)
            previous = (*previous, result.captured)
            current = result.adapted + .05
        self.assertEqual(len(observed), 1)
        np.testing.assert_array_equal(observed[0], np.asarray(self.current))

    def test_group_boundary_gradient_and_invalid_order_fail_closed(self):
        features = _features(1)
        adapter = AdapterParameters(
            0, mx.ones((768,), dtype=mx.float32),
            mx.full((8, 768), .025, dtype=mx.float32),
            mx.full((768, 8), .015, dtype=mx.float32))
        previous = (_summaries(1)[0],)

        def objective(params, A, B):
            candidate = AdapterParameters(0, adapter.norm, A, B)
            result = _group_boundary_numerical(
                self.current, previous, features, params, candidate,
                second_motif_read=lambda value: value + .35)
            return mx.sum(result.adapted * result.adapted)

        gradients = mx.grad(objective, argnums=(0, 1, 2))(
            self.params, adapter.A, adapter.B)
        for label, grad in (("depth.query", gradients[0]["query"]),
                            ("adapter.A", gradients[1]),
                            ("adapter.B", gradients[2])):
            self.assertGreater(float(mx.sum(mx.abs(grad)).item()), 0, label)
        for motif_read in (None, lambda value: mx.zeros((1, 768))):
            with self.assertRaises(BilqisError):
                _group_boundary_numerical(
                    self.current, previous, features, self.params, adapter,
                    second_motif_read=motif_read)
        with self.assertRaises(BilqisError):
            _group_boundary_numerical(
                self.current, previous, _features(2), _params(2), adapter)
        with self.assertRaises(BilqisError):
            _group_boundary_numerical(
                self.current, previous, features, self.params,
                AdapterParameters(1, adapter.norm, adapter.A, adapter.B),
                second_motif_read=lambda value: value)
