"""Public B05 selectors cannot admit caller-minted backbone summaries."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import block_attnres
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.runtime.tests.depth.depth_helpers import (
    _hidden, _released_features, _summaries,
)


class PublicSelectorAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.current = _hidden([[1, 3, 2], [2, 4, 1]])
        self.features = _released_features(1)
        extents = GenerationExtents(
            1, 1, "a" * 64, "b" * 64, self.features.features.digest)
        parameters = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                      for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
        parameters["depth.norm"] = mx.ones((768,), dtype=mx.float32)
        self.view = block_attnres.depth_parameter_view(
            parameters, spec=ModelTopologySpecV2(), extents=extents, boundary_group=1)

    def test_public_paths_reject_g2_relabelled_as_g1_before_computation(self):
        sources = _summaries(3)
        forged = (sources[0], replace(sources[2], source_id="g1", completed_layer=4))
        self._assert_unadmitted(forged)

    def test_well_shaped_caller_summaries_do_not_establish_producer_authority(self):
        self._assert_unadmitted(_summaries(1))

    def test_reordered_and_future_sources_reject_before_computation(self):
        sources = _summaries(2)
        for changed in ((sources[1], sources[0]), sources):
            with self.subTest(source_ids=tuple(item.source_id for item in changed)):
                self._assert_unadmitted(changed)

    def _assert_unadmitted(self, summaries):
        for selector in (block_attnres.depth_select,
                         block_attnres.depth_select_with_diagnostics):
            with (self.subTest(selector=selector.__name__),
                  patch.object(block_attnres, "compose_factor_features",
                               wraps=block_attnres.compose_factor_features) as compose,
                  patch.object(block_attnres, "_depth_components",
                               wraps=block_attnres._depth_components) as compute):
                with self.assertRaises(BilqisError):
                    selector(self.current, summaries, self.features, self.view)
                compose.assert_not_called()
                compute.assert_not_called()
