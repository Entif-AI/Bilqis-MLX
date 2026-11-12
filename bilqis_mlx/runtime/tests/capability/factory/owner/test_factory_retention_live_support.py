"""Cheap initialization regressions for the real-source C05 live support."""
from types import SimpleNamespace
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.model_topology_v2 import (
    Initializer, ParameterGroup, ParameterSpec, initialize_bamf_parameter,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
    C05_GENESIS_SEED, _genesis_parameter,
)


class FactoryRetentionLiveSupportTests(unittest.TestCase):
    def test_genesis_preserves_identity_owner_and_uses_b01_for_model_tensor(self):
        identity = mx.array([[1.0, 2.0]], dtype=mx.float32)
        identity_spec = SimpleNamespace(
            name="identity.bank.fixture",
            shape=identity.shape,
            initializer=Initializer.IDENTITY_BANK,
        )
        self.assertIs(
            _genesis_parameter({identity_spec.name: identity}, identity_spec),
            identity,
        )

        readout = ParameterSpec(
            "readout.fixture", (2, 3), Initializer.MATRIX,
            ParameterGroup.SLOW, True,
        )
        actual = _genesis_parameter({}, readout)
        expected = initialize_bamf_parameter(readout, run_seed=C05_GENESIS_SEED)
        np.testing.assert_array_equal(np.asarray(actual), expected)
        self.assertFalse(bool(mx.all(actual == 0)))


if __name__ == "__main__":
    unittest.main()
