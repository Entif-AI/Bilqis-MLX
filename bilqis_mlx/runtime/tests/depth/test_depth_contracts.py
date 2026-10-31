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

    def test_depth_view_borrows_exact_shared_and_per_boundary_b01_tensors(self):
        spec = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, _atlas_features().digest)
        ledger = expected_bamf_shapes(spec, extents)
        parameters = {
            item.name: mx.zeros(item.shape, dtype=mx.float32)
            for item in ledger
        }
        parameters["depth.norm"] = mx.ones((768,), dtype=mx.float32)
        for index in range(3):
            parameters[f"depth.gate.{index}.bias"] = _array([math.log(1 / 9)])
        views = tuple(depth_parameter_view(
            parameters, spec=spec, extents=extents, boundary_group=group)
            for group in (1, 2, 3))
        self.assertEqual(len(parameters), len(ledger))
        for group, view in enumerate(views, 1):
            self.assertEqual(set(view), set(PARAMETER_SHAPES))
            for name in ("norm", "query", "key", "value", "output"):
                self.assertIs(view[name], parameters[f"depth.{name}"])
            self.assertIs(view["gate_vector"],
                          parameters[f"depth.gate.{group - 1}.vector"])
            self.assertIs(view["gate_bias"],
                          parameters[f"depth.gate.{group - 1}.bias"])
            self.assertNotIn("features.norm", view)
            self.assertNotIn("blocks.0.query", view)
            output = depth_select(
                self.current, _summaries(group), _released_features(group), view)
            np.testing.assert_array_equal(
                np.asarray(output), np.asarray(self.current))

    def test_depth_view_rejects_wrong_full_ledger_or_boundary(self):
        spec = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
        parameters = {
            item.name: mx.zeros(item.shape, dtype=mx.float32)
            for item in expected_bamf_shapes(spec, extents)
        }
        for change in (
            {"depth.query": None},
            {"depth.gate.1.bias": mx.zeros((2,), dtype=mx.float32)},
            {"features.norm": mx.zeros((768,), dtype=mx.float16)},
            {"unexpected.tensor": mx.zeros((1,), dtype=mx.float32)},
        ):
            malformed = dict(parameters)
            malformed.update(change)
            if "depth.query" in change:
                malformed.pop("depth.query")
            with self.subTest(change=tuple(change)), self.assertRaises(BilqisError):
                depth_parameter_view(
                    malformed, spec=spec, extents=extents, boundary_group=2)
        for invalid in (-1, 0, 4, True):
            with self.assertRaises(BilqisError):
                depth_parameter_view(
                    parameters, spec=spec, extents=extents,
                    boundary_group=invalid)

    def test_public_selector_rejects_anonymous_or_cross_boundary_weights(self):
        with self.assertRaises(BilqisError):
            depth_select(
                self.current, self.sources, self.features, self.params)
        with self.assertRaises(BilqisError):
            DepthParameterView(self.params, 1, object())
        spec = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
        parameters = {
            item.name: mx.zeros(item.shape, dtype=mx.float32)
            for item in expected_bamf_shapes(spec, extents)
        }
        view = depth_parameter_view(
            parameters, spec=spec, extents=extents, boundary_group=2)
        with self.assertRaises(BilqisError):
            depth_select(
                self.current, self.sources, self.features, view)
        with self.assertRaises(TypeError):
            view._tensors["query"] = view["key"]
        with self.assertRaises(BilqisError):
            replace(view, _tensors={**view, "query": view["key"]})
