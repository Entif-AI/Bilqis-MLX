from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lib.ithkuil.src import build_lexicon_chapters as legacy
from lib.ithkuil.src import lexicon_frontier as frontier


ROOT = ITHKUIL_ROOT
PDF = ROOT / "_raw/New_Ithkuil_Lexicon.pdf"


class ChapterFourFrontierTests(unittest.TestCase):
    def test_golden_chapter_four_extraction_and_receipt_rerun(self):
        expected = json.loads((ROOT / "tests/fixtures/chapter4_extraction_expected.json").read_text())
        with (legacy.DATA / "lexicon_root_senses.csv").open(encoding="utf-8", newline="") as source:
            prior_senses = [row for row in csv.DictReader(source) if row["lexicon_chapter"] in {"1", "2", "3"}]
        result = frontier.extract_chapter("4", PDF, prior_senses=prior_senses)
        receipt = result["receipt"]
        source = receipt["source"]

        self.assertEqual(
            source["canonical_pages"],
            list(range(115, 245)),
        )
        for key in ("filename", "sha256", "canonical_sha256", "canonical_page_start", "page_count",
                    "canonical_page_text_variant_pages", "min_text_similarity"):
            self.assertEqual(source[key], expected["source"][key])
        self.assertEqual(source["comparison"], "normalized-page-text-exact-with-pinned-variants")
        self.assertEqual(receipt["counts"], expected["counts"])
        self.assertEqual(receipt["dispositions"], expected["dispositions"])
        self.assertEqual(receipt["output_sha256"], expected["output_sha256"])
        self.assertEqual(receipt["accounting_sha256"], expected["accounting_sha256"])
        published = json.loads((legacy.DATA / "sources/lexicon_frontier_manifest.json").read_text())
        self.assertEqual(receipt, published["chapter_receipts"]["4"])

        self.assertTrue(
            all(
                row["source_id"] == "NI-LEXICON-CURRICULUM"
                and row["canonical_source_sha256"] == json.loads(frontier.PINS.read_text())["canonical_sha256"]
                and row["source_pdf_page"]
                and row["lexicon_section"].startswith("4.")
                and row["lexicon_root_id"] == legacy.stable_id("LEXROOT", legacy.SOURCE_ID, row["root_form_raw"])
                and row["root_gloss"]
                for row in result["roots"]
            )
        )
        shapes = expected["representative_shapes"]
        root_rows = {row["root_form_raw"] for row in result["roots"]}
        self.assertTrue(set(shapes["recovered_root_rows"]).issubset(root_rows))
        for debt in shapes["root_locus_debt"]:
            matching = [row for row in result["accounting"] if
                        row["root_form_raw"] == debt["root_form_raw"] and
                        row["status"] == "DEBT_INSUFFICIENT_SENSE_EVIDENCE" and
                        row["source_locus"].get("kind") == "root"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["lexicon_root_id"], "")
            self.assertEqual(
                {key: matching[0]["source_locus"][key]
                 for key in ("pdf_page", "lexicon_section", "line")},
                {key: debt[key] for key in ("pdf_page", "lexicon_section", "line")},
            )

        for row in result["senses"]:
            self.assertEqual(row["lexicon_sense_id"], frontier.structural_sense_id(
                row["root_form_raw"], row["stem"], row["specification"]))
            self.assertTrue(row["source_pdf_page"] and row["source_printed_page"] and row["source_locus_kind"])

        accounting = result["accounting"]
        emitted = {row["lexicon_sense_id"] for row in result["senses"]}
        accounted = {row["sense_id"] for row in accounting if row["status"] == "PARSED"}
        self.assertEqual(emitted, accounted)
        ordinary = shapes["ordinary_table_sense"]
        self.assertTrue(any(all(row.get(key) == value for key, value in ordinary.items()) for row in accounting))
        multi = shapes["multi_sense_root"]
        multi_rows = [row for row in result["senses"] if row["root_form_raw"] == multi["root_form_raw"]]
        self.assertEqual(sorted([row["stem"], row["specification"]] for row in multi_rows), multi["coordinates"])
        self.assertTrue(all(row["source_pdf_page"] == multi["source_pdf_page"] and
                            row["source_table_index"] == multi["source_table_index"] for row in multi_rows))
        prose = shapes["prose_debt"]
        self.assertTrue(any(all(row.get(key) == value for key, value in prose.items()) for row in accounting))
        unsupported = shapes["unsupported_table"]
        self.assertTrue(any(all(row.get(key) == value for key, value in unsupported.items()) for row in accounting))
        self.assertEqual(sum(row["source_locus_kind"] == "prose" for row in result["senses"]),
                         shapes["prose_parsed_sense_count"])
        self.assertTrue(all(row["status"] in {"PARSED", "DEBT_UNSUPPORTED_SHAPE", "DEBT_INSUFFICIENT_SENSE_EVIDENCE",
                                              "DEBT_AMBIGUOUS_LOCUS", "DEBT_CONFLICT"} for row in accounting))

    def test_unexpected_page_text_variant_fails_closed(self):
        manifest = json.loads(frontier.PINS.read_text(encoding="utf-8"))
        pin = manifest["chapters"]["4"]
        pin["canonical_page_text_variants"]["42"]["tracked_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pins.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(frontier, "PINS", path):
                with self.assertRaisesRegex(ValueError, "LEXICON_CANONICAL_PAGE_MISMATCH:42"):
                    frontier.extract_chapter("4", PDF)


if __name__ == "__main__":
    unittest.main()
