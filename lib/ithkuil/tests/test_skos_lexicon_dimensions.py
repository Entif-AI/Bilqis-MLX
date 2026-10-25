from __future__ import annotations

from pathlib import Path
import unittest

from rdflib import Graph, Literal, URIRef


import lib.ithkuil.src.skos as _skos
BASE_SKOS = Path(next(iter(_skos.__path__))).resolve()
STAGED = Path(__file__).resolve().parents[1] / "src" / "skos"
VERIFY = Path(__file__).resolve().parents[3] / "_verify" / "lib" / "ithkuil" / "src" / "skos"
_skos.__path__.insert(0, str(STAGED))
if VERIFY.exists():
    _skos.__path__.insert(1, str(VERIFY))

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.lexicon_dimensions import (
    SPECIFICATION, STEM, project_lexicon_dimensions, query_senses,
)
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable


LIB = BASE_SKOS.parents[1]
DATA = LIB / "_data" / "csv"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def replace_rows(closure: CompilerClosure, rows) -> CompilerClosure:
    tables = []
    for table in closure.tables:
        if table.name == "lexicon_root_senses":
            frozen = tuple(FrozenRow(tuple(row.items())) if isinstance(row, dict) else row for row in rows)
            tables.append(LoadedTable(table.name, table.columns, frozen))
        else:
            tables.append(table)
    return CompilerClosure(closure.manifest_version, tuple(tables))


class LexiconDimensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.result = project_lexicon_dimensions(cls.closure)

    def test_every_current_sense_has_exact_dimensions(self):
        self.assertEqual(len(self.result.records), 1615)
        self.assertEqual(self.result.held_source_ids, ())
        self.assertEqual(self.result.issues, ())
        self.assertEqual(len(self.result.graph), 3230)
        self.assertEqual(len(list(self.result.graph.triples((None, STEM, None)))), 1615)
        self.assertEqual(len(list(self.result.graph.triples((None, SPECIFICATION, None)))), 1615)

    def test_direct_prose_and_compact_source_modes_remain_record_metadata_only(self):
        cases = {
            ("LEXROOT-01e02023f505ec", "STEM 1", "BSC"): "table",
            ("LEXROOT-a5299227d87d97", "STEM 1", "BSC"): "prose",
            ("LEXROOT-4c7bdc159bffbf", "STEM 1", "BSC"): "compact_numbered_stem",
        }
        for (root_id, stem, spec), expected_mode in cases.items():
            with self.subTest(root=root_id):
                identity = Identity("sense", ("NI-LEXICON-CURRICULUM", root_id, stem, spec))
                subject = URIRef(identity.iri)
                record = next(item for item in self.result.records if item.sense == identity)
                self.assertIn((subject, STEM, Literal(stem)), self.result.graph)
                self.assertIn((subject, SPECIFICATION, Literal(spec)), self.result.graph)
                self.assertEqual(record.source_locus_kinds, (expected_mode,))
                self.assertFalse(any(str(predicate).endswith("/sourceLocusKind")
                                     for _, predicate, _ in self.result.graph))

    def test_root_wide_and_stems_one_through_three_are_not_ordered(self):
        root = Identity("root", ("NI-LEXICON-CURRICULUM", "LEXROOT-01e02023f505ec"))
        bsc = {
            query_senses(self.result.records, parent_root=root, stem=stem, specification="BSC")[0]
            for stem in ("STEM 1", "STEM 2", "STEM 3")
        }
        self.assertEqual(len(bsc), 3)
        csv = query_senses(self.result.records, parent_root=root, stem="ROOT-WIDE", specification="CSV")
        self.assertEqual(len(csv), 1)
        predicates = {str(predicate) for _, predicate, _ in self.result.graph}
        self.assertFalse(any(name.endswith(("broader", "narrower", "memberList")) for name in predicates))

    def test_combined_stems_source_coordinate_survives_exactly(self):
        identity = Identity("sense", (
            "NI-LEXICON-CURRICULUM", "LEXROOT-38f830ad38e6e4", "STEMS 1-3", "BSC"
        ))
        subject = URIRef(identity.iri)
        record = next(item for item in self.result.records if item.sense == identity)
        self.assertIn((subject, STEM, Literal("STEMS 1-3")), self.result.graph)
        self.assertEqual(record.source_locus_kinds, ("prose",))

    def test_unknown_source_mode_holds_dimension_projection(self):
        rows = [dict(row.values) for row in self.closure.table("lexicon_root_senses").rows]
        target = next(row for row in rows if row["lexicon_sense_id"] == "LEXSENSE-e3f64d03c6f6ec")
        target["source_locus_kind"] = "future-unreviewed-mode"
        result = project_lexicon_dimensions(replace_rows(self.closure, rows))
        self.assertIn(target["lexicon_sense_id"], result.held_source_ids)
        self.assertTrue(any(issue.code == "UNKNOWN_LEXICON_SOURCE_LOCUS_KIND" for issue in result.issues))
        identity = Identity("sense", ("NI-LEXICON-CURRICULUM", target["lexicon_root_id"], "STEM 1", "BSC"))
        self.assertFalse(any(result.graph.triples((URIRef(identity.iri), None, None))))

    def test_impossible_stem_is_held_upstream_not_reinterpreted(self):
        rows = [dict(row.values) for row in self.closure.table("lexicon_root_senses").rows]
        target = next(row for row in rows if row["lexicon_sense_id"] == "LEXSENSE-e3f64d03c6f6ec")
        target["stem"] = "STEM 4"
        result = project_lexicon_dimensions(replace_rows(self.closure, rows))
        self.assertIn(target["lexicon_sense_id"], result.held_source_ids)

    def test_row_reorder_is_canonically_invariant(self):
        other = project_lexicon_dimensions(
            replace_rows(self.closure, reversed(self.closure.table("lexicon_root_senses").rows))
        )
        self.assertEqual(canonicalize(other.graph), canonicalize(self.result.graph))
        self.assertEqual(other.records, self.result.records)

    def test_literal_dimension_fixture_is_exact(self):
        expected = Graph().parse(FIXTURES / "skos_lexicon_dimensions_expected.nt", format="nt")
        actual = Graph()
        for root_id, stem, spec in (
            ("LEXROOT-01e02023f505ec", "STEM 1", "BSC"),
            ("LEXROOT-a5299227d87d97", "STEM 1", "BSC"),
            ("LEXROOT-4c7bdc159bffbf", "STEM 1", "BSC"),
        ):
            subject = URIRef(Identity("sense", ("NI-LEXICON-CURRICULUM", root_id, stem, spec)).iri)
            for triple in self.result.graph.triples((subject, None, None)):
                actual.add(triple)
        self.assertEqual(canonicalize(actual), canonicalize(expected))


if __name__ == "__main__":
    unittest.main()
