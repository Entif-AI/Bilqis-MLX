import csv
import itertools
from pathlib import Path
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import SKOS

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.text import TextAssertion, project_text


RESOURCE = "https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CONFIGURATION/MFF"


class SourceTextTests(unittest.TestCase):
    def assertion(self, field="value_name", value="multiplex/fuzzy/fused", **kwargs):
        return TextAssertion(RESOURCE, field, value, kwargs.pop("language", "en"),
                             kwargs.pop("source_ref", "NI-WEB-CH03:T003"), **kwargs)

    def code(self, expected, rows):
        with self.assertRaises(ProfileError) as caught:
            project_text(rows)
        self.assertEqual(caught.exception.code, expected)
        return caught.exception

    def test_all_declared_properties_map_exactly(self):
        expected = {
            "value_name": "prefLabel", "category_name": "prefLabel", "root_gloss": "prefLabel",
            "preferred_label": "prefLabel", "alternate_label": "altLabel", "hidden_label": "hiddenLabel",
            "sense_summary": "definition", "definition": "definition", "scope_note": "scopeNote",
            "note": "note", "example": "example", "history_note": "historyNote",
            "change_note": "changeNote", "editorial_note": "editorialNote",
        }
        for field, prop in expected.items():
            with self.subTest(field=field):
                graph = project_text([self.assertion(field, "Source text")])
                self.assertEqual(set(graph), {(URIRef(RESOURCE), SKOS[prop], Literal("Source text", lang="en"))})

    def test_identical_assertions_deduplicate_and_language_tag_case_is_canonical(self):
        rows = [self.assertion(), self.assertion(language="EN", source_ref="NI-WEB-CH03:3.1")]
        self.assertEqual(set(project_text(rows)), {(URIRef(RESOURCE), SKOS.prefLabel,
                                                   Literal("multiplex/fuzzy/fused", lang="en"))})

    def test_two_languages_do_not_clone_resource_or_conflict(self):
        graph = project_text([self.assertion(), self.assertion(value="source supplied label", language="fr")])
        self.assertEqual(set(graph.subjects()), {URIRef(RESOURCE)})
        self.assertEqual({value.language for value in graph.objects(URIRef(RESOURCE), SKOS.prefLabel)}, {"en", "fr"})

    def test_conflicting_preferred_labels_fail_for_every_input_order(self):
        rows = [self.assertion(), self.assertion(value="different meaning", source_ref="OTHER-SOURCE")]
        messages = {str(self.code("PREFERRED_LABEL_CONFLICT", order)) for order in itertools.permutations(rows)}
        self.assertEqual(len(messages), 1)
        self.assertIn("different meaning", next(iter(messages)))

    def test_label_classes_are_disjoint(self):
        self.code("LABEL_KIND_CONFLICT", [self.assertion(), self.assertion("alternate_label")])
        graph = project_text([self.assertion(), self.assertion("alternate_label", "attested alternative"),
                              self.assertion("hidden_label", "attested historical spelling")])
        self.assertEqual(len(graph), 3)

    def test_realization_summaries_are_notes_and_cannot_overwrite_definition(self):
        graph = project_text([self.assertion("definition", "The source identity definition"),
                              self.assertion("semantic_summary", "word-final realization", scope="realization"),
                              self.assertion("semantic_summary", "initial realization", scope="realization")])
        self.assertEqual(set(graph.objects(URIRef(RESOURCE), SKOS.definition)),
                         {Literal("The source identity definition", lang="en")})
        self.assertEqual(set(graph.objects(URIRef(RESOURCE), SKOS.note)),
                         {Literal("word-final realization", lang="en"), Literal("initial realization", lang="en")})
        self.code("REALIZATION_TEXT_NOT_IDENTITY", [self.assertion("definition", "a realization", scope="realization")])

    def test_conflicting_identity_definitions_are_held(self):
        rows = [self.assertion("semantic_summary", "one meaning", scope="concept"),
                self.assertion("sense_summary", "another meaning")]
        for order in itertools.permutations(rows):
            self.code("DEFINITION_CONFLICT", order)

    def test_unclassified_summary_does_not_default_to_identity_definition(self):
        self.code("UNKNOWN_TEXT_SCOPE", [self.assertion("semantic_summary", "unclassified prose")])
        graph = project_text([self.assertion("semantic_summary", "source concept definition", scope="concept")])
        self.assertEqual(set(graph.objects(URIRef(RESOURCE), SKOS.definition)),
                         {Literal("source concept definition", lang="en")})

    def test_missing_source_language_and_generated_labels_are_held(self):
        self.code("MISSING_TEXT_SOURCE", [self.assertion(source_ref="")])
        for language in (None, "", "English label", "en_US"):
            self.code("MISSING_OR_INVALID_TEXT_LANGUAGE", [self.assertion(language=language)])
        self.code("GENERATED_TEXT_NOT_ADMITTED", [self.assertion(generated=True)])
        self.code("UNCLASSIFIED_SOURCE_TEXT", [self.assertion("unknown_role")])
        self.code("UNKNOWN_TEXT_SCOPE", [self.assertion(scope="unknown")])

    def test_long_prose_is_held_without_silent_truncation(self):
        self.code("SOURCE_TEXT_TOO_LONG", [self.assertion("note", "x" * 181)])
        self.assertEqual(len(project_text([self.assertion("note", "x" * 180)])), 1)

    def test_current_source_label_is_projected_without_paraphrase(self):
        path = Path(__file__).resolve().parents[1] / "_data/csv/morphemes_atomic.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            row = next(r for r in csv.DictReader(handle)
                       if r["category_code"] == "CONFIGURATION" and r["value_code"] == "MFF")
        graph = project_text([self.assertion("value_name", row["value_name"], source_ref=row["primary_table_id"])])
        self.assertEqual(set(graph), {(URIRef(RESOURCE), SKOS.prefLabel,
                                      Literal("multiplex/fuzzy/fused", lang="en"))})

    def test_source_punctuation_unicode_and_whitespace_roundtrip_exactly(self):
        value = "  C\u030c; ‘source wording’  "
        graph = project_text([self.assertion("note", value)])
        restored = Graph().parse(data=graph.serialize(format="nt"), format="nt")
        self.assertEqual(str(next(restored.objects(URIRef(RESOURCE), SKOS.note))), value)
        self.assertEqual(str(next(restored.objects(URIRef(RESOURCE), SKOS.note))).encode(), value.encode())

    def test_reordering_source_assertions_preserves_exact_graph(self):
        rows = [self.assertion(), self.assertion("note", "A note"), self.assertion("example", "A source example")]
        expected = set(project_text(rows))
        for order in itertools.permutations(rows):
            self.assertEqual(set(project_text(order)), expected)


if __name__ == "__main__":
    unittest.main()
