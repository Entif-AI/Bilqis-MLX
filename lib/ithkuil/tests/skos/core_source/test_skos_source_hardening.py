from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
from pathlib import Path
import unittest

from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.resolver import RecordRef, resolve_identities
from lib.ithkuil.src.skos.source import SourceProjector
from lib.ithkuil.src.skos.source_public import PublicLocus, public_source_url, safe_public_literal


ROOT = ITHKUIL_ROOT
SOURCE_ROOT = ROOT / "_data/csv"


class SourceProjectionHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(SOURCE_ROOT).require_valid()
        cls.resolution = resolve_identities(cls.closure)
        cls.resource = next(
            resource
            for resource in cls.resolution.resources
            if resource.identity.iri.endswith("/grammar/CONFIGURATION/MFF")
        )

    def mutate_row(self, row, **changes):
        values = dict(row.values)
        values.update(changes)
        return FrozenRow(tuple((key, values[key]) for key, _ in row.values))

    def append_collision(self, closure, table_name, source_row, **changes):
        tables = []
        for table in closure.tables:
            if table.name == table_name:
                copied = self.mutate_row(source_row, **changes)
                tables.append(
                    LoadedTable(table.name, table.columns, table.rows + (copied,))
                )
            else:
                tables.append(table)
        return CompilerClosure(closure.manifest_version, tuple(tables))

    def test_cross_source_reused_section_and_table_ids_do_not_overwrite_by_row_order(self):
        section = next(
            row
            for row in self.closure.table("source_sections").rows
            if row["section_id"] == "NI-WEB-CH03:3.1"
        )
        table = next(
            row
            for row in self.closure.table("source_tables").rows
            if row["table_id"] == "NI-WEB-CH03:T003"
        )
        changed = self.append_collision(
            self.closure,
            "source_sections",
            section,
            source_id="NI-WEB-CH05",
            source_url="https://www.ithkuil.net/newithkuil_05_verbs.htm",
        )
        changed = self.append_collision(
            changed,
            "source_tables",
            table,
            source_id="NI-WEB-CH05",
            section_id="NI-WEB-CH05:5.0",
            source_url="https://www.ithkuil.net/newithkuil_05_verbs.htm",
        )
        expected = SourceProjector(changed).project_resource(
            self.resource.identity, self.resource.source_records
        )
        reversed_closure = CompilerClosure(
            changed.manifest_version,
            tuple(
                LoadedTable(item.name, item.columns, tuple(reversed(item.rows)))
                for item in reversed(changed.tables)
            ),
        )
        actual = SourceProjector(reversed_closure).project_resource(
            self.resource.identity, self.resource.source_records
        )
        self.assertEqual(expected.issues, ())
        self.assertEqual(actual.issues, ())
        self.assertEqual(set(actual.source_graph), set(expected.source_graph))

    def test_structured_locus_hash_does_not_alias_delimiter_ambiguous_display(self):
        first_coordinates = (
            ("source", "NI-X"),
            ("section", "S;table=T"),
        )
        second_coordinates = (
            ("source", "NI-X"),
            ("section", "S"),
            ("table", "T"),
        )
        display = "source=NI-X;section=S;table=T"
        first = PublicLocus(
            "https://www.ithkuil.net/example.htm",
            "NI-X",
            "Synthetic title",
            first_coordinates,
            display,
            "Synthetic citation.",
        )
        second = PublicLocus(
            "https://www.ithkuil.net/example.htm",
            "NI-X",
            "Synthetic title",
            second_coordinates,
            display,
            "Synthetic citation.",
        )
        self.assertEqual(first.identifier, second.identifier)
        self.assertNotEqual(first.iri, second.iri)

    def test_url_parser_must_not_silently_discard_raw_controls_or_whitespace(self):
        for url in (
            " https://ithkuil.net/source.htm",
            "https://ithkuil.net/so\nurce.htm",
            "https://ithkuil.net/so\turce.htm",
            "https://ithkuil.net/source name.htm",
            "https://ithkuil.net/\ud800.htm",
        ):
            with self.subTest(url=repr(url)):
                self.assertFalse(public_source_url(url))
        self.assertTrue(public_source_url("https://ithkuil.net/New_Ithkuil_Lexicon.pdf"))

    def test_literal_screening_rejects_arbitrary_external_urls_without_domain_specific_hacks(self):
        self.assertIsNone(safe_public_literal("source https://other-private.example/notes"))
        self.assertIsNone(safe_public_literal("source https%3A%2F%2Fother-private.example%2Fnotes"))
        text = "New Ithkuil source title"
        self.assertEqual(safe_public_literal(text), text)

    def test_literal_screening_rejects_nested_percent_encoded_private_paths_without_rewriting_safe_text(self):
        for value in (
            "file:///Users/example/private-source",
            "file%3A%2F%2F%2FUsers%2Fexample%2Fprivate-source",
            "file%253A%252F%252F%252FUsers%252Fexample%252Fprivate-source",
            "file%25253A%25252F%25252F%25252FUsers%25252Fexample%25252Fprivate-source",
            "file%252525253A%252525252F%252525252F%252525252FUsers%252525252Fexample",
        ):
            with self.subTest(value=value):
                self.assertIsNone(safe_public_literal(value))
        harmless = "%C4%8C"
        self.assertEqual(safe_public_literal(harmless), harmless)


if __name__ == "__main__":
    unittest.main()
