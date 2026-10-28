import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lib.ithkuil.src import build_lexicon_chapters as legacy
from lib.ithkuil.src import lexicon_frontier as frontier


PDF = legacy.ROOT / "_raw/New_Ithkuil_Lexicon.pdf"


class ChapterFiveFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (legacy.DATA / "lexicon_root_senses.csv").open(encoding="utf-8", newline="") as source:
            cls.prior = [row for row in csv.DictReader(source) if row["lexicon_chapter"] in {"1", "2", "3", "4"}]
        cls.result = frontier.extract_chapter("5", PDF, prior_senses=cls.prior)

    def test_pinned_chapter_five_source_and_ordinary_root(self):
        result = self.result
        self.assertEqual(result["receipt"]["source"]["sha256"],
                         "c48b1a83f541c3728b5d2685ec186b64b73b00c417ded234b30c40361e36ef30")
        self.assertEqual(result["receipt"]["source"]["canonical_pages"], list(range(245, 261)))
        root = next(row for row in result["roots"] if row["root_form_raw"] == "-DDL-")
        self.assertEqual(root["lexicon_root_id"], legacy.stable_id("LEXROOT", legacy.SOURCE_ID, "-DDL-"))
        self.assertEqual((root["source_pdf_page"], root["source_printed_page"], root["lexicon_section"]),
                         ("1", "245", "5.0"))
        sense = next(row for row in result["senses"] if row["root_form_raw"] == "-DDL-"
                     and row["stem"] == "STEM 1" and row["specification"] == "BSC")
        self.assertEqual(sense["lexicon_sense_id"], frontier.structural_sense_id("-DDL-", "STEM 1", "BSC"))
        self.assertEqual(sense["source_pdf_page"], "1")

    def test_golden_outputs_and_deterministic_rerun(self):
        expected = json.loads((legacy.ROOT / "tests/fixtures/chapter5_extraction_expected.json").read_text())
        receipt = self.result["receipt"]
        for key, value in expected["source"].items():
            self.assertEqual(receipt["source"][key], value)
        for key in ("counts", "dispositions", "output_sha256", "accounting_sha256"):
            self.assertEqual(receipt[key], expected[key])
        self.assertEqual(self.result, frontier.extract_chapter("5", PDF, prior_senses=self.prior))

    def test_stable_identities_and_source_shapes(self):
        roots = {row["root_form_raw"]: row for row in self.result["roots"]}
        for row in roots.values():
            self.assertEqual(row["lexicon_root_id"], legacy.stable_id("LEXROOT", legacy.SOURCE_ID, row["root_form_raw"]))
            self.assertTrue(row["source_pdf_page"] and row["lexicon_section"].startswith("5."))
        for row in self.result["senses"]:
            self.assertEqual(row["lexicon_sense_id"], frontier.structural_sense_id(
                row["root_form_raw"], row["stem"], row["specification"]))
            self.assertTrue(row["source_pdf_page"] and row["source_locus_kind"])
        self.assertEqual(roots["-ŠMY-"]["source_pdf_page"], "3")
        self.assertEqual(roots["-ŽTMW-"]["source_pdf_page"], "16")
        self.assertNotIn("-ŽMY-", roots)
        ddl = [row for row in self.result["senses"] if row["root_form_raw"] == "-DDL-"]
        self.assertEqual(sorted((row["stem"], row["specification"]) for row in ddl),
                         [("STEM 1", "BSC"), ("STEM 2", "BSC"), ("STEM 3", "BSC")])
        accounting = self.result["accounting"]
        self.assertEqual({row["sense_id"] for row in accounting if row["status"] == "PARSED"},
                         {row["lexicon_sense_id"] for row in self.result["senses"]})
        self.assertTrue(any(row["root_form_raw"] == "-RFB-" and row.get("stem") == "STEM 2"
                            and row["status"] == "DEBT_INSUFFICIENT_SENSE_EVIDENCE"
                            and row["source_locus"] == {"kind": "prose", "pdf_page": 3, "line_start": 49, "line_end": 49}
                            and "specification" not in row for row in accounting))
        self.assertTrue(any(row["status"] == "DEBT_UNSUPPORTED_SHAPE" and row["lexicon_root_id"] == ""
                            and row["source_locus"] == {"kind": "table", "pdf_page": 6, "table_index": 4, "row": 0, "column": 0}
                            for row in accounting))
        self.assertTrue(any(row["root_form_raw"] == "-ÇÇTR-" and row["source_locus"]["kind"] == "root"
                            and row["status"] == "DEBT_INSUFFICIENT_SENSE_EVIDENCE" for row in accounting))
        self.assertFalse(any(row["root_form_raw"] == "-ÇÇTR-" for row in self.result["senses"]))
        self.assertEqual(sum(row["source_locus_kind"] == "prose" for row in self.result["senses"]), 0)

    def test_unpinned_page_variant_fails_before_publication(self):
        paths = [legacy.DATA / (table + ".csv") for table in frontier.TABLES]
        before = [path.read_bytes() for path in paths]
        pins = json.loads(frontier.PINS.read_text())
        pins["chapters"]["5"]["canonical_page_text_variants"]["2"]["tracked_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pins.json"
            path.write_text(json.dumps(pins))
            with patch.object(frontier, "PINS", path):
                with self.assertRaisesRegex(ValueError, "LEXICON_CANONICAL_PAGE_MISMATCH:2"):
                    frontier.extract_chapter("5", PDF)
        self.assertEqual(before, [path.read_bytes() for path in paths])


if __name__ == "__main__":
    unittest.main()
