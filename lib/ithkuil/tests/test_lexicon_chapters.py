from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "build_lexicon_chapters.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_lexicon_chapters", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LexiconChapterExtractionTests(unittest.TestCase):
    def test_chapters_one_and_two_extract_source_roots_and_senses(self):
        module = load_module()
        roots, senses, evidence = module.build()
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
