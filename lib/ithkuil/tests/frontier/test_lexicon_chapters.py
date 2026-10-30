from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = ITHKUIL_ROOT
SCRIPT = ROOT / "src" / "build_lexicon_chapters.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_lexicon_chapters", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LexiconChapterExtractionTests(unittest.TestCase):
    def test_chapter_three_expands_source_work_without_mutating_canonical_tables(self):
        module = load_module()
        data = ROOT / "_data" / "csv"
        original = {name: (data / name).read_bytes() for name in (
            "lexicon_roots.csv", "lexicon_root_senses.csv", "lexicon_root_evidence.csv")}
        with tempfile.TemporaryDirectory() as temp:
            manifest = module.extract_snapshot(("3",), Path(temp))
            self.assertEqual(manifest["chapters"], ["3"])
            with (Path(temp) / "lexicon_roots.csv").open(newline="") as stream:
                roots = list(csv.DictReader(stream))
            with (Path(temp) / "lexicon_root_senses.csv").open(newline="") as stream:
                senses = list(csv.DictReader(stream))
            self.assertIn("-ŠŘ-", {row["root_form_raw"] for row in roots})
            self.assertIn("-LC-", {row["root_form_raw"] for row in roots})
            self.assertTrue(senses)
            self.assertEqual({row["lexicon_chapter"] for row in roots}, {"3"})
            self.assertEqual(manifest, module.extract_snapshot(("3",), Path(temp)))
            self.assertEqual(manifest["canonical_page_equivalence"], "NOT_MEASURED")
        self.assertEqual(original, {name: (data / name).read_bytes() for name in original})

    def test_expansion_refuses_canonical_output_and_unknown_chapters(self):
        module = load_module()
        with self.assertRaisesRegex(ValueError, "LEXICON_EXPANSION_REQUIRES_SEPARATE_OUTPUT"):
            module.extract_snapshot(("3",), module.DATA)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "LEXICON_CHAPTER_SCOPE_INVALID"):
                module.extract_snapshot(("99",), Path(temp))

    def test_chapters_one_and_two_extract_source_roots_and_senses(self):
        module = load_module()
        roots, senses, evidence = module.build(module.CHAPTERS)
        by_form = {row["root_form_raw"]: row for row in roots}

        self.assertEqual(len(roots), 503)
        self.assertEqual(len(senses), 1615)
        self.assertEqual(len(evidence), 150)
        self.assertIn("-Č-", by_form)
        self.assertIn("-PS-", by_form)
        self.assertIn("-THW-", by_form)
        self.assertEqual(by_form["-Č-"]["lexicon_section"], "1.3")
        self.assertEqual(by_form["-PS-"]["lexicon_section"], "2.0")
        self.assertTrue(all(row["source_id"] == "NI-LEXICON-CURRICULUM" for row in roots))
        self.assertTrue(all(row["tracked_pdf_sha256"] for row in senses))

        copular = [row for row in senses if row["root_form_raw"] == "-Č-"]
        self.assertEqual(len(copular), 12)
        self.assertEqual({row["specification"] for row in copular}, {"BSC", "CTE", "CSV", "OBJ"})
        self.assertEqual({row["stem"] for row in copular}, {"STEM 1", "STEM 2", "STEM 3"})

        inherited_pattern = [row for row in senses if row["root_form_raw"] == "-RMC-"]
        self.assertEqual(len(inherited_pattern), 3)
        self.assertEqual({row["stem"] for row in inherited_pattern}, {"STEM 1", "STEM 2", "STEM 3"})
        self.assertTrue(all(row["source_locus_kind"] == "prose" for row in inherited_pattern))

        inherited_stems = [row for row in senses if row["root_form_raw"] == "-ŘḐŘ-"]
        self.assertEqual(len(inherited_stems), 1)
        self.assertEqual(inherited_stems[0]["stem"], "STEMS 1-3")

        computer = [row for row in senses if row["root_form_raw"] == "-KŢG-"]
        self.assertEqual(len(computer), 3)
        self.assertEqual(
            {row["stem"] for row in computer},
            {"STEM 1", "STEM 2", "STEM 3"},
        )
        self.assertTrue(
            all(row["source_locus_kind"] == "compact_numbered_stem" for row in computer)
        )
        program = [row for row in senses if row["root_form_raw"] == "-KŢGY-"]
        self.assertEqual(len(program), 3)
        self.assertIn("computer program", program[0]["sense_summary"].lower())

        self.assertTrue(all(len(row["source_text_sha256"]) == 64 for row in senses))
        self.assertTrue(all(int(row["source_text_char_count"]) > 0 for row in senses))
        copular_evidence = [row for row in evidence if row["root_form_raw"] == "-Č-"]
        self.assertEqual(len(copular_evidence), 8)
        self.assertEqual(
            sum(row["evidence_kind"] == "scope_restriction" for row in copular_evidence),
            7,
        )
        self.assertFalse(any(row["root_form_raw"] == "-T-" for row in copular_evidence))

    def test_checked_in_tables_are_reproducible(self):
        module = load_module()
        roots, senses, evidence = module.build()
        for filename, expected in (
            ("lexicon_roots.csv", roots),
            ("lexicon_root_senses.csv", senses),
            ("lexicon_root_evidence.csv", evidence),
        ):
            with (ROOT / "_data" / "csv" / filename).open(newline="", encoding="utf-8") as handle:
                observed = list(csv.DictReader(handle))
            self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
