"""Focused regressions for mixed v2 admission test support."""
from types import MappingProxyType
import unittest

import numpy as np

from bilqis_mlx.runtime.tests.admission.atlas.v2.mixed_source_support import (
    MixedSourceSupport,
)
from bilqis_mlx.source_adapters import event_frames


class MixedSourceSupportTests(unittest.TestCase):
    def test_common_atlas_keeps_repeated_event_targets_parameter_only(self):
        snapshot, *_ = MixedSourceSupport().common_atlas()
        targets = {
            event_frames.atlas_semantic_id("D.EVENT_OCCURRENCE"),
            event_frames.atlas_semantic_id("D.COMMENCEMENT"),
        }
        actual = {
            item.concept.semantic_id: tuple(item.concept.types)
            for item in snapshot.concepts
            if item.concept.semantic_id in targets
        }

        self.assertEqual(actual, {semantic_id: () for semantic_id in targets})

    def test_tree_prefix_accepts_immutable_mapping_trees(self):
        parent = MappingProxyType({
            "identity.bank.0": np.array([[1.0, 2.0]], dtype=np.float32),
        })
        child = MappingProxyType({
            "identity.bank.0": np.array(
                [[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
        })

        MixedSourceSupport.assert_tree_prefix(self, parent, child)

    def test_tree_prefix_allows_only_declared_new_semantic_rows_to_change(self):
        parent = MappingProxyType({
            "identity.bank.0": np.array(
                [[1.0, 2.0], [0.0, 0.0], [5.0, 6.0]], dtype=np.float32),
        })
        child = MappingProxyType({
            "identity.bank.0": np.array(
                [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=np.float32),
        })

        MixedSourceSupport.assert_tree_prefix(
            self, parent, child,
            mutable_rows_by_key={"identity.bank.0": (1,)})

        corrupted = MappingProxyType({
            "identity.bank.0": np.array(
                [[9.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=np.float32),
        })
        with self.assertRaises(AssertionError):
            MixedSourceSupport.assert_tree_prefix(
                self, parent, corrupted,
                mutable_rows_by_key={"identity.bank.0": (1,)})


if __name__ == "__main__":
    unittest.main()
