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


def _array(values):
    return mx.array(np.asarray(values, dtype=np.float32))


def _hidden(values):
    values = np.asarray(values, dtype=np.float32)
    hidden = np.zeros((*values.shape, 768), dtype=np.float32)
    hidden[..., 0] = values
    hidden[..., 1] = values * 0.5 + 1
    hidden[..., 2] = values * -0.25 + 2
    return _array(hidden)


def _params(boundary=1):
    rng = np.random.default_rng(451)
    spec = ModelTopologySpecV2()
    extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
    ledger = {row.name: row for row in expected_bamf_shapes(spec, extents)}
    parameters = {
        "norm": _array(initialize_bamf_parameter(
            ledger["depth.norm"], run_seed=0)),
        "gate_vector": _array(initialize_bamf_parameter(
            ledger[f"depth.gate.{boundary - 1}.vector"], run_seed=0)),
        "gate_bias": _array(initialize_bamf_parameter(
            ledger[f"depth.gate.{boundary - 1}.bias"], run_seed=0)),
    }
    for name in ("query", "key", "value", "output"):
        shape = ledger[f"depth.{name}"].shape
        parameters[name] = _array(rng.normal(0, 0.1, shape))
    return parameters


def _features(boundary=1):
    return _DepthFeatureValues(
        _hidden([[0.1, 0.2, 0.3], [0.2, 0.1, 0.4]]),
        _hidden([[0.3, 0.1, 0.2], [0.2, 0.4, 0.1]]),
        RELEASE, EVIDENCE, boundary)


def _released_features(boundary=1):
    features = _atlas_features()
    ref = ConceptRef("urn:concept:A", features.semantic_release, 11,
                     ("urn:type:Entity",), "fixture:source")
    requests = []
    for batch in range(2):
        row = []
        for position in range(3):
            context = _context_for(ref, f"fixture:depth:{batch}:{position}")
            row.append(tuple(FeatureRequest.from_context(context, "frame:0", "source:member:"+role)
                             for role in ("left", "right")))
        requests.append(tuple(row))
    return DepthFrameFeatures(tuple(requests), features, boundary)


def _summaries(boundary=1):
    values = (
        _hidden([[1, 2, 3], [2, 3, 1]]),
        _hidden([[3, 1, 2], [1, 2, 4]]),
        _hidden([[2, 4, 1], [4, 1, 2]]),
        _hidden([[4, 3, 2], [2, 1, 3]]),
    )
    return tuple(
        DepthSummary(name, layer, values[index])
        for index, (name, layer) in enumerate(
            (("h0", 0), ("g1", 4), ("g2", 8), ("g3", 12))
        ) if index <= boundary)


def _numpy_oracle(current, summaries, features, params):
    """Independent NumPy FP32 implementation, not a call to the MLX selector."""
    h = np.asarray(current)
    gamma = np.asarray(params["norm"])
    seed = np.asarray(features.frame_seed)
    types = np.asarray(features.type_role)
    q_weight = np.asarray(params["query"])
    k_weight = np.asarray(params["key"])
    v_weight = np.asarray(params["value"])
    out_weight = np.asarray(params["output"])
    gate_vector = np.asarray(params["gate_vector"])
    gate_bias = float(np.asarray(params["gate_bias"])[0])

    def rms(values):
        return values / np.sqrt(np.mean(values * values, axis=-1, keepdims=True)
                                + np.float32(1e-5)) * gamma

    q = rms(h + seed) @ q_weight.T
    sources = [np.asarray(item.hidden) for item in summaries]
    keys = np.stack([rms(item + types) @ k_weight.T for item in sources], axis=2)
    values = np.stack([item @ v_weight.T for item in sources], axis=2)
    scores = np.sum(q[:, :, None] * keys, axis=-1) / np.float32(np.sqrt(128))
    weights = np.exp(scores - scores.max(axis=-1, keepdims=True))
    weights /= weights.sum(axis=-1, keepdims=True)
    mix = np.sum(weights[:, :, :, None] * values, axis=2)
    logits = np.sum(rms(h) * gate_vector, axis=-1, keepdims=True) + gate_bias
    gate = np.float32(0.1) / (1 + np.exp(-logits))
    return h + gate * (mix @ out_weight.T), weights, gate


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


if __name__ == "__main__":
    unittest.main()
