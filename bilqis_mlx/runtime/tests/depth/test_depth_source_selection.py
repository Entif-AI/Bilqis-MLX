"""Selection must reach the source-aware factor composer."""
from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.runtime import depth_selection
from bilqis_mlx.runtime.block_attnres import DepthSummary, depth_parameter_view
from bilqis_mlx.learning.source_atoms.backbone import _SourceBackboneProducerSession
import bilqis_mlx.runtime.depth_contracts as depth_contracts
from bilqis_mlx.learning.frame_embeddings import FrameFactorTerms
from bilqis_mlx.learning.frame_encoder import FrameEncoding
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.runtime.tests.depth.depth_helpers import _hidden, _released_features, _summaries
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection


class DepthSourceSelectionTests(TestCase):
    def test_trace_summaries_normalize_each_completed_boundary_once(self):
        spec = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "c" * 64)
        parameters = {
            item.name: mx.zeros(item.shape, dtype=mx.float32)
            for item in expected_bamf_shapes(spec, extents)
        }
        binding = object()
        views = tuple(
            depth_parameter_view(
                parameters, spec=spec, extents=extents, boundary_group=group)
            for group in (1, 2, 3)
        )
        for view in views:
            object.__setattr__(view, "_execution_binding", binding)
        producer = object.__new__(_SourceBackboneProducerSession)
        producer._trace = True
        producer._execution_binding = binding
        producer._generation = "generation"
        producer._trace_boundaries = tuple(
            mx.full((1, 1, spec.width), float(index), dtype=mx.float32)
            for index in range(4)
        )

        original = depth_selection._rms_norm
        with (
            patch.object(
                depth_contracts, "require_execution_generation_binding",
                return_value=SimpleNamespace(
                    generation_digest="generation",
                    parameter_tree_digest="tree")),
            patch.object(depth_selection, "_rms_norm", wraps=original) as norm,
        ):
            for boundary, view in enumerate(views, 1):
                depth_selection._producer_summaries(producer, boundary, view)

        self.assertEqual(norm.call_count, 3)

    def test_trace_source_type_role_tensor_is_built_once(self):
        spec = ModelTopologySpecV2()
        extents = GenerationExtents(1, 1, "a" * 64, "b" * 64, "d" * 64)
        parameters = {
            item.name: mx.zeros(item.shape, dtype=mx.float32)
            for item in expected_bamf_shapes(spec, extents)
        }
        factor = FrameFactorTerms(
            mx.zeros((128,), dtype=mx.float32),
            mx.zeros((128,), dtype=mx.float32),
            mx.ones((spec.width,), dtype=mx.float32),
            (),
            "d" * 64,
            "a" * 64,
        )
        encoded = FrameEncoding(
            mx.zeros((1, 2, spec.width), dtype=mx.float32),
            ((),),
            ((None, None),),
            ((factor, factor),),
        )
        producer = object.__new__(_SourceBackboneProducerSession)
        producer._trace = True
        producer._encoded = encoded
        producer._compiled = SimpleNamespace(
            features=SimpleNamespace(
                digest="d" * 64,
                semantic_release="a" * 64))
        current = mx.zeros((1, 2, spec.width), dtype=mx.float32)
        summaries = (
            DepthSummary("h0", 0, current),
            DepthSummary("g1", 4, current),
        )
        view = depth_parameter_view(
            parameters, spec=spec, extents=extents, boundary_group=1)
        output = mx.zeros_like(current)
        alpha = mx.zeros((1, 2, 2), dtype=mx.float32)
        gate = mx.zeros((1, 2, 1), dtype=mx.float32)

        original_stack = depth_selection.mx.stack
        with (
            patch.object(
                depth_selection, "_producer_summaries",
                return_value=(summaries, current)),
            patch.object(
                depth_selection, "_depth_components",
                return_value=(output, alpha, gate)),
            patch.object(depth_selection.mx, "stack", wraps=original_stack) as stack,
        ):
            for _ in range(3):
                depth_selection.source_depth_select_with_diagnostics(producer, view)

        self.assertEqual(stack.call_count, 2)

    def test_public_selectors_keep_pickle_identities(self):
        import pickle
        from bilqis_mlx.runtime import block_attnres
        for name in ('depth_select', 'depth_select_with_diagnostics'):
            with self.subTest(name=name):
                value = getattr(block_attnres, name)
                expected = ('cbilqis_mlx.runtime.block_attnres\n' + name + '\np0\n.').encode()
                self.assertIs(pickle.loads(expected), value)
                self.assertEqual(pickle.dumps(value, protocol=0), expected)

    def test_selection_reaches_composer(self):
        released = _released_features()
        selection = AtlasArtifactSelection('/unused', '1' * 64, '2' * 64, '3' * 64)
        released = replace(released, atlas_selection=selection)
        extents = GenerationExtents(1, 1, 'a' * 64, 'b' * 64, released.features.digest)
        params = {item.name: mx.zeros(item.shape) for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
        view = depth_parameter_view(params, spec=ModelTopologySpecV2(), extents=extents, boundary_group=1)
        with patch.object(depth_selection, 'compose_factor_features', wraps=depth_selection.compose_factor_features) as compose:
            depth_selection._numerical_depth_select(_hidden([[1, 3, 2], [2, 4, 1]]), _summaries(), released, view)
        self.assertTrue(compose.call_args_list)
        self.assertTrue(all(call.kwargs['atlas_selection'] is selection for call in compose.call_args_list))
