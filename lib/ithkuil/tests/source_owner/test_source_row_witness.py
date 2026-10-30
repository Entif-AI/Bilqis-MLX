from __future__ import annotations

import unittest

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.source_owner.row_witness import source_row_byte_witness


ROOT = "lib/ithkuil/_data/csv"


class SourceRowWitnessTests(unittest.TestCase):
    def test_exact_tracked_source_row_has_stable_byte_identity(self):
        witness = source_row_byte_witness(ROOT, "source", "source_sections", "NI-WEB-CH01:1.0")
        self.assertEqual(witness.relative_path, "source_sections.csv")
        self.assertEqual(witness.record_start_byte, 170)
        self.assertEqual(witness.record_end_byte, 294)
        self.assertEqual(
            witness.record_sha256,
            "421024295678da118a302c531b6cd0446707c491e43833b0884c17aa33fa154d",
        )
        self.assertEqual(
            witness.source_reference,
            "ithkuil-csv:source/source_sections.csv#NI-WEB-CH01:1.0@sha256:"
            + witness.record_sha256,
        )
        self.assertEqual(dict(witness.values)["source_id"], "NI-WEB-CH01")

    def test_unknown_row_and_table_fail_closed(self):
        for table, key in (
            ("source_sections", "missing-row"),
            ("missing-table", "missing-row"),
        ):
            with self.subTest(table=table), self.assertRaises(ProfileError):
                source_row_byte_witness(ROOT, "source", table, key)


if __name__ == "__main__":
    unittest.main()
