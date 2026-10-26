"""Source-backed concept-definition normalization proofs for issue #46."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest

from rdflib import URIRef
from rdflib.namespace import SKOS

from lib.ithkuil.src.skos.definition import (
    CONCEPT_DEFINITION,
    DEFINITION_CLASSES,
    REALIZATION_NOTE,
    definition_graph,
    normalize_atomic_definitions,
)
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import LoadedTable
from lib.ithkuil.src.skos.realization import normalize_atomic_realizations
from lib.ithkuil.src.skos.resolver import resolve_identities


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "_data" / "csv"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SOURCE = json.loads((FIXTURES / "definition_source_expected.json").read_text(encoding="utf-8"))
EXPECTED = json.loads((FIXTURES / "definition_normalized_expected.json").read_text(encoding="utf-8"))


class DefinitionNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure = preflight(SOURCE_ROOT).require_valid()
        cls.resolution = resolve_identities(cls.closure)
        cls.realizations = normalize_atomic_realizations(cls.closure, cls.resolution)
        cls.normalized = normalize_atomic_definitions(cls.closure, cls.resolution, cls.realizations)
        cls.resources = {resource.identity.iri: resource for resource in cls.normalized.resolution.resources}
        cls.definitions = {item.identity_iri: item for item in cls.normalized.definitions}
        cls.candidates = {}
        for candidate in cls.normalized.candidates:
            cls.candidates.setdefault(candidate.identity_iri, []).append(candidate)

    def test_source_fixture_pins_current_summary_census(self) -> None:
        self.assertEqual(
            hashlib.sha256((SOURCE_ROOT / "morphemes_atomic.csv").read_bytes()).hexdigest(),
            SOURCE["tracked_input_digests"]["morphemes_atomic.csv"],
        )
        self.assertEqual(
            hashlib.sha256((SOURCE_ROOT / "source_assertions.csv").read_bytes()).hexdigest(),
            SOURCE["tracked_input_digests"]["source_assertions.csv"],
        )
        self.assertEqual(
            SOURCE["counts"],
            {
                "divergent_case_keys": 32,
                "divergent_register_keys": 6,
                "grammar_rows": 607,
                "grammar_semantic_keys": 485,
                "multi_divergent_summary_keys": 38,
                "multi_same_summary_keys": 84,
                "single_summary_keys": 363,
            },
        )
        rows = {row["atomic_id"]: row for row in self.closure.table("morphemes_atomic").rows}
        assertions = {
            row["entity_id"]: row["assertion_id"]
            for row in self.closure.table("source_assertions").rows
            if row["entity_kind"] == "atomic_morpheme"
        }
        for fixture_rows in SOURCE["examples"].values():
            for expected in fixture_rows:
                row = rows[expected["atomic_id"]]
                for source_field, fixture_field in (
                    ("value_name", "value_name"),
                    ("semantic_summary", "semantic_summary"),
                    ("realization_type", "realization_type"),
                    ("allomorph_group_id", "allomorph_group_id"),
                    ("allomorph_condition", "allomorph_condition"),
                    ("morpheme_class", "morpheme_class"),
                    ("morpheme_family", "morpheme_family"),
                    ("slot", "slot"),
                    ("primary_source_id", "primary_source_id"),
                    ("primary_section_id", "primary_section_id"),
                    ("primary_table_id", "primary_table_id"),
                    ("primary_source_line", "primary_source_line"),
                    ("primary_source_url", "primary_source_url"),
                    ("primary_source_anchor", "primary_source_anchor"),
                ):
                    self.assertEqual(row[source_field], expected[fixture_field])
                self.assertEqual(assertions[expected["atomic_id"]], expected["source_assertion_id"])

    def test_current_corpus_has_literal_definition_and_note_counts(self) -> None:
        counts = Counter(candidate.classification for candidate in self.normalized.candidates)
        self.assertEqual(counts[CONCEPT_DEFINITION], 563)
        self.assertEqual(counts[REALIZATION_NOTE], 44)
        self.assertEqual(set(counts), {CONCEPT_DEFINITION, REALIZATION_NOTE})
        self.assertEqual(self.normalized.definition_count, 479)
        self.assertEqual(self.normalized.added_issues, ())
        grammar_iris = {
            resource.identity.iri
            for resource in self.normalized.resolution.resources
            if resource.identity.kind == "grammar"
        }
        self.assertEqual(len(grammar_iris), 485)
        self.assertEqual(len(grammar_iris - set(self.definitions)), 6)
        self.assertEqual(
            set(DEFINITION_CLASSES),
            {"CONCEPT_DEFINITION", "REALIZATION_NOTE", "SOURCE_EDITORIAL", "HELD_CONFLICT", "IGNORE_WITH_REASON"},
        )

    def test_literal_cases_have_exact_definition_note_outputs(self) -> None:
        for expected in EXPECTED["cases"].values():
            iri = expected["identity_iri"]
            actual_definition = self.definitions.get(iri)
            self.assertEqual(actual_definition.text if actual_definition else None, expected["definition"])
            actual_candidates = [
                {
                    "atomic_id": item.record_ref.key,
                    "classification": item.classification,
                    "reason": item.reason,
                    "text": item.text,
                }
                for item in sorted(self.candidates[iri])
            ]
            self.assertEqual(actual_candidates, expected["candidates"])
            resource = self.resources[iri]
            notes = sorted(
                text.text
                for text in resource.texts
                if text.field == "semantic_summary" and text.role == "source_note"
            )
            self.assertEqual(notes, sorted(expected["remaining_realization_notes"]))

    def test_definition_graph_uses_exact_source_text_without_paraphrase(self) -> None:
        graph = definition_graph(self.normalized)
        self.assertEqual(len(graph), 479)
        self.assertIn(
            (
                URIRef("https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CASE/ACT"),
                SKOS.definition,
                next(iter(graph.objects(
                    URIRef("https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CASE/ACT"),
                    SKOS.definition,
                ))),
            ),
            graph,
        )
        self.assertEqual(
            [str(value) for value in graph.objects(
                URIRef("https://github.com/Entif-AI/Bilqis-MLX/id/grammar/CASE/ACT"), SKOS.definition
            )],
            ["activative case"],
        )
        self.assertEqual(
            list(graph.objects(
                URIRef("https://github.com/Entif-AI/Bilqis-MLX/id/grammar/REGISTER/DSV"), SKOS.definition
            )),
            [],
        )

    def test_reordered_source_is_exactly_definition_invariant(self) -> None:
        reversed_closure = CompilerClosure(
            self.closure.manifest_version,
            tuple(
                LoadedTable(table.name, table.columns, tuple(reversed(table.rows)))
                for table in reversed(self.closure.tables)
            ),
        )
        resolution = resolve_identities(reversed_closure)
        realizations = normalize_atomic_realizations(reversed_closure, resolution)
        normalized = normalize_atomic_definitions(reversed_closure, resolution, realizations)
        self.assertEqual(normalized, self.normalized)
        self.assertEqual(set(definition_graph(normalized)), set(definition_graph(self.normalized)))


if __name__ == "__main__":
    unittest.main()
