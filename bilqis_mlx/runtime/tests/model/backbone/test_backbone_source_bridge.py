"""Historical B11 source bridge remains numerical-only."""
import unittest
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.backbone_source_bridge import compute_compiled_h0
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2, GenerationExtents

class BackboneSourceBridgeTests(unittest.TestCase):
    def test_raw_hidden_cannot_enter_compiled_h0(self):
        with self.assertRaises(BilqisError):
            compute_compiled_h0(mx.zeros((1, 4, 768)), mx.zeros((1, 4, 768)), {},
                spec=ModelTopologySpecV2(),
                extents=GenerationExtents(1,1,"a"*64,"b"*64,"c"*64))

class AtomCustodyTests(unittest.TestCase):
    def test_raw_atom_vectors_are_not_a_production_credential(self):
        from bilqis_mlx.runtime.backbone_source_bridge import compute_compiled_h0_from_b01_source
        with self.assertRaises(BilqisError):
            compute_compiled_h0_from_b01_source(compiled=mx.zeros((1,4,768)),
                                                parameters={},banks=())
