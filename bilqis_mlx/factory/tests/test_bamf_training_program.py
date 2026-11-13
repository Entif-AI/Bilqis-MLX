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
            ("positive-identity", "boolean", "numeric"),
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


    def test_public_constructors_reject_mutable_collections(self):
        from bilqis_mlx.factory.curriculum.developmental_program import (
            BamfDevelopmentalProgram, DevelopmentalDomainProgram, SCHEMA)

        with self.assertRaises(BilqisError):
            DevelopmentalDomainProgram(
                DevelopmentalLevel.L0, "bad", ["numeric"],
                ("POSITIVE_IDENTITY",), ("ADMITTED_RELEASE",))
        level = load_bamf_developmental_program().levels[0]
        with self.assertRaises(BilqisError):
            BamfDevelopmentalProgram(SCHEMA, "bad", "v1", [level])

    def test_default_manifest_is_packaged_and_operator_path_is_same_data(self):
        from importlib import resources
        from bilqis_mlx.factory.curriculum import developmental_program as owner

        packaged = resources.files(owner.__package__).joinpath(
            owner.DEFAULT_PROGRAM_RESOURCE).read_bytes()
        operator_path = (Path(__file__).resolve().parents[3] / "configs" /
                         "curricula" / "bamf-developmental-v1.json")
        self.assertEqual(operator_path.read_bytes(), packaged)
        self.assertIn(b'"numeric"', packaged)

    def test_malformed_json_collection_shape_fails_typed_boundary(self):
        path = Path(__file__).resolve().parents[3] / "configs" / "curricula" / "bamf-developmental-v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["levels"][0]["domains"] = "numeric"
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "program.json"
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(BilqisError):
                load_bamf_developmental_program(candidate)

    def test_invalid_utf8_fails_through_typed_error_bus(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "program.json"
            candidate.write_bytes(b"\xff\xfe\xfd")
            with self.assertRaises(BilqisError) as caught:
                load_bamf_developmental_program(candidate)
        self.assertIn("FACTORY.DEVELOPMENTAL_PROGRAM.INVALID", str(caught.exception))

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
