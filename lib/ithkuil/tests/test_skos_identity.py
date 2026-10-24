import csv
import itertools
import json
from pathlib import Path
import unittest

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.identity import (
    Identity, check_successor, from_record, identity_map, sense_from_source, validate_assignments,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "tests/fixtures/skos_identity.json").read_text())


class IdentityContractTests(unittest.TestCase):
    def assert_code(self, code, callable_, *args, **kwargs):
        with self.assertRaises(ProfileError) as caught:
            callable_(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_literal_expected_iris(self):
        for row in FIXTURES:
            with self.subTest(row=row):
                self.assertEqual(from_record(row["kind"], row["source_keys"]).iri, row["expected_iri"])
                self.assertTrue(row["survives_label_change"])

    def test_repeat_reorder_and_mutable_metadata_preserve_exact_identity(self):
        def build(rows):
            return identity_map(from_record(row["kind"], row["source_keys"]) for row in rows)
        expected = build(FIXTURES)
        self.assertEqual(build(FIXTURES), expected)
        self.assertEqual(build(reversed(FIXTURES)), expected)
        changed = [{**row, "source_keys": {**row["source_keys"], "label": "Changed",
                    "source_line": "999", "file_path": "/elsewhere.csv", "falkor_id": "77",
                    "source_version": "new-snapshot", "curriculum_order": "0"}} for row in FIXTURES]
        self.assertEqual(build(changed), expected)

    def test_distinct_source_senses_share_one_existing_root(self):
        def read(name):
            with (ROOT / "_data/csv" / name).open(newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))
        rows = {r["lexicon_sense_id"]: r for r in read("lexicon_root_senses.csv")}
        first, second = (rows[key] for key in ("LEXSENSE-5286ade9db42c7", "LEXSENSE-2219dd530fe045"))
        self.assertEqual(first["lexicon_root_id"], "LEXROOT-0bd881a56fac9e")
        self.assertEqual(second["lexicon_root_id"], first["lexicon_root_id"])
        iris = {from_record("sense", {**r, "root_id": r["lexicon_root_id"]}).iri for r in (first, second)}
        self.assertEqual(len(iris), 2)
        self.assertIn(first["lexicon_root_id"], {r["lexicon_root_id"] for r in read("lexicon_roots.csv")})

    def test_gloss_edit_and_reminted_legacy_hash_preserve_sense_iri(self):
        with (ROOT / "_data/csv/lexicon_root_senses.csv").open(newline="", encoding="utf-8") as handle:
            row = next(r for r in csv.DictReader(handle) if r["lexicon_sense_id"] == "LEXSENSE-5286ade9db42c7")
        original = {**row, "root_id": row["lexicon_root_id"]}
        changed = {**original, "sense_summary": row["sense_summary"] + ".",
                   "lexicon_sense_id": "LEXSENSE-af2682e356ae56", "source_text_sha256": "changed"}
        expected = "https://github.com/Entif-AI/Bilqis-MLX/id/sense/NI-LEXICON-CURRICULUM/LEXROOT-0bd881a56fac9e/STEM%201/BSC"
        self.assertEqual(from_record("sense", original).iri, expected)
        self.assertEqual(from_record("sense", changed).iri, expected)
        self.assertEqual(from_record("sense", {**original, "stem": "Stem 1", "specification": "bsc"}).iri, expected)

    def test_gloss_hash_alone_cannot_identify_sense(self):
        self.assert_code("MISSING_IDENTITY_KEY", from_record, "sense",
                         {"source_id": "NI-LEXICON-CURRICULUM", "sense_id": "LEXSENSE-5286ade9db42c7"})

    def test_sense_coordinate_validation_precedes_case_normalization(self):
        keys = {"source_id": "S", "root_id": "R", "stem": "STEM 1", "specification": "BSC"}
        self.assert_code("MISSING_OR_INVALID_IDENTITY_KEY", from_record, "sense", {**keys, "stem": 7})
        self.assert_code("INVALID_SENSE_COORDINATE", from_record, "sense", {**keys, "specification": "ß"})

    def test_declared_blank_scopes_have_explicit_distinct_keys(self):
        row = {"source_id": "S", "atomic_id": "R", "stem": "", "specification": ""}
        self.assertEqual(sense_from_source("root_senses", row).iri,
                         "https://github.com/Entif-AI/Bilqis-MLX/id/sense/S/R/ROOT-WIDE/UNSPECIFIED")
        lex = {"source_id": "S", "lexicon_root_id": "R", "stem": "", "specification": "CTE"}
        self.assertEqual(sense_from_source("lexicon_root_senses", lex).iri,
                         "https://github.com/Entif-AI/Bilqis-MLX/id/sense/S/R/ROOT-WIDE/CTE")
        self.assert_code("MISSING_SENSE_COORDINATE", sense_from_source, "root_senses",
                         {k: v for k, v in row.items() if k != "stem"})
        self.assert_code("INVALID_SENSE_COORDINATE", sense_from_source, "lexicon_root_senses",
                         {**lex, "specification": ""})
        self.assert_code("UNKNOWN_SENSE_SOURCE_SHAPE", sense_from_source, "unknown", row)

    def test_all_current_sense_coordinates_are_stable_under_text_and_legacy_id_edits(self):
        for table, count in (("root_senses", 200), ("lexicon_root_senses", 1615)):
            with (ROOT / "_data/csv" / (table + ".csv")).open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            original = {sense_from_source(table, row).iri for row in rows}
            changed = {sense_from_source(table, {**row, "sense_summary": row["sense_summary"] + ".",
                       "sense_id": "changed", "lexicon_sense_id": "changed"}).iri for row in reversed(rows)}
            self.assertEqual(len(original), count)
            self.assertEqual(changed, original)

    def test_key_change_and_case_change_are_distinct(self):
        values = ("MFF", "mff", "MFS", "a/b", "a%2Fb", "a?b", "a#b")
        iris = {Identity("grammar", ("CONFIGURATION", value)).iri for value in values}
        self.assertEqual(len(iris), len(values))

    def test_missing_keys_never_fall_back_to_label_or_store_id(self):
        for row in ({}, {"label": "MFF"}, {"falkor_id": "12"}, {"category_code": "CONFIGURATION"}):
            self.assert_code("MISSING_IDENTITY_KEY", from_record, "grammar", row)

    def test_invalid_key_inputs_fail(self):
        for value in ("", None, 123, " x", "x "):
            self.assert_code("MISSING_OR_INVALID_IDENTITY_KEY", Identity, "scheme", (value,))
        for value in (".", "..", "a\x00b", "a\nb", "\ud800"):
            self.assert_code("INVALID_IDENTITY_KEY", Identity, "scheme", (value,))
        self.assert_code("IDENTITY_KEY_NOT_NFC", Identity, "scheme", ("C\u030c",))
        self.assert_code("UNKNOWN_IDENTITY_KIND", Identity, "label", ("English",))
        self.assert_code("IDENTITY_KEY_ARITY", Identity, "grammar", ("MFF",))

    def test_synthetic_collision_names_both_identities_independent_of_order(self):
        a = Identity("grammar", ("CONFIGURATION", "MFF"))
        b = Identity("grammar", ("CONFIGURATION", "MFS"))
        messages = set()
        for claims in itertools.permutations(((a, a.iri), (b, a.iri))):
            error = self.assert_code("IRI_COLLISION", validate_assignments, claims)
            self.assertIn(repr(a), error.details)
            self.assertIn(repr(b), error.details)
            messages.add(str(error))
        self.assertEqual(len(messages), 1)

    def test_same_identity_two_iris_and_noncanonical_binding_fail(self):
        a = Identity("scheme", ("new-ithkuil",))
        self.assert_code("IDENTITY_DRIFT", validate_assignments, [(a, a.iri), (a, a.iri + "-other")])
        self.assert_code("NONCANONICAL_IRI", validate_assignments, [(a, "https://example.invalid/id")])

    def test_duplicate_identical_claims_are_idempotent(self):
        a = Identity("scheme", ("new-ithkuil",))
        self.assertEqual(validate_assignments([(a, a.iri), (a, a.iri)]), {a: a.iri})

    def test_semantic_change_requires_new_identity_and_explicit_successor(self):
        old = Identity("grammar", ("C", "V"))
        new = Identity("grammar", ("C", "V2"))
        check_successor(old, old, meaning_changed=False)
        self.assert_code("MEANING_CHANGE_REUSES_IRI", check_successor, old, old,
                         meaning_changed=True, successor_recorded=True)
        self.assert_code("SUCCESSOR_RECORD_REQUIRED", check_successor, old, new, meaning_changed=True)
        check_successor(old, new, meaning_changed=True, successor_recorded=True)


if __name__ == "__main__":
    unittest.main()
