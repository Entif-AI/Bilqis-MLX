from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

from lib.ithkuil.tests.source_expectations import CORE
from collections import Counter, defaultdict
import json
from pathlib import Path
import unittest

from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.resolver import (
    GRAMMAR_ATOM_CLASSES,
    RecordRef,
    resolve_identities,
)


ROOT = ITHKUIL_ROOT
SOURCE_ROOT = ROOT / "_data/csv"
FIXTURE_ROOT = FIXTURES
EXPECTED = json.loads((FIXTURE_ROOT / "skos_identity_resolution_expected.json").read_text(encoding="utf-8"))


class IdentityResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(SOURCE_ROOT).require_valid()
        cls.resolution = resolve_identities(cls.closure)

    def resource(self, iri):
        return next(resource for resource in self.resolution.resources if resource.identity.iri == iri)

    def replace_table(self, closure, table_name, transform):
        tables = []
        for table in closure.tables:
            if table.name != table_name:
                tables.append(table)
                continue
            rows = tuple(transform(row) for row in table.rows)
            tables.append(LoadedTable(table.name, table.columns, rows))
        return CompilerClosure(closure.manifest_version, tuple(tables))

    def mutate_row(self, row, **changes):
        values = dict(row.values)
        values.update(changes)
        return FrozenRow(tuple((key, values[key]) for key, _ in row.values))

    def append_row(self, closure, table_name, source_row, **changes):
        new_row = self.mutate_row(source_row, **changes)
        tables = []
        for table in closure.tables:
            if table.name == table_name:
                tables.append(LoadedTable(table.name, table.columns, table.rows + (new_row,)))
            else:
                tables.append(table)
        return CompilerClosure(closure.manifest_version, tuple(tables))

    def identities(self, resolution):
        return tuple(resource.identity for resource in resolution.resources)

    def test_current_corpus_matches_literal_counts_and_has_no_held_issues(self):
        expected = EXPECTED["counts"]
        semantic_rows = sum(
            len(self.closure.table(name).rows)
            for name in ("morphemes_atomic", "root_senses", "lexicon_roots", "lexicon_root_senses")
        )
        self.assertEqual(semantic_rows, CORE["semantic_rows"])
        self.assertEqual(len(self.resolution.resources), expected["resources"])
        self.assertEqual(len(self.resolution.issues), expected["issues"])
        kinds = Counter(resource.identity.kind for resource in self.resolution.resources)
        self.assertEqual(kinds["grammar"], expected["grammar"])
        self.assertEqual(kinds["sense"], expected["senses"])
        self.assertEqual(kinds["root"], expected["atomic_roots"] + expected["lexicon_roots"])
        atomic_refs = {
            ref.key for resource in self.resolution.resources if resource.identity.kind == "root"
            for ref in resource.source_records if ref.table == "morphemes_atomic"
        }
        lexicon_refs = {
            ref.key for resource in self.resolution.resources if resource.identity.kind == "root"
            for ref in resource.source_records if ref.table == "lexicon_roots"
        }
        self.assertEqual(len(atomic_refs), expected["atomic_roots"])
        self.assertEqual(len(lexicon_refs), expected["lexicon_roots"])

    def test_register_duplicate_form_merges_one_concept_and_preserves_both_families(self):
        expected = EXPECTED["register_nrr"]
        resource = self.resource(expected["iri"])
        self.assertEqual(resource.role, "concept")
        self.assertEqual(resource.families, tuple(expected["families"]))
        self.assertEqual(
            [(ref.table, ref.key) for ref in resource.source_records],
            [tuple(item) for item in expected["source_records"]],
        )
        self.assertEqual([item.lexical_form for item in resource.realizations], expected["lexical_forms"])
        self.assertEqual(resource.schemes, (Identity("scheme", ("new-ithkuil",)),))
        notes = [text for text in resource.texts if text.field == "semantic_summary"]
        raw_notation = [text for text in resource.texts if text.field == "surface_form_raw"]
        self.assertTrue(notes)
        self.assertEqual([text.text for text in raw_notation], ["∅", "∅"])
        self.assertTrue(all(text.language is None for text in raw_notation))
        self.assertTrue(all(item.condition == "unmarked/default register boundary" for item in resource.realizations))
        self.assertTrue(all(text.scope == "realization" and text.role == "source_note" for text in notes))

    def test_root_shapes_and_source_pref_labels_are_literal(self):
        atomic = EXPECTED["atomic_root"]
        resource = self.resource(atomic["iri"])
        self.assertEqual(resource.role, "root")
        self.assertEqual(resource.schemes, ())
        self.assertEqual(resource.families, (atomic["family"],))
        self.assertEqual(resource.source_records, (RecordRef(*atomic["source_record"]),))
        self.assertEqual([r.lexical_form for r in resource.realizations], [atomic["lexical_form"]])

        lex = EXPECTED["lexicon_root"]
        resource = self.resource(lex["iri"])
        self.assertEqual(resource.source_records, (RecordRef(*lex["source_record"]),))
        self.assertEqual([r.lexical_form for r in resource.realizations], [lex["lexical_form"]])
        labels = [text.text for text in resource.texts if text.role == "source_pref_label"]
        self.assertEqual(labels, [lex["pref_label"]])
        self.assertTrue(all(text.language == "en" for text in resource.texts if text.role == "source_pref_label"))

        raw_case = EXPECTED["raw_vs_normalized_root"]
        resource = self.resource(raw_case["iri"])
        self.assertEqual([item.lexical_form for item in resource.realizations], [raw_case["normalized"]])
        raw = [text for text in resource.texts if text.field == "root_form_raw"]
        self.assertEqual(
            [(text.text, text.role, text.language) for text in raw],
            [(raw_case["raw"], "source_notation_raw", None)],
        )

    def test_distinct_senses_with_same_english_definition_remain_distinct(self):
        rows = EXPECTED["same_label_distinct_senses"]
        resources = [self.resource(item["iri"]) for item in rows]
        self.assertNotEqual(resources[0].identity, resources[1].identity)
        definitions = []
        for resource, item in zip(resources, rows):
            self.assertIn(RecordRef(*item["record"]), resource.source_records)
            self.assertEqual(resource.realizations, ())
            self.assertEqual(resource.schemes, (Identity("scheme", ("new-ithkuil",)),))
            definitions.append(next(text.text for text in resource.texts if text.role == "identity_definition"))
            self.assertFalse(any(text.role == "source_pref_label" for text in resource.texts))
        self.assertEqual(definitions[0], definitions[1])

    def test_shuffled_closure_is_exactly_resolution_invariant(self):
        shuffled = CompilerClosure(
            self.closure.manifest_version,
            tuple(LoadedTable(table.name, table.columns, tuple(reversed(table.rows))) for table in reversed(self.closure.tables)),
        )
        self.assertEqual(resolve_identities(shuffled), self.resolution)

    def test_mutable_labels_do_not_remint_identities(self):
        atoms = self.closure.table("morphemes_atomic").rows
        counts = Counter((row["category_code"], row["value_code"]) for row in atoms if row["morpheme_class"] in GRAMMAR_ATOM_CLASSES)
        target = next(row for row in atoms if row["morpheme_class"] in GRAMMAR_ATOM_CLASSES and counts[(row["category_code"], row["value_code"])] == 1)
        changed_atoms = self.replace_table(
            self.closure, "morphemes_atomic",
            lambda row: self.mutate_row(row, value_name="changed display label", category_name="changed category label") if row is target else row,
        )
        lex_target = self.closure.table("lexicon_roots").rows[0]
        changed = self.replace_table(
            changed_atoms, "lexicon_roots",
            lambda row: self.mutate_row(row, root_gloss="changed root display gloss") if row["lexicon_root_id"] == lex_target["lexicon_root_id"] else row,
        )
        self.assertEqual(self.identities(resolve_identities(changed)), self.identities(self.resolution))

    def test_source_hash_remints_do_not_remint_identities(self):
        changed = self.replace_table(
            self.closure, "lexicon_roots",
            lambda row: self.mutate_row(row, tracked_pdf_sha256="f" * 64, canonical_source_sha256="e" * 64),
        )
        changed = self.replace_table(
            changed, "lexicon_root_senses",
            lambda row: self.mutate_row(row, tracked_pdf_sha256="d" * 64, source_text_sha256="c" * 64),
        )
        self.assertEqual(self.identities(resolve_identities(changed)), self.identities(self.resolution))

    def test_same_coordinates_different_legacy_meaning_are_held_with_both_refs(self):
        source = self.closure.table("root_senses").rows[0]
        duplicate_id = "SENSE-SYNTHETIC-CONFLICT"
        changed = self.append_row(
            self.closure, "root_senses", source,
            sense_id=duplicate_id, sense_summary=source["sense_summary"] + " DIFFERENT MEANING",
        )
        resolution = resolve_identities(changed)
        issues = [issue for issue in resolution.issues if issue.code == "CONFLICTING_SEMANTIC_MEANING"]
        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual(
            set(issue.record_refs),
            {RecordRef("root_senses", source["sense_id"]), RecordRef("root_senses", duplicate_id)},
        )
        self.assertIn("field=sense_summary", issue.details)
        self.assertFalse(any(resource.identity.keys == issue.semantic_key for resource in resolution.resources))

    def test_conflicting_root_blocks_its_senses_instead_of_leaving_children(self):
        root = self.closure.table("lexicon_roots").rows[0]
        changed = self.append_row(
            self.closure, "lexicon_roots", root,
            root_gloss=root["root_gloss"] + " DIFFERENT ROOT MEANING",
        )
        resolution = resolve_identities(changed)
        root_identity = Identity("root", (root["source_id"], root["lexicon_root_id"]))
        self.assertFalse(any(resource.identity == root_identity for resource in resolution.resources))
        expected_sense_refs = {
            RecordRef("lexicon_root_senses", row["lexicon_sense_id"])
            for row in self.closure.table("lexicon_root_senses").rows
            if row["lexicon_root_id"] == root["lexicon_root_id"]
        }
        orphan_issues = [
            issue for issue in resolution.issues
            if issue.code == "SENSE_ROOT_NOT_RESOLVED"
            and issue.record_refs
            and issue.record_refs[0].table == "lexicon_root_senses"
        ]
        self.assertEqual({issue.record_refs[0] for issue in orphan_issues}, expected_sense_refs)
        self.assertTrue(all(root_identity.iri in issue.details for issue in orphan_issues))

    def test_cross_table_same_identity_conflict_removes_root_and_final_orphans(self):
        legacy_sense = self.closure.table("root_senses").rows[0]
        atom_id = legacy_sense["atomic_id"]
        atom = next(row for row in self.closure.table("morphemes_atomic").rows if row["atomic_id"] == atom_id)
        lex = self.closure.table("lexicon_roots").rows[0]
        changed = self.append_row(
            self.closure, "lexicon_roots", lex,
            lexicon_root_id=atom_id,
            source_id=atom["primary_source_id"],
            root_gloss="synthetic incompatible second source record",
        )
        resolution = resolve_identities(changed)
        identity = Identity("root", (atom["primary_source_id"], atom_id))
        conflicts = [issue for issue in resolution.issues if issue.code == "SOURCE_IDENTITY_CONFLICT"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].semantic_key, identity.keys)
        self.assertEqual({ref.table for ref in conflicts[0].record_refs}, {"morphemes_atomic", "lexicon_roots"})
        self.assertFalse(any(resource.identity == identity for resource in resolution.resources))
        self.assertTrue(any(
            issue.code == "SENSE_ROOT_NOT_RESOLVED"
            and RecordRef("root_senses", legacy_sense["sense_id"]) in issue.record_refs
            for issue in resolution.issues
        ))

    def test_missing_semantic_key_and_unknown_atom_shape_are_held(self):
        atoms = self.closure.table("morphemes_atomic").rows
        counts = Counter((row["category_code"], row["value_code"]) for row in atoms if row["morpheme_class"] in GRAMMAR_ATOM_CLASSES)
        source = next(row for row in atoms if row["morpheme_class"] in GRAMMAR_ATOM_CLASSES and counts[(row["category_code"], row["value_code"])] == 1)
        missing = self.replace_table(
            self.closure, "morphemes_atomic",
            lambda row: self.mutate_row(row, category_code="") if row["atomic_id"] == source["atomic_id"] else row,
        )
        missing_result = resolve_identities(missing)
        self.assertTrue(any(issue.code == "MISSING_SEMANTIC_KEY" and RecordRef("morphemes_atomic", source["atomic_id"]) in issue.record_refs for issue in missing_result.issues))

        unknown = self.replace_table(
            self.closure, "morphemes_atomic",
            lambda row: self.mutate_row(row, morpheme_class="future_unknown_shape") if row["atomic_id"] == source["atomic_id"] else row,
        )
        unknown_result = resolve_identities(unknown)
        self.assertTrue(any(issue.code == "UNKNOWN_ATOM_SHAPE" and RecordRef("morphemes_atomic", source["atomic_id"]) in issue.record_refs for issue in unknown_result.issues))

    def test_value_name_is_pref_label_but_semantic_summary_is_realization_scoped_note(self):
        resource = self.resource("https://github.com/Entif-AI/Bilqis-MLX/id/grammar/REGISTER/DSV")
        pref = [text for text in resource.texts if text.field == "value_name"]
        notes = [text for text in resource.texts if text.field == "semantic_summary"]
        self.assertTrue(pref and notes)
        self.assertTrue(all(text.role == "source_pref_label" and text.language == "en" for text in pref))
        self.assertTrue(all(text.role == "source_note" and text.scope == "realization" for text in notes))
        self.assertGreater(len({text.text for text in notes}), 1)


if __name__ == "__main__":
    unittest.main()
