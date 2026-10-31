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

    def test_literal_fp32_oracle_and_normalized_source_weights(self):
        actual, alpha, gate = _depth_components(
            self.current, self.sources, self.features, self.params)
        expected, expected_alpha, expected_gate = _numpy_oracle(
            self.current, self.sources, self.features, self.params)
        np.testing.assert_allclose(np.asarray(actual), expected,
                                   atol=3e-6, rtol=3e-5)
        np.testing.assert_allclose(np.asarray(alpha), expected_alpha,
                                   atol=2e-6, rtol=3e-5)
        np.testing.assert_allclose(np.asarray(gate), expected_gate,
                                   atol=1e-7, rtol=1e-6)
        np.testing.assert_allclose(np.asarray(alpha).sum(axis=-1),
                                   np.ones((2, 3)), atol=1e-7)
        np.testing.assert_allclose(np.asarray(gate),
                                   np.full((2, 3, 1), 0.01), atol=1e-7)
        self.assertEqual(_depth_components(
            self.current, self.sources, self.features, self.params)[0].shape,
            (2, 3, 768))

    def test_completed_group_order_and_no_future_source_admission(self):
        for boundary in (1, 2, 3):
            sources = _summaries(boundary)
            features = _features(boundary)
            params = _params(boundary)
            actual, alpha, _ = _depth_components(
                self.current, sources, features, params)
            expected, _, _ = _numpy_oracle(
                self.current, sources, features, params)
            self.assertEqual(alpha.shape, (2, 3, boundary + 1))
            np.testing.assert_allclose(np.asarray(actual), expected,
                                       atol=3e-6, rtol=3e-5)
        baseline = _depth_components(
            self.current, self.sources, self.features, self.params)[0]
        unrelated_future = _summaries(3)[2].hidden.at[:].add(100)
        self.assertIsInstance(unrelated_future, mx.array)
        np.testing.assert_array_equal(
            np.asarray(_depth_components(
                self.current, self.sources, self.features, self.params)[0]),
            np.asarray(baseline))
        for invalid in (
            (self.sources[1], self.sources[0]),
            (*self.sources, _summaries(2)[2]),
        ):
            with self.assertRaises(BilqisError):
                _depth_components(self.current, invalid, self.features, self.params)

    def test_real_gradients_reach_shared_selector_and_boundary_gate(self):
        def objective(params):
            value = _depth_components(
                self.current, self.sources, self.features, params)[0]
            return mx.sum(value * value)
        gradients = mx.grad(objective)(self.params)
        for name in self.params:
            array = np.asarray(gradients[name])
            self.assertTrue(np.isfinite(array).all(), name)
            self.assertGreater(float(np.abs(array).sum()), 0, name)

    def test_nonzero_gradients_reach_all_completed_source_states(self):
        sources = _summaries(3)
        features = _features(3)
        params = _params(3)
        names = (("h0", 0), ("g1", 4), ("g2", 8), ("g3", 12))

        def objective(h0, g1, g2, g3):
            summaries = tuple(
                DepthSummary(name, layer, hidden)
                for (name, layer), hidden in zip(names, (h0, g1, g2, g3)))
            output = _depth_components(
                self.current, summaries, features, params)[0]
            return mx.sum(output * output)

        gradients = mx.grad(objective, argnums=(0, 1, 2, 3))(
            *(item.hidden for item in sources))
        for (name, _), gradient in zip(names, gradients):
            array = np.asarray(gradient)
            self.assertEqual(array.shape, (2, 3, 768))
            self.assertTrue(np.isfinite(array).all(), name)
            self.assertGreater(float(np.abs(array).sum()), 0, name)

    def test_invalid_tensor_shapes_dtype_source_order_and_release_fail_closed(self):
        for name, value in (
            ("query", mx.zeros((64, 768), dtype=mx.float32)),
            ("gate_bias", mx.zeros((2,), dtype=mx.float32)),
            ("norm", mx.zeros((768,), dtype=mx.float16)),
        ):
            malformed = dict(self.params)
            malformed[name] = value
            with self.subTest(name=name), self.assertRaises(BilqisError):
                _depth_components(self.current, self.sources, self.features, malformed)
        with self.assertRaises(BilqisError):
            _depth_components(self.current, self.sources, self.features,
                              {**self.params, "unexpected": mx.array([1.0])})
        with self.assertRaises(BilqisError):
            _depth_components(self.current, self.sources, self.features,
                              {key: value for key, value in self.params.items()
                               if key != "value"})
        for changes in (
            {"semantic_release": "not-a-release"},
            {"source_evidence_digest": "not-a-digest"},
        ):
            with self.assertRaises(BilqisError):
                replace(self.features, **changes)
        for changed in (
            replace(self.features, boundary_group=2),
            replace(self.features, type_role=mx.zeros((2, 3, 4))),
        ):
            with self.assertRaises(BilqisError):
                _depth_components(self.current, self.sources, changed, self.params)
        with self.assertRaises(BilqisError):
            DepthSummary("g2", 4, self.sources[0].hidden)

    def test_nonfinite_source_or_parameter_fails_before_residual_output(self):
        current_data = np.asarray(self.current).copy()
        current_data[0, 0, 0] = float("nan")
        poisoned_current = _array(current_data)
        with self.assertRaises(BilqisError):
            _depth_components(
                poisoned_current, self.sources, self.features, self.params)
        source_data = np.asarray(self.sources[1].hidden).copy()
        source_data[0, 0, 0] = float("inf")
        poisoned_source = replace(self.sources[1], hidden=_array(source_data))
        with self.assertRaises(BilqisError):
            _depth_components(
                self.current, (self.sources[0], poisoned_source),
                self.features, self.params)
        poisoned_params = dict(self.params)
        query_data = np.asarray(self.params["query"]).copy()
        query_data[0, 0] = float("inf")
        poisoned_params["query"] = _array(query_data)
        with self.assertRaises(BilqisError):
            _depth_components(
                self.current, self.sources, self.features, poisoned_params)

    def test_public_diagnostics_are_source_qualified_and_normalized(self):
        released = _released_features(1)
        extents = GenerationExtents(1, 1, "a"*64, "b"*64, released.features.digest)
        full = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
        full["depth.norm"] = mx.ones((768,), dtype=mx.float32)
        full["depth.gate.0.bias"] = _array([math.log(1/9)])
        view = depth_parameter_view(
            full, spec=ModelTopologySpecV2(), extents=extents, boundary_group=1)
        diagnostics = depth_select_with_diagnostics(
            self.current, self.sources, released, view)
        self.assertEqual(diagnostics.schema_version, "bilqis.mlx.depth-diagnostics/v1")
        self.assertEqual(diagnostics.alpha.shape, (2, 3, 2))
        np.testing.assert_allclose(
            np.asarray(diagnostics.alpha).sum(-1), np.ones((2, 3)), atol=1e-6)
        np.testing.assert_allclose(
            np.asarray(diagnostics.output),
            np.asarray(depth_select(self.current, self.sources, released, view)),
            atol=1e-6)
        with self.assertRaises(BilqisError):
            depth_select_with_diagnostics(
                self.current, self.sources, self.features, view)
