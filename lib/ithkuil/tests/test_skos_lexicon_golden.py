from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, SKOS


STAGED = os.environ.get("BILQIS_STAGED_SKOS_PATH")
if STAGED:
    import lib.ithkuil.src.skos as _skos
    for path in reversed(STAGED.split(os.pathsep)):
        _skos.__path__.insert(0, path)

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.lexicon_dimensions import (
    SOURCE_LOCUS_KIND, SPECIFICATION, STEM, project_lexicon_dimensions,
)
from lib.ithkuil.src.skos.lexicon_links import load_root_sense_term, project_root_sense_links
from lib.ithkuil.src.skos.lexicon_roots import project_lexicon_roots
from lib.ithkuil.src.skos.lexicon_senses import project_lexicon_senses
from lib.ithkuil.src.skos.notation import NEW_ITHKUIL_DATATYPE_IRI
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable


LIB = Path(os.environ.get("BILQIS_ITHKUIL_LIB", Path(__file__).resolve().parents[1]))
DATA = LIB / "_data" / "csv"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = json.loads((FIXTURES / "skos_lexicon_golden_cases.json").read_text(encoding="utf-8"))
ROOT_SENSE_NEGATIVE = Path(os.environ.get("BILQIS_ROOT_SENSE_NEGATIVE_FIXTURE", FIXTURES / "skos_root_sense_negative.ttl"))


def staged_module_file(name: str) -> Path:
    module = __import__(f"lib.ithkuil.src.skos.{name}", fromlist=[name])
    return Path(module.__file__)


def replace_table(closure: CompilerClosure, name: str, rows) -> CompilerClosure:
    tables = []
    for table in closure.tables:
        if table.name == name:
            frozen = tuple(FrozenRow(tuple(row.items())) if isinstance(row, dict) else row for row in rows)
            tables.append(LoadedTable(table.name, table.columns, frozen))
        else:
            tables.append(table)
    return CompilerClosure(closure.manifest_version, tuple(tables))


class LexiconGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.roots = project_lexicon_roots(cls.closure)
        cls.senses = project_lexicon_senses(cls.closure)
        cls.dimensions = project_lexicon_dimensions(cls.closure, cls.senses)
        cls.term = load_root_sense_term(
            staged_module_file("lexicon_links").with_name("root_sense_extension.json"),
            source_csv_root=DATA,
            negative_fixture_path=ROOT_SENSE_NEGATIVE,
        )
        cls.links = project_root_sense_links(
            cls.closure, cls.term,
            roots=cls.roots, senses=cls.senses, dimensions=cls.dimensions,
        )

    def test_manifest_counts_match_all_four_projection_layers(self):
        expected = GOLDEN["expected_counts"]
        self.assertEqual(len(self.roots.records), expected["root_resources"])
        self.assertEqual(len(self.senses.records), expected["sense_concepts"])
        self.assertEqual(len(self.dimensions.graph), expected["dimension_triples"])
        self.assertEqual(len(self.links.graph), expected["root_sense_links"])

    def test_multi_unicode_root_matches_literal_expectations(self):
        case = GOLDEN["cases"]["multi_unicode_root"]
        record = next(item for item in self.roots.records if item.source_root_id == case["root_id"])
        subject = URIRef(case["root_iri"])
        self.assertEqual(record.identity.iri, case["root_iri"])
        self.assertEqual(record.raw_notation, case["raw_notation"])
        self.assertEqual(len(record.evidence_ids), case["evidence_count"])
        literal = Literal(case["raw_notation"], datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI), normalize=False)
        self.assertIn((subject, SKOS.notation, literal), self.roots.graph)
        self.assertEqual(len(list(self.links.graph.objects(subject, URIRef(self.term.iri)))),
                         case["sense_link_count"])
        self.assertEqual(sorted(map(str, self.roots.graph.objects(subject, DCTERMS.source))),
                         case["source_locus_iris"])

    def test_sense_cases_match_iri_dimensions_definition_and_locus(self):
        for name in (
            "direct_table", "prose_inherited_shape", "compact_inherited_shape",
            "combined_stems", "same_gloss_left", "same_gloss_right",
        ):
            with self.subTest(case=name):
                case = GOLDEN["cases"][name]
                subject = URIRef(case["sense_iri"])
                record = next(item for item in self.dimensions.records if item.sense.iri == case["sense_iri"])
                self.assertEqual(list(record.source_sense_ids), case["source_sense_ids"])
                self.assertEqual(record.stem, case["stem"])
                self.assertEqual(record.specification, case["specification"])
                self.assertEqual(list(record.source_locus_kinds), case["source_locus_kinds"])
                self.assertIn((subject, STEM, Literal(case["stem"])), self.dimensions.graph)
                self.assertIn((subject, SPECIFICATION, Literal(case["specification"])), self.dimensions.graph)
                self.assertEqual(sorted(map(str, self.senses.graph.objects(subject, DCTERMS.source))),
                                 case["source_locus_iris"])
                if "definition" in case:
                    self.assertIn((subject, SKOS.definition, Literal(case["definition"], lang="en")),
                                  self.senses.graph)

    def test_same_gloss_fixture_proves_source_distinct_identity(self):
        left = GOLDEN["cases"]["same_gloss_left"]
        right = GOLDEN["cases"]["same_gloss_right"]
        self.assertEqual(left["definition"], right["definition"])
        self.assertNotEqual(left["sense_iri"], right["sense_iri"])
        self.assertNotEqual(left["source_sense_ids"], right["source_sense_ids"])

    def test_invalid_root_evidence_form_is_held_without_root_rdf(self):
        rows = [dict(row.values) for row in self.closure.table("lexicon_root_evidence").rows]
        target = next(row for row in rows if row["lexicon_root_id"] == "LEXROOT-0bd881a56fac9e")
        target["root_form_raw"] = "-WRONG-"
        result = project_lexicon_roots(replace_table(self.closure, "lexicon_root_evidence", rows))
        self.assertIn(target["lexicon_root_id"], result.held_ids)
        root = URIRef(GOLDEN["cases"]["multi_unicode_root"]["root_iri"])
        self.assertFalse(any(result.graph.triples((root, None, None))))

    def test_conflicting_duplicate_sense_coordinate_is_held_without_concept_rdf(self):
        rows = [dict(row.values) for row in self.closure.table("lexicon_root_senses").rows]
        target = next(row for row in rows if row["lexicon_sense_id"] == "LEXSENSE-e3f64d03c6f6ec")
        duplicate = dict(target)
        duplicate["lexicon_sense_id"] = "LEXSENSE-golden-conflict"
        duplicate["sense_summary"] = "contradictory synthetic meaning"
        result = project_lexicon_senses(replace_table(self.closure, "lexicon_root_senses", [*rows, duplicate]))
        self.assertIn(target["lexicon_sense_id"], result.held_source_ids)
        self.assertIn(duplicate["lexicon_sense_id"], result.held_source_ids)
        subject = URIRef(GOLDEN["cases"]["direct_table"]["sense_iri"])
        self.assertFalse(any(result.graph.triples((subject, None, None))))

    def test_reordered_primary_rows_leave_combined_golden_graph_unchanged(self):
        def merged(closure):
            roots = project_lexicon_roots(closure)
            senses = project_lexicon_senses(closure)
            dims = project_lexicon_dimensions(closure, senses)
            links = project_root_sense_links(closure, self.term, roots=roots, senses=senses, dimensions=dims)
            graph = Graph()
            for source in (roots.graph, senses.graph, dims.graph, links.graph):
                for triple in source:
                    graph.add(triple)
            return graph

        closure = replace_table(self.closure, "lexicon_roots", reversed(self.closure.table("lexicon_roots").rows))
        closure = replace_table(closure, "lexicon_root_senses", reversed(closure.table("lexicon_root_senses").rows))
        closure = replace_table(closure, "lexicon_root_evidence", reversed(closure.table("lexicon_root_evidence").rows))
        self.assertEqual(canonicalize(merged(closure)), canonicalize(merged(self.closure)))


if __name__ == "__main__":
    unittest.main()
