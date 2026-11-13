"""C14 developmental-program data contract."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.curriculum.developmental_program import (
    DevelopmentalLevel,
    load_bamf_developmental_program,
)


class BamfTrainingProgramTests(unittest.TestCase):
    def test_declares_constructive_l0_and_released_l1_l2_programs(self):
        program = load_bamf_developmental_program()

        self.assertEqual(
            tuple(item.level.value for item in program.levels),
            ("L0", "L1", "L2", "L3", "L4"),
        )
        self.assertEqual(
            program.require_level("L0").domains,
            ("positive-identity", "boolean", "integer"),
        )
        self.assertEqual(
            program.require_level("L0").constructive_steps,
            ("POSITIVE_IDENTITY", "DIRECT_CONSTITUENTS", "LAWFUL_COMPOSITION"),
        )
        self.assertEqual(
            program.require_level("L1").domains,
            ("skos-roles", "skos-senses", "skos-morphology",
             "bravo-category-frames", "bravo-time-frames"),
        )
        self.assertEqual(
            program.require_level("L2").domains,
            ("new-concepts", "ambiguity", "relations", "cross-family-composition"),
        )
        self.assertIn("ADMITTED_RELEASE", program.require_level("L1").source_requirements)
        self.assertIn("ADMITTED_RELEASE", program.require_level("L2").source_requirements)

    def test_l3_is_optional_and_l4_packages_bounded_capabilities(self):
        program = load_bamf_developmental_program()

        self.assertTrue(program.require_level(DevelopmentalLevel.L3).optional)
        self.assertFalse(program.require_level("L3").packages_bounded_capabilities)
        self.assertTrue(program.require_level("L4").packages_bounded_capabilities)
        self.assertIn("RESOURCE_AUTHORITY", program.require_level("L3").source_requirements)
        self.assertIn("RIGHTS_AUTHORITY", program.require_level("L4").source_requirements)

    def test_program_and_levels_are_immutable_and_digest_is_stable(self):
        first = load_bamf_developmental_program()
        second = load_bamf_developmental_program()

        self.assertEqual(first.digest(), second.digest())
        with self.assertRaises(FrozenInstanceError):
            first.program_id = "other"
        with self.assertRaises(FrozenInstanceError):
            first.levels[0].purpose = "other"

    def test_invalid_level_order_fails_through_typed_error_bus(self):
        path = Path(__file__).resolve().parents[3] / "configs" / "curricula" / "bamf-developmental-v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["levels"][0], payload["levels"][1] = payload["levels"][1], payload["levels"][0]
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "program.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(BilqisError) as caught:
                load_bamf_developmental_program(candidate)
        self.assertIn("FACTORY.DEVELOPMENTAL_PROGRAM.INVALID", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
