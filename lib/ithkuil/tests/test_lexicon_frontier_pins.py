import hashlib
import json
import re
import unittest

from lib.ithkuil.src import build_lexicon_chapters as legacy


PINS = legacy.ROOT / "src/lexicon_frontier_pins.json"


class LexiconFrontierPinTests(unittest.TestCase):
    def test_every_local_chapter_pdf_has_an_exact_pin(self):
        manifest = json.loads(PINS.read_text(encoding="utf-8"))
        pins = manifest["source_pdfs"]
        pdfs = sorted(legacy.PDF_DIR.glob("*.pdf"))
        chapter_numbers = {
            str(int(re.search(r"Chapter (\d+)", path.name).group(1)))
            for path in pdfs
        }

        self.assertSetEqual(set(pins), chapter_numbers)
        for path in pdfs:
            chapter = str(int(re.search(r"Chapter (\d+)", path.name).group(1)))
            pin = pins[chapter]
            with legacy.fitz.open(path) as document:
                self.assertEqual(pin["filename"], path.name)
                self.assertEqual(pin["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(pin["page_count"], len(document))
                self.assertEqual(pin["format"], document.metadata["format"])

    def test_only_the_selected_frontier_is_a_later_chapter_pin(self):
        manifest = json.loads(PINS.read_text(encoding="utf-8"))
        source_pdfs = manifest["source_pdfs"]
        chapters = manifest["chapters"]

        self.assertEqual(set(chapters), {"3", "4"})
        for chapter, pin in chapters.items():
            self.assertEqual(pin, source_pdfs[chapter])


if __name__ == "__main__":
    unittest.main()
