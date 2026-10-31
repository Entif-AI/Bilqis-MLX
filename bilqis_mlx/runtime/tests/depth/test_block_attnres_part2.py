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
