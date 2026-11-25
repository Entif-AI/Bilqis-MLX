import unittest
import numpy as np

from scripts.bamf.profiling.issue1645.frozen_geometry import summarize
from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES


class FrozenGeometryTests(unittest.TestCase):
    def test_separable_fixture_family_folds(self):
        bank = np.array([[1., 0.], [-1., 0.], [0., .1], [0., -.1]])
        rows = [{"row": {"capability": cap, "tokens": [label, family],
                         "gold": gold, "source_family_id": str(family)}}
                for cap in CAPABILITIES
                for family in (2, 3)
                for label, gold in ((0, "TRUE"), (1, "FALSE"))]
        result = summarize(bank, rows, 4)
        self.assertEqual(len(result["pairs"]), 15)
        for item in result["capabilities"].values():
            self.assertEqual(item["linear_probe"]["family_held_out_correct"], 4)
            self.assertEqual(item["linear_probe"]["family_held_out_total"], 4)
        self.assertIsNone(result["independent_learner_generalization"])
        rows[0]["row"]["tokens"] = [4]
        with self.assertRaisesRegex(ValueError, "outside catalog"):
            summarize(bank, rows, 4)
