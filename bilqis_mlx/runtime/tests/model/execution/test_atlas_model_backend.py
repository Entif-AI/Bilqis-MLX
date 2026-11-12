"""B11 backend contract tests."""
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_model import Backend, model_backend
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2


class AtlasModelBackendTests(unittest.TestCase):
    def test_model_backend_preserves_one_fp32_topology_contract(self):
        spec = ModelTopologySpecV2()
        backend = model_backend(spec)
        self.assertIs(type(backend), Backend)
        self.assertEqual(backend.topology, spec)
        self.assertEqual(backend.precision, "FP32")
        self.assertTrue(backend.device)
        with self.assertRaises(BilqisError):
            Backend(spec, backend.device, precision="BF16")
        with self.assertRaises(BilqisError):
            model_backend(object())
