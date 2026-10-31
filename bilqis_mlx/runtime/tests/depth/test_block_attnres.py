"""Structural test shard from test_block_attnres.py; assertions preserved."""
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
from bilqis_mlx.runtime.tests.depth.test_block_attnres_helpers import (_array, _features, _hidden, _numpy_oracle, _params, _released_features, _summaries)

class DepthSelectionTests(unittest.TestCase):
        def setUp(self):
            self.current = _hidden([[1, 3, 2], [2, 4, 1]])
            self.params = _params()
            self.features = _features()
            self.sources = _summaries()

        def test_public_depth_features_are_recomputed_from_actual_released_source_members(self):
            released = _released_features()
            features = released.features
            extents = GenerationExtents(1, 1, "a"*64, "b"*64, features.digest)
            full = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                    for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
            for local, value in self.params.items():
                path = {"gate_vector": "depth.gate.0.vector", "gate_bias": "depth.gate.0.bias"}.get(local, "depth."+local)
                full[path] = value
            for group in range(3):
                full[f"depth.gate.{group}.bias"] = _array([math.log(1/9)])
            full["features.role"] = full["features.role"].at[2, 0].add(1).at[3, 0].add(2)
            full["features.project_role"] = full["features.project_role"].at[0, 0].add(1)
            full["features.type"] = full["features.type"].at[2, 0].add(.25)
            full["features.project_type"] = full["features.project_type"].at[1, 0].add(1)
            full["features.gates"] = mx.full((4,), -2, dtype=mx.float32)
            type_role = (mx.zeros((2, 3, 768), dtype=mx.float32).at[:, :, 0].add(1.5/(1+math.exp(2)))
                         .at[:, :, 1].add(.25/(1+math.exp(2))))
            for group in (1, 2, 3):
                view = depth_parameter_view(full, spec=ModelTopologySpecV2(), extents=extents, boundary_group=group)
                sources = _summaries(group)
                actual = depth_select(self.current, sources, replace(released, boundary_group=group), view)
                numerical = replace(self.features, frame_seed=sources[0].hidden, type_role=type_role, boundary_group=group)
                expected, _, _ = _numpy_oracle(self.current, sources, numerical, self.params)
                np.testing.assert_allclose(np.asarray(actual), expected, atol=3e-6, rtol=3e-5)
                self.assertGreater(float(mx.sum(mx.abs(actual-self.current)).item()), 0)
            def objective(parameters):
                local = depth_parameter_view(parameters, spec=ModelTopologySpecV2(), extents=extents, boundary_group=1)
                output = depth_select(self.current, self.sources, released, local)
                return mx.sum(output*output)
            gradients = mx.grad(objective)(full)
            for path in ("features.type", "features.role", "features.project_type", "features.project_role", "features.gates"):
                self.assertGreater(float(mx.sum(mx.abs(gradients[path])).item()), 0, path)
            with self.assertRaises(BilqisError):
                depth_select(self.current, self.sources, self.features, view)
            with self.assertRaises(BilqisError):
                replace(released, requests=((released.requests[0][0][:1],),))

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
