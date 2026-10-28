from __future__ import annotations

import json
from pathlib import Path
import unittest

from lib.ithkuil.src.skos.coverage_schema import (
    SCHEMA_ID,
    coverage_receipt_json_bytes,
    validate_coverage_receipt,
)
from lib.ithkuil.src.skos.errors import ProfileError


FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID = json.loads((FIXTURES / "coverage_valid.json").read_text(encoding="utf-8"))
INVALID = {
    "coverage_invalid_missing_input_digest.json": "COVERAGE_INPUT_FIELD_MISSING",
    "coverage_invalid_rdf_digest.json": "COVERAGE_DIGEST_INVALID",
    "coverage_invalid_totals.json": "COVERAGE_GLOBAL_TOTAL_MISMATCH",
    "coverage_invalid_status.json": "COVERAGE_DISPOSITION_ENUM_INVALID",
    "coverage_invalid_frontier_debt.json": "COVERAGE_TOP_LEVEL_FIELD_MISSING",
}


class CoverageSchemaTests(unittest.TestCase):
    def test_complete_fixture_validates_and_serializes_stably(self):
        self.assertIs(validate_coverage_receipt(VALID), VALID)
        payload = coverage_receipt_json_bytes(VALID)
        self.assertEqual(payload, coverage_receipt_json_bytes(VALID))
        parsed = json.loads(payload)
        self.assertEqual(parsed["schema"], SCHEMA_ID)
        self.assertEqual(parsed["totals"]["source_rows"], 10)
        self.assertEqual(
            parsed["totals"]["dispositions"],
            {"EMITTED": 5, "HELD": 2, "REJECTED": 1, "UNSUPPORTED": 1, "IR_ONLY": 1},
        )

    def test_every_required_negative_fixture_fails_with_stable_code(self):
        for filename, code in INVALID.items():
            with self.subTest(filename=filename):
                value = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
                with self.assertRaises(ProfileError) as caught:
                    validate_coverage_receipt(value)
                self.assertEqual(caught.exception.code, code)

    def test_schema_document_is_versioned_extensible_and_status_closed(self):
        path = Path(__file__).resolve().parents[1] / "src/skos/coverage_receipt.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schema"]["const"], SCHEMA_ID)
        self.assertTrue(schema["properties"]["domains"]["additionalProperties"]["$ref"].endswith("/domain"))
        disposition = schema["$defs"]["dispositions"]
        self.assertFalse(disposition["additionalProperties"])
        self.assertEqual(
            set(disposition["required"]),
            {"EMITTED", "HELD", "REJECTED", "UNSUPPORTED", "IR_ONLY"},
        )

    def test_schema_and_fixture_contain_no_curriculum_or_admission_authority(self):
        schema_text = (Path(__file__).resolve().parents[1] / "src/skos/coverage_receipt.schema.json").read_text(
            encoding="utf-8"
        ).lower()
        fixture_text = json.dumps(VALID, sort_keys=True).lower()
        self.assertNotIn("curriculum", schema_text + fixture_text)
        self.assertNotIn("admission", schema_text + fixture_text)

    def test_duplicate_input_artifact_is_rejected(self):
        value = json.loads(json.dumps(VALID))
        value["inputs"].append(dict(value["inputs"][0]))
        with self.assertRaises(ProfileError) as caught:
            validate_coverage_receipt(value)
        self.assertEqual(caught.exception.code, "COVERAGE_INPUT_DUPLICATE")

    def test_domain_total_mismatch_is_rejected_independently_of_global_totals(self):
        value = json.loads(json.dumps(VALID))
        value["domains"]["atomic"]["source_rows"] = 4
        value["totals"]["source_rows"] = 11
        with self.assertRaises(ProfileError) as caught:
            validate_coverage_receipt(value)
        self.assertEqual(caught.exception.code, "COVERAGE_DOMAIN_TOTAL_MISMATCH")


if __name__ == "__main__":
    unittest.main()
