"""Focused regressions for mixed v2 admission test support."""
from types import MappingProxyType
import unittest

import numpy as np

from bilqis_mlx.runtime.tests.admission.atlas.v2.mixed_source_support import (
    MixedSourceSupport,
)


class MixedSourceSupportTests(unittest.TestCase):
    def test_tree_prefix_accepts_immutable_mapping_trees(self):
        parent = MappingProxyType({
            "identity.bank.0": np.array([[1.0, 2.0]], dtype=np.float32),
        })
        child = MappingProxyType({
            "identity.bank.0": np.array(
                [[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
        })

        MixedSourceSupport.assert_tree_prefix(self, parent, child)


if __name__ == "__main__":
    unittest.main()
