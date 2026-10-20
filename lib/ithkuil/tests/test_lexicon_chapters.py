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
        roots, senses = module.build()
        by_form = {row["root_form_raw"]: row for row in roots}

        self.assertEqual(len(roots), 503)
        self.assertEqual(len(senses), 1530)
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

    def test_checked_in_tables_are_reproducible(self):
        module = load_module()
        roots, senses = module.build()
        for filename, expected in (("lexicon_roots.csv", roots), ("lexicon_root_senses.csv", senses)):
            with (ROOT / "_data" / "csv" / filename).open(newline="", encoding="utf-8") as handle:
                observed = list(csv.DictReader(handle))
            self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
