"""Local diagnostic witnesses, not evidence of trained competence."""
import unittest

from scripts.bamf.profiling.issue1645.geometry import interference, source_geometry
from scripts.bamf.profiling.issue1645.reservation import CAPABILITIES, digest
from scripts.bamf.profiling.issue1645.test_reservation import fixture


class GeometryTests(unittest.TestCase):
    def test_source_overlap_is_not_a_learned_representation_measurement(self):
        prepared = fixture()
        for entry in prepared["prospective"]["rows"]:
            row = entry["row"]
            row.update(record={"world": [0, 1]}, source_family_id="shared",
                       universe_size=2)
        prepared["prospective"]["sha256"] = digest(prepared["prospective"]["rows"])
        result = source_geometry(prepared)
        self.assertEqual(set(result["source"]), set(CAPABILITIES))
        self.assertEqual(len(result["pairs"]), 15)
        self.assertTrue(all(p["exact_world_overlap"] == 1 for p in result["pairs"]))
        self.assertIsNone(result["learned_representation_geometry"])
        self.assertIsNone(result["architectural_attainability"])
        self.assertIsNone(result["generalization"])

    def test_signed_actual_step_not_unsigned_gradient_overlap(self):
        result = interference({"A.PARENT": [1., 0.], "A.EDGE": [-1., 0.]},
                              {"A.IDENTITY": [.5, 0.]})
        self.assertEqual(result["A.IDENTITY->A.PARENT"], .5)
        self.assertEqual(result["A.IDENTITY->A.EDGE"], -.5)
        self.assertIsNone(result["A.MAPS->A.PARENT"])
        self.assertEqual(len(result), 36)
        with self.assertRaisesRegex(ValueError, "unmatched"):
            interference({"A.PARENT": [1.]}, {"A.IDENTITY": [1., 2.]})


if __name__ == "__main__":
    unittest.main()
