import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lib.ithkuil.src import build_lexicon_chapters as legacy
from lib.ithkuil.src import lexicon_frontier as frontier


PDF = legacy.ROOT / "_raw/New_Ithkuil_Lexicon.pdf"


class ChapterSixFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (legacy.DATA / "lexicon_root_senses.csv").open(encoding="utf-8", newline="") as source:
            cls.prior = [row for row in csv.DictReader(source) if int(row["lexicon_chapter"]) < 6]
        cls.result = frontier.extract_chapter("6", PDF, prior_senses=cls.prior)

    def test_spaced_source_root_and_stable_locus(self):
        root = next(row for row in self.result["roots"] if row["root_form_raw"] == "-RẒBW-")
        self.assertEqual(root["lexicon_root_id"], legacy.stable_id("LEXROOT", legacy.SOURCE_ID, "-RẒBW-"))
        self.assertEqual(root["root_gloss"], "‘CHEMICAL COMPOUND BY TYPE OF MOLECULAR BOND’")
        self.assertEqual((root["source_pdf_page"], root["source_printed_page"], root["lexicon_section"]),
                         ("53", "313", "6.4.3"))

    def test_unaddressable_diagram_page_stays_explicit_debt(self):
        self.assertFalse(any(row["source_pdf_page"] == "44"
                             for key in ("roots", "senses", "evidence") for row in self.result[key]))
        page = [row for row in self.result["accounting"]
                if row["source_locus"] == {"kind": "page", "pdf_page": 44}]
        self.assertEqual(len(page), 1)
        self.assertEqual(page[0]["status"], "DEBT_UNSUPPORTED_SHAPE")
        self.assertEqual(page[0]["source_printed_page"], "")
        self.assertEqual(page[0]["lexicon_root_id"], "")
        held_roots = [row for row in self.result["accounting"]
                      if row["source_pdf_page"] == "44" and row["source_locus"]["kind"] == "root"]
        self.assertEqual(len(held_roots), 14)
        self.assertTrue(all(row["status"] == "DEBT_UNSUPPORTED_SHAPE" and not row["lexicon_root_id"]
                            for row in held_roots))

    def test_golden_receipt_and_deterministic_rerun(self):
        expected = json.loads((legacy.ROOT / "tests/fixtures/chapter6_extraction_expected.json").read_text())
        receipt = self.result["receipt"]
        for key, value in expected["source"].items():
            self.assertEqual(receipt["source"][key], value)
        self.assertEqual(receipt["source"]["canonical_pages"], list(range(261, 320)))
        for key in ("counts", "dispositions", "output_sha256", "accounting_sha256"):
            self.assertEqual(receipt[key], expected[key])
        self.assertEqual(receipt, json.loads(frontier.PROFILE.read_text())["chapter_receipts"]["6"])
        self.assertEqual(self.result, frontier.extract_chapter("6", PDF, prior_senses=self.prior))

    def test_source_shapes_and_stable_sense_coordinates(self):
        for root in self.result["roots"]:
            self.assertEqual(root["lexicon_root_id"], legacy.stable_id("LEXROOT", legacy.SOURCE_ID, root["root_form_raw"]))
            self.assertTrue(root["source_pdf_page"] and root["source_printed_page"] and root["root_gloss"]
                            and root["lexicon_section"].startswith("6."))
        for sense in self.result["senses"]:
            self.assertEqual(sense["lexicon_sense_id"], frontier.structural_sense_id(
                sense["root_form_raw"], sense["stem"], sense["specification"]))
            self.assertTrue(sense["source_pdf_page"] and sense["source_locus_kind"])
        matter = [row for row in self.result["senses"] if row["root_form_raw"] == "-TKL-"]
        self.assertEqual(sorted((row["stem"], row["specification"]) for row in matter),
                         [("STEM 1", "BSC"), ("STEM 2", "BSC"), ("STEM 3", "BSC")])
        self.assertTrue(all(row["source_pdf_page"] == "1" and row["source_table_index"] == "1" for row in matter))
        accounting = self.result["accounting"]
        three = next(row for row in self.result["roots"] if row["root_form_raw"] == "-Z-")
        self.assertTrue(three["root_gloss"].startswith("‘THREE / TRINARY’"))
        self.assertEqual((three["source_pdf_page"], three["lexicon_section"]), ("36", "6.4.1"))
        self.assertTrue(any(row["root_form_raw"] == "-BC-" and not row["lexicon_root_id"]
                            and row["status"] == "DEBT_INSUFFICIENT_SENSE_EVIDENCE" for row in accounting))
        self.assertEqual({row["sense_id"] for row in accounting if row["status"] == "PARSED"},
                         {row["lexicon_sense_id"] for row in self.result["senses"]})
        self.assertTrue(any(row["root_form_raw"] == "-JB-" and row.get("stem") == "STEM 1"
                            and row["status"] == "DEBT_CONFLICT"
                            and row["source_locus"] == {"kind": "prose", "pdf_page": 41, "line_start": 5, "line_end": 6}
                            for row in accounting))
        self.assertFalse(any(row["root_form_raw"] == "-JB-" and row["stem"] == "STEM 1"
                             and row["specification"] == "BSC" for row in self.result["senses"]))
        self.assertTrue(any(row["status"] == "DEBT_UNSUPPORTED_SHAPE" and row["lexicon_root_id"] == ""
                            and row["source_locus"] == {"kind": "table", "pdf_page": 9, "table_index": 2, "row": 0, "column": 0}
                            for row in accounting))
        self.assertEqual(sum(row["source_locus_kind"] == "prose" for row in self.result["senses"]), 0)

    def test_changed_source_variant_fails_before_publication(self):
        paths = [legacy.DATA / (table + ".csv") for table in frontier.TABLES]
        before = [path.read_bytes() for path in paths]
        pins = json.loads(frontier.PINS.read_text())
        pins["chapters"]["6"]["canonical_page_text_variants"]["6"]["canonical_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pins.json"
            path.write_text(json.dumps(pins))
            with patch.object(frontier, "PINS", path):
                with self.assertRaisesRegex(ValueError, "LEXICON_CANONICAL_PAGE_MISMATCH:6"):
                    frontier.extract_chapter("6", PDF)
        self.assertEqual(before, [path.read_bytes() for path in paths])


if __name__ == "__main__":
    unittest.main()
