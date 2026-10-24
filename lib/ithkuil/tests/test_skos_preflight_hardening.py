import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.preflight import preflight
from lib.ithkuil.src.skos.preflight_io import load_input_root
from lib.ithkuil.src.skos.preflight_manifest import (
    DEFAULT_MANIFEST_PATH,
    load_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "_data/csv"


class PreflightHardeningTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest()

    def clone(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name) / "csv"
        shutil.copytree(SOURCE_ROOT, root)
        return temp, root

    def path(self, root, table):
        return root / self.manifest.table(table).path

    def mutate(self, root, table, change):
        path = self.path(root, table)
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames
            rows = list(reader)
        change(rows)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_unknown_assertion_selector_preserves_enum_failure(self):
        temp, root = self.clone()
        try:
            self.mutate(
                root,
                "source_assertions",
                lambda rows: rows[0].__setitem__("entity_kind", "future_kind"),
            )
            result = preflight(root)
            self.assertIn(
                ("INVALID_ENUM_STATE", "source_assertions", "entity_kind"),
                {(f.code, f.table, f.field) for f in result.findings},
            )
        finally:
            temp.cleanup()

    def test_whitespace_only_primary_and_required_fields_are_blank(self):
        temp, root = self.clone()
        try:
            def whitespace(rows):
                rows[0]["atomic_id"] = "   "
                rows[1]["primary_source_id"] = "\t "
            self.mutate(root, "morphemes_atomic", whitespace)
            result = preflight(root)
            found = {(f.code, f.field) for f in result.findings}
            self.assertIn(("BLANK_PRIMARY_KEY", "atomic_id"), found)
            self.assertIn(("BLANK_REQUIRED_FIELD", "atomic_id"), found)
            self.assertIn(("BLANK_REQUIRED_FIELD", "primary_source_id"), found)
        finally:
            temp.cleanup()

    def test_oserror_table_read_is_stable_blocker(self):
        original = Path.read_bytes

        def flaky(path):
            if path.name == "source_sections.csv":
                raise OSError("synthetic read failure")
            return original(path)

        with mock.patch.object(Path, "read_bytes", flaky):
            loaded = load_input_root(SOURCE_ROOT, self.manifest)
        match = [
            f
            for f in loaded.findings
            if f.code == "TABLE_READ_ERROR" and f.table == "source_sections"
        ]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0].locus, "source_sections.csv")
        self.assertEqual(match[0].details, ("OSError",))

    def test_ragged_record_locus_is_content_stable_under_reorder(self):
        temp, root = self.clone()
        try:
            path = self.path(root, "source_sections")
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            rows[1] = rows[1][:-1]
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle, lineterminator="\n").writerows(rows)
            first = preflight(root)
            match = [f for f in first.findings if f.code == "MALFORMED_CSV"]
            self.assertEqual(len(match), 1)
            self.assertTrue(match[0].locus.startswith("record="))
            self.assertNotIn("line", match[0].locus)

            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle, lineterminator="\n").writerows(
                    [rows[0], *reversed(rows[1:])]
                )
            self.assertEqual(first.as_dict(), preflight(root).as_dict())
        finally:
            temp.cleanup()

    def assert_invalid_manifest(self, mutate):
        raw = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
        mutate(raw)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ProfileError) as caught:
                load_manifest(path)
        self.assertEqual(caught.exception.code, "INVALID_COMPILER_INPUT_MANIFEST")

    def test_invalid_manifest_configuration_fails_before_constraints_can_disappear(self):
        cases = [
            lambda raw: raw.__setitem__("version", "future-version"),
            lambda raw: raw["tables"].append(dict(raw["tables"][0])),
            lambda raw: raw["tables"][0].__setitem__(
                "columns", [*raw["tables"][0]["columns"], raw["tables"][0]["columns"][0]]
            ),
            lambda raw: raw["tables"][0].__setitem__("path", "../escape.csv"),
            lambda raw: raw["tables"][2]["foreign_keys"][0].__setitem__(
                "target_fields", ["source_id", "extra"]
            ),
            lambda raw: raw["semantic_invariants"].append(
                {"name": "future_silent_constraint"}
            ),
        ]
        for index, mutate in enumerate(cases):
            with self.subTest(case=index):
                self.assert_invalid_manifest(mutate)


if __name__ == "__main__":
    unittest.main()
