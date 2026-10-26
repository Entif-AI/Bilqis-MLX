import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from lib.ithkuil.src import build_lexicon_chapters as legacy
from lib.ithkuil.src import lexicon_frontier as frontier


PDF = legacy.ROOT / "_raw/New_Ithkuil_Lexicon.pdf"
INCOMPLETE_ROOT_LINE = "- KŠPW ‘APIOIDEAE’ II 1. (genus Pimpinella ) anise, short-fruit pimpinella / chamnamul, burnet-saxifrage 2. (genus Carum ) caraway / meridian fennel / Persian cumin"


class ChapterSevenFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (legacy.DATA / "lexicon_root_senses.csv").open(encoding="utf-8", newline="") as source:
            cls.prior = [row for row in csv.DictReader(source) if int(row["lexicon_chapter"]) < 7]
        cls.result = frontier.extract_chapter("7", PDF, prior_senses=cls.prior)

    def test_fresh_extraction_matches_published_golden_receipt(self):
        expected = json.loads((legacy.ROOT / "tests/fixtures/chapter7_extraction_expected.json").read_text())
        receipt = self.result["receipt"]
        for key, value in expected["source"].items():
            self.assertEqual(receipt["source"][key], value)
        self.assertEqual(receipt["source"]["canonical_pages"], list(range(319, 571)))
        self.assertEqual(receipt["source"]["comparison"], "normalized-page-text-exact")
        for key in ("counts", "dispositions", "output_sha256", "accounting_sha256"):
            self.assertEqual(receipt[key], expected[key])
        self.assertEqual(receipt, json.loads(frontier.PROFILE.read_text())["chapter_receipts"]["7"])

    def test_source_shapes_loci_and_stable_identity(self):
        roots = {row["root_form_raw"]: row for row in self.result["roots"]}
        for root in roots.values():
            self.assertEqual(root["lexicon_root_id"], legacy.stable_id("LEXROOT", legacy.SOURCE_ID, root["root_form_raw"]))
            self.assertTrue(root["root_form_raw"].strip("-").isalpha())
            self.assertTrue(root["root_gloss"] and root["source_printed_page"]
                            and root["lexicon_section"].startswith("7."))
        for form, page, section in (("-RDK-", "98", "7.3.1.1"), ("-PÇR-", "47", "7.2.1.1"),
                                    ("-PFTY-", "242", "7.3.5")):
            self.assertEqual((roots[form]["source_pdf_page"], roots[form]["lexicon_section"]), (page, section))
        for sense in self.result["senses"]:
            self.assertEqual(sense["lexicon_sense_id"], frontier.structural_sense_id(
                sense["root_form_raw"], sense["stem"], sense["specification"]))
            self.assertTrue(sense["source_pdf_page"] and sense["source_locus_kind"])
        cellular = [row for row in self.result["senses"] if row["root_form_raw"] == "-LCP-"]
        self.assertEqual(sorted((row["stem"], row["specification"]) for row in cellular),
                         [("STEM 1", "BSC"), ("STEM 2", "BSC"), ("STEM 3", "BSC")])
        self.assertTrue(all(row["source_pdf_page"] == "1" and row["source_table_index"] == "1"
                            for row in cellular))
        accounting = self.result["accounting"]
        self.assertEqual({row["sense_id"] for row in accounting if row["status"] == "PARSED"},
                         {row["lexicon_sense_id"] for row in self.result["senses"]})
        incomplete = [row for row in accounting
                      if row.get("reason") == "Quoted root heading has no supported complete root boundary."]
        self.assertEqual({(row["source_locus"]["pdf_page"], row["source_locus"]["line"]) for row in incomplete},
                         {(44, 66), (44, 68), (97, 18), (125, 30), (168, 20)})
        self.assertTrue(all(row["status"] == "DEBT_UNSUPPORTED_SHAPE"
                            and not row["lexicon_root_id"] and not row["root_form_raw"] for row in incomplete))
        held = [row for row in accounting if row["source_locus"]["kind"] == "root"
                and row["root_form_raw"] and not row["lexicon_root_id"]]
        self.assertEqual(len(held), 34)
        self.assertTrue(any(row["root_form_raw"] == "-ŽKW-" and row.get("stem") == "STEM 3"
                            and row["status"] == "DEBT_INSUFFICIENT_SENSE_EVIDENCE"
                            and "specification" not in row
                            and row["source_locus"] == {"kind": "prose", "pdf_page": 11, "line_start": 15, "line_end": 15}
                            for row in accounting))
        self.assertTrue(any(row["status"] == "DEBT_UNSUPPORTED_SHAPE" and not row["lexicon_root_id"]
                            and row["source_locus"] == {"kind": "table", "pdf_page": 3, "table_index": 2, "row": 0, "column": 0}
                            for row in accounting))

    def test_unpinned_page_map_fails_without_publication(self):
        paths = [legacy.DATA / (table + ".csv") for table in frontier.TABLES]
        before = [path.read_bytes() for path in paths]
        pins = json.loads(frontier.PINS.read_text())
        pins["chapters"]["7"]["canonical_page_start"] += 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pins.json"
            path.write_text(json.dumps(pins))
            with patch.object(frontier, "PINS", path):
                with self.assertRaisesRegex(ValueError, "LEXICON_CANONICAL_PAGE_MISMATCH:1"):
                    frontier.extract_chapter("7", PDF)
        self.assertEqual(before, [path.read_bytes() for path in paths])


class RootBoundaryTests(unittest.TestCase):
    def test_strict_root_requires_a_complete_letter_only_boundary(self):
        self.assertIsNone(frontier._root_form(INCOMPLETE_ROOT_LINE, strict=True))
        self.assertIsNone(frontier._root_form("- - ‘PELVIC LIGAMENT’", strict=True))
        self.assertEqual(frontier._root_form("- RDK - ‘DASYURINE MARSUPIAL’", strict=True), "-RDK-")

    def test_unknown_heading_cannot_inherit_the_previous_root_scope(self):
        # Synthetic negative: a broken root heading separates two explicit stems.
        lines = ["-LCP- ‘CELLULAR ORGANELLE’", "BSC", "STEM 1: an organelle",
                 INCOMPLETE_ROOT_LINE, "STEM 2: an unassigned source statement", "7.1 New section"]
        page = Mock()
        page.find_tables.return_value.tables = []
        page.get_text.return_value = "319\n" + "\n".join(lines)
        root = {"lexicon_root_id": legacy.stable_id("LEXROOT", legacy.SOURCE_ID, "-LCP-")}
        records = [(i, text, (0, i, 10, i + 1)) for i, text in enumerate(lines, 1)]
        with patch.object(frontier, "_page_lines", return_value=iter(records)):
            accounting, candidates = frontier._prose_sense_candidates(
                [page], "7", {(1, "-LCP-"): {"lexicon_section": "7.0"}}, {"-LCP-": root}, {})
        self.assertEqual(set(candidates), {("-LCP-", "STEM 1", "BSC")})
        debt = next(row for row in accounting if row.get("stem") == "STEM 2")
        self.assertEqual((debt["status"], debt["root_form_raw"], debt["lexicon_root_id"]),
                         ("DEBT_INSUFFICIENT_SENSE_EVIDENCE", "", ""))


if __name__ == "__main__":
    unittest.main()
