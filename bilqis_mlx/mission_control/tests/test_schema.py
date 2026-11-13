"""Machine-readable shape coverage for the entire CP02 record registry."""
import json
from pathlib import Path
import unittest

from bilqis_mlx.mission_control.codec import encode_record
from bilqis_mlx.mission_control.registry import ALL_RECORD_TYPES
from bilqis_mlx.mission_control.schema import JSON_SCHEMA_DIALECT, schema_bundle
from bilqis_mlx.mission_control.tests.samples import SAMPLES


class MissionControlSchemaTests(unittest.TestCase):
    def test_bundle_has_one_unique_versioned_shape_per_registered_record(self):
        bundle = schema_bundle()
        expected = {record_type.SCHEMA for record_type in ALL_RECORD_TYPES}
        self.assertEqual(set(bundle["records"]), expected)
        self.assertEqual(len(expected), len(ALL_RECORD_TYPES))
        for record_type in ALL_RECORD_TYPES:
            with self.subTest(schema=record_type.SCHEMA):
                schema = bundle["records"][record_type.SCHEMA]
                self.assertEqual(schema["$schema"], JSON_SCHEMA_DIALECT)
                self.assertEqual(schema["$id"], record_type.SCHEMA)
                self.assertEqual(
                    schema["properties"]["schema_version"]["const"],
                    record_type.SCHEMA,
                )
                self.assertFalse(schema["additionalProperties"])
                json.dumps(schema, sort_keys=True)

    def test_schema_required_keys_match_literal_wire_records(self):
        bundle = schema_bundle()["records"]
        for sample in SAMPLES:
            with self.subTest(schema=sample.schema_version):
                self.assertEqual(
                    set(bundle[sample.schema_version]["required"]),
                    set(encode_record(sample)),
                )

    def test_checked_in_schema_bundle_is_the_generated_projection(self):
        path = Path(__file__).parents[1] / "schemas" / "mission-control-v1.schema.json"
        expected = (
            json.dumps(schema_bundle(), indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        self.assertEqual(path.read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
