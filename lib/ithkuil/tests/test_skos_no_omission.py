from __future__ import annotations

import json
from pathlib import Path
import unittest

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.no_omission import (
    SourceRowIdentity,
    no_omission_json_bytes,
    validate_no_omission,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"
SOURCE_DATA = json.loads((FIXTURES / "no_omission_source_rows.json").read_text(encoding="utf-8"))
EXPECTED = tuple(
    SourceRowIdentity(item["domain"], item["table"], item["key"])
    for item in SOURCE_DATA["rows"]
)
VALID = json.loads((FIXTURES / "no_omission_valid_receipt.json").read_text(encoding="utf-8"))
MISSING = {
    "no_omission_missing_atomic.json": "atomic:morphemes_atomic:ATOM-A3",
    "no_omission_missing_lexicon.json": "lexicon:lexicon_root_senses:LEXSENSE-L2",
    "no_omission_missing_residue.json": "residue:morpheme_compositions:COMP-R1",
    "no_omission_missing_affix.json": "residue:affix_residue:AFF-R2",
    "no_omission_missing_mapping.json": "mapping:mapping_crosswalk:MAP-M1",
}


class NoOmissionTests(unittest.TestCase):
    def test_complete_fixture_accounts_every_row_once(self):
        result = validate_no_omission(EXPECTED, VALID)
        self.assertEqual(result.source_rows, 10)
        self.assertEqual(result.accounted_rows, 10)
        self.assertEqual(
            dict(result.dispositions),
            {"EMITTED": 5, "HELD": 2, "REJECTED": 1, "UNSUPPORTED": 1, "IR_ONLY": 1},
        )
        self.assertEqual(dict(result.domain_rows), {"atomic": 3, "lexicon": 3, "mapping": 2, "residue": 2})
        self.assertTrue(result.as_dict()["complete"])
        self.assertEqual(no_omission_json_bytes(result), no_omission_json_bytes(result))

    def test_each_domain_omission_names_the_exact_stable_id(self):
        for filename, locator in MISSING.items():
            with self.subTest(filename=filename):
                receipt = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
                with self.assertRaises(ProfileError) as caught:
                    validate_no_omission(EXPECTED, receipt)
                self.assertEqual(caught.exception.code, "NO_OMISSION_MISMATCH")
                self.assertIn(f"missing={locator}", caught.exception.details)

    def test_duplicate_accounting_names_the_exact_stable_id(self):
        receipt = json.loads((FIXTURES / "no_omission_duplicate.json").read_text(encoding="utf-8"))
        with self.assertRaises(ProfileError) as caught:
            validate_no_omission(EXPECTED, receipt)
        self.assertEqual(caught.exception.code, "NO_OMISSION_MISMATCH")
        self.assertIn("duplicate=atomic:morphemes_atomic:ATOM-A1", caught.exception.details)

    def test_ir_only_requires_explicit_reason_and_owner(self):
        receipt = json.loads(
            (FIXTURES / "no_omission_ir_only_without_reason.json").read_text(encoding="utf-8")
        )
        with self.assertRaises(ProfileError) as caught:
            validate_no_omission(EXPECTED, receipt)
        self.assertEqual(caught.exception.code, "IR_ONLY_RATIONALE_REQUIRED")
        self.assertIn("lexicon:lexicon_root_evidence:EVID-L3", caught.exception.details)

    def test_nonemitted_row_cannot_have_strong_semantic_subject(self):
        with self.assertRaises(ProfileError) as caught:
            validate_no_omission(EXPECTED, VALID, strong_subjects={"urn:atomic:a3"})
        self.assertEqual(caught.exception.code, "NONEMITTED_ROW_HAS_STRONG_ASSERTION")
        self.assertIn("atomic:morphemes_atomic:ATOM-A3", caught.exception.details)

    def test_duplicate_expected_source_id_is_rejected(self):
        with self.assertRaises(ProfileError) as caught:
            validate_no_omission((*EXPECTED, EXPECTED[0]), VALID)
        self.assertEqual(caught.exception.code, "SOURCE_ROW_ID_DUPLICATE")
        self.assertIn(f"duplicate={EXPECTED[0].locator}", caught.exception.details)


if __name__ == "__main__":
    unittest.main()
