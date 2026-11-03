"""Selection must reach the source-aware factor composer."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.runtime import depth_selection
from bilqis_mlx.runtime.block_attnres import depth_parameter_view
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.runtime.tests.depth.depth_helpers import _hidden, _released_features, _summaries
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection


class DepthSourceSelectionTests(TestCase):
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
