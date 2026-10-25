
from lib.ithkuil.tests.source_expectations import LEXICON
import csv
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.preflight import preflight
from lib.ithkuil.src.skos.preflight_manifest import load_manifest
ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "_data/csv"
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
NEGATIVE = json.loads(
    (FIXTURE_ROOT / "skos_preflight_negative_cases.json").read_text(encoding="utf-8")
)
class PreflightContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest()
    def case(self, name):
        return NEGATIVE["cases"][name]
    def assert_finding(self, result, name, *, key=None):
        expected = self.case(name)
        matches = [
            finding
            for finding in result.findings
            if finding.code == expected["code"]
            and finding.table == expected["table"]
            and finding.field == expected["field"]
        ]
        self.assertTrue(matches, (name, result.as_dict()))
        if key is None:
            key = expected.get("key")
        if key is not None:
            self.assertIn(key, {finding.key for finding in matches})
        self.assertIsNone(result.closure)
        return matches[0]
    def clone(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name) / "csv"
        shutil.copytree(SOURCE_ROOT, root)
        return temp, root
    def table_path(self, root, table_name):
        return root / self.manifest.table(table_name).path
    def rows(self, root, table_name):
        path = self.table_path(root, table_name)
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            return list(reader)
    def write_rows(self, root, table_name, rows):
        path = self.table_path(root, table_name)
        with path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows)
    def mutate_dict_rows(self, root, table_name, mutate):
        path = self.table_path(root, table_name)
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames
            rows = list(reader)
        mutate(rows)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    def test_manifest_is_versioned_exact_and_declares_non_core_ownership(self):
        self.assertEqual(self.manifest.version, "bilqis.skos.compiler-input/v1")
        self.assertEqual(
            [table.name for table in self.manifest.tables],
            [
                "source_manifest",
                "curriculum_manifest",
                "source_sections",
                "source_tables",
                "source_assertions",
                "grammatical_categories",
                "morphemes_atomic",
                "root_senses",
                "lexicon_roots",
                "lexicon_root_senses",
                "lexicon_root_evidence",
                "morpheme_compositions",
            ],
        )
        self.assertEqual(
            self.manifest.table("curriculum_manifest").role,
            "provenance_support_only",
        )
        self.assertEqual(
            self.manifest.table("morpheme_compositions").role,
            "non_core_fk_support_only",
        )
        deferred = dict(self.manifest.deferred_non_core)
        self.assertIn("bilqis_mapping_tables", deferred)
        self.assertIn("allomorph_rules", deferred)
        self.assertIn("affix_degrees", deferred)
        self.assertIn("CONFLICTING_SEMANTIC_KEY", self.manifest.reason_codes)
    def test_current_tracked_corpus_returns_immutable_normalized_closure(self):
        result = preflight(SOURCE_ROOT)
        self.assertEqual(
            result.as_dict(),
            {
                "manifest_version": "bilqis.skos.compiler-input/v1",
                "ok": True,
                "findings": [],
            },
        )
        closure = result.require_valid()
        self.assertEqual(
            [(table.name, len(table.rows)) for table in closure.tables],
            [
                ("source_manifest", 18),
                ("curriculum_manifest", 8),
                ("source_sections", 337),
                ("source_tables", 727),
                ("source_assertions", 4709),
                ("grammatical_categories", 35),
                ("morphemes_atomic", 772),
                ("root_senses", 200),
                ("lexicon_roots", LEXICON["root_rows"]),
                ("lexicon_root_senses", LEXICON["sense_rows"]),
                ("lexicon_root_evidence", LEXICON["evidence_rows"]),
                ("morpheme_compositions", 1917),
            ],
        )
        with self.assertRaises(FrozenInstanceError):
            closure.tables = ()
        with self.assertRaises(FrozenInstanceError):
            closure.table("morphemes_atomic").rows[0].values = ()
    def test_missing_table_blocks_before_any_output_artifact(self):
        temp, root = self.clone()
        try:
            self.table_path(root, "root_senses").unlink()
            output = Path(temp.name) / "canonical.nt"
            result = preflight(root)
            self.assert_finding(result, "missing_table")
            with self.assertRaises(ProfileError) as caught:
                result.require_valid()
            self.assertEqual(caught.exception.code, "MISSING_TABLE")
            self.assertFalse(output.exists())
        finally:
            temp.cleanup()
    def test_missing_column_and_duplicate_header_are_distinct(self):
        for mode in ("missing", "duplicate"):
            temp, root = self.clone()
            try:
                if mode == "missing":
                    rows = self.rows(root, "morphemes_atomic")
                    index = rows[0].index("category_code")
                    rows = [
                        [value for i, value in enumerate(row) if i != index]
                        for row in rows
                    ]
                    self.write_rows(root, "morphemes_atomic", rows)
                    self.assert_finding(preflight(root), "missing_column")
                else:
                    rows = self.rows(root, "source_sections")
                    rows[0][rows[0].index("chapter_number")] = "source_id"
                    self.write_rows(root, "source_sections", rows)
                    self.assert_finding(preflight(root), "duplicate_header")
            finally:
                temp.cleanup()
    def test_duplicate_and_blank_primary_keys_block_with_literal_fields(self):
        temp, root = self.clone()
        try:
            rows = self.rows(root, "grammatical_categories")
            rows.append(list(rows[1]))
            duplicate_key = rows[1][rows[0].index("category_id")]
            self.write_rows(root, "grammatical_categories", rows)
            self.assert_finding(preflight(root), "duplicate_pk", key=duplicate_key)
        finally:
            temp.cleanup()
        temp, root = self.clone()
        try:
            def blank(rows):
                rows[0]["atomic_id"] = ""
            self.mutate_dict_rows(root, "morphemes_atomic", blank)
            self.assert_finding(preflight(root), "blank_pk", key="")
        finally:
            temp.cleanup()
    def test_malformed_utf8_and_malformed_csv_are_blocking_load_failures(self):
        temp, root = self.clone()
        try:
            path = self.table_path(root, "source_sections")
            path.write_bytes(path.read_bytes() + b"\xff")
            self.assert_finding(preflight(root), "malformed_utf8")
        finally:
            temp.cleanup()
        temp, root = self.clone()
        try:
            path = self.table_path(root, "source_sections")
            path.write_text(path.read_text(encoding="utf-8") + '"unterminated\n', encoding="utf-8")
            self.assert_finding(preflight(root), "malformed_csv")
        finally:
            temp.cleanup()
    def test_unknown_fk_and_source_assertion_entity_are_source_qualified(self):
        temp, root = self.clone()
        try:
            def unknown_source(rows):
                rows[0]["source_id"] = "SOURCE-NOT-REAL"
            self.mutate_dict_rows(root, "grammatical_categories", unknown_source)
            result = preflight(root)
            finding = self.assert_finding(result, "unknown_fk")
            self.assertIn("target=source_manifest", finding.details)
            with self.assertRaises(ProfileError) as caught:
                result.require_valid()
            self.assertEqual(caught.exception.code, "UNKNOWN_FOREIGN_KEY")
            self.assertIn("table=grammatical_categories", caught.exception.details)
            self.assertIn("field=source_id", caught.exception.details)
            self.assertTrue(
                any(detail.startswith("locus=row=") for detail in caught.exception.details)
            )
        finally:
            temp.cleanup()
        temp, root = self.clone()
        try:
            def cross_source(rows):
                row = next(
                    row
                    for row in rows
                    if row["primary_source_id"] != "NI-WEB-CH03"
                )
                row["primary_section_id"] = "NI-WEB-CH03:3.1"
            self.mutate_dict_rows(root, "morphemes_atomic", cross_source)
            finding = self.assert_finding(preflight(root), "cross_source_section")
            self.assertIn("target=source_sections", finding.details)
        finally:
            temp.cleanup()
        temp, root = self.clone()
        try:
            def unknown_entity(rows):
                row = next(row for row in rows if row["entity_kind"] == "atomic_morpheme")
                row["entity_id"] = "ATOM-NOT-REAL"
            self.mutate_dict_rows(root, "source_assertions", unknown_entity)
            finding = self.assert_finding(preflight(root), "unknown_assertion_entity")
            self.assertIn("target=morphemes_atomic", finding.details)
        finally:
            temp.cleanup()
    def test_missing_atomic_source_assertion_is_reported(self):
        temp, root = self.clone()
        try:
            with self.table_path(root, "morphemes_atomic").open(
                newline="", encoding="utf-8"
            ) as handle:
                atomic_id = next(csv.DictReader(handle))["atomic_id"]
            def remove(rows):
                rows[:] = [
                    row
                    for row in rows
                    if not (
                        row["entity_kind"] == "atomic_morpheme"
                        and row["entity_id"] == atomic_id
                    )
                ]
            self.mutate_dict_rows(root, "source_assertions", remove)
            self.assert_finding(
                preflight(root), "missing_source_assertion", key=atomic_id
            )
        finally:
            temp.cleanup()
    def test_invalid_enum_and_source_url_binding_fail_closed(self):
        temp, root = self.clone()
        try:
            def invalid_state(rows):
                rows[0]["realization_type"] = "future_state"
            self.mutate_dict_rows(root, "morphemes_atomic", invalid_state)
            self.assert_finding(preflight(root), "invalid_enum")
        finally:
            temp.cleanup()
        temp, root = self.clone()
        try:
            def bad_url(rows):
                rows[0]["primary_source_url"] = "https://example.invalid/source"
            self.mutate_dict_rows(root, "morphemes_atomic", bad_url)
            self.assert_finding(preflight(root), "source_url_binding")
        finally:
            temp.cleanup()
    def test_semantic_key_conflict_is_structural_not_realization_summary(self):
        temp, root = self.clone()
        try:
            def conflict(rows):
                matches = [
                    row
                    for row in rows
                    if row["category_code"] == "CASE" and row["value_code"] == "ABL"
                ]
                self.assertGreaterEqual(len(matches), 2)
                matches[0]["value_name"] = "synthetic conflicting source label"
            self.mutate_dict_rows(root, "morphemes_atomic", conflict)
            first = preflight(root)
            self.assert_finding(first, "semantic_conflict", key="CASE|ABL")
            rows = self.rows(root, "morphemes_atomic")
            self.write_rows(root, "morphemes_atomic", [rows[0], *reversed(rows[1:])])
            self.assertEqual(first.as_dict(), preflight(root).as_dict())
        finally:
            temp.cleanup()
        temp, root = self.clone()
        try:
            def realization_summary_only(rows):
                matches = [
                    row
                    for row in rows
                    if row["category_code"] == "CASE" and row["value_code"] == "ABL"
                ]
                matches[0]["semantic_summary"] = "different realization-only summary"
            self.mutate_dict_rows(root, "morphemes_atomic", realization_summary_only)
            self.assertTrue(preflight(root).ok)
        finally:
            temp.cleanup()
    def test_lexicon_child_binding_is_source_qualified(self):
        temp, root = self.clone()
        try:
            def drift(rows):
                rows[0]["root_form_raw"] = "SYNTHETIC-DRIFT"
            self.mutate_dict_rows(root, "lexicon_root_senses", drift)
            self.assert_finding(preflight(root), "lexicon_parent_binding")
        finally:
            temp.cleanup()
    def test_repeated_root_keeps_its_later_observation_locus(self):
        closure = preflight(SOURCE_ROOT).require_valid()
        parent = next(row for row in closure.table("lexicon_roots").rows if row["root_form_raw"] == "-ŠMW-")
        sense = next(row for row in closure.table("lexicon_root_senses").rows
                     if row["root_form_raw"] == "-ŠMW-" and row["lexicon_chapter"] == "5")
        self.assertEqual(parent["lexicon_chapter"], "2")
        self.assertEqual(sense["lexicon_root_id"], parent["lexicon_root_id"])
        self.assertEqual(sense["tracked_pdf_name"], "New Ithkuil Lexicon - Chapter 05 - Miscellaneous Entities.pdf")
        self.assertEqual(sense["source_pdf_page"], "5")
    def test_repeated_root_rejects_an_unbound_observation_artifact(self):
        temp, root = self.clone()
        try:
            def drift(rows):
                row = next(row for row in rows if row["root_form_raw"] == "-ŠMW-" and row["lexicon_chapter"] == "5")
                row["tracked_pdf_sha256"] = "0" * 64
            self.mutate_dict_rows(root, "lexicon_root_senses", drift)
            result = preflight(root)
            self.assertTrue(any(finding.code == "LEXICON_PARENT_BINDING_CONFLICT"
                                and finding.table == "lexicon_root_senses"
                                and "tracked_pdf_sha256" in finding.field for finding in result.findings))
            self.assertIsNone(result.closure)
        finally:
            temp.cleanup()
    def test_row_reordering_preserves_exact_normalized_closure(self):
        expected = preflight(SOURCE_ROOT).require_valid()
        temp, root = self.clone()
        try:
            for spec in self.manifest.tables:
                rows = self.rows(root, spec.name)
                self.write_rows(root, spec.name, [rows[0], *reversed(rows[1:])])
            actual = preflight(root).require_valid()
            self.assertEqual(actual, expected)
        finally:
            temp.cleanup()
if __name__ == "__main__":
    unittest.main()
