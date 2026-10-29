"""Focused tests for BAMF grooming publication helpers."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "bamf"))

import bamf02_groom_publication as publication


class GroomPublicationTests(unittest.TestCase):
    def test_append_parent_navigation_is_idempotent(self):
        source = "# A01\n\n## Direct dependencies and existing owners\nNone.\n"
        descendants = [{"key": "A01.1", "title": "First child", "group": False, "parent": "A01"}]
        identifiers = {"A01.1": 500}
        once = publication.append_parent_navigation("A01", source, descendants, identifiers)
        twice = publication.append_parent_navigation("A01", once, descendants, identifiers)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(publication.MARKER + "A01 -->"), 1)

    def test_existing_title_stops_after_short_page(self):
        with patch.object(publication, "gh", return_value=[{"title": "Other", "number": 1}]) as gh:
            self.assertIsNone(publication.existing_title("Wanted"))
        gh.assert_called_once()

    def test_existing_title_ignores_pull_requests(self):
        payload = [
            {"title": "Wanted", "number": 2, "pull_request": {"url": "https://example.test/pr/2"}},
            {"title": "Wanted", "number": 3},
        ]
        with patch.object(publication, "gh", return_value=payload):
            found = publication.existing_title("Wanted")
        self.assertEqual(found["number"], 3)


if __name__ == "__main__":
    unittest.main()
