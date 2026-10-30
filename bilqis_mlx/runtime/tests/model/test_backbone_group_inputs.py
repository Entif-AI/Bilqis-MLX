"""B11.1a fixed group execution, without producer admission."""
from dataclasses import replace
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.backbone_group_numerical import (
    UnadmittedGroupNumerical, UnadmittedBackboneSession, run_backbone_group_numerical,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)


from bilqis_mlx.runtime.tests.model.test_backbone_group_numerical import _params, _run, SPEC

class BackboneInputTests(unittest.TestCase):
    def test_wrong_group_and_parameter_geometry_reject(self):
        params = _params()
        hidden = mx.zeros((1, 4, SPEC.width), dtype=mx.float32)
        with self.assertRaises(BilqisError):
            _run(hidden, params, group_index=0)
        with self.assertRaises(BilqisError):
            _run(hidden, params, group_index=4)
        with self.assertRaises(BilqisError):
            _run(hidden, {
                name: value for name, value in params.items()
                if name != "blocks.0.query"})
        wrong = dict(params)
        wrong["blocks.0.query"] = mx.zeros((1, 1), dtype=mx.float32)
        with self.assertRaises(BilqisError):
            _run(hidden, wrong)
