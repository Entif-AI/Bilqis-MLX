from __future__ import annotations

from dataclasses import replace
from lib.ithkuil.tests.source_expectations import LEXICON

import os
from pathlib import Path
import unittest

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS


STAGED = os.environ.get("BILQIS_STAGED_SKOS_PATH")
if STAGED:
    import lib.ithkuil.src.skos as _skos
    for path in reversed(STAGED.split(os.pathsep)):
        _skos.__path__.insert(0, path)

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.identity import Identity, sense_from_source
from lib.ithkuil.src.skos.lexicon_senses import project_lexicon_senses
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable


LIB = Path(os.environ.get("BILQIS_ITHKUIL_LIB", Path(__file__).resolve().parents[1]))
DATA = LIB / "_data" / "csv"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def replace_sense_rows(closure: CompilerClosure, rows) -> CompilerClosure:
    tables = []
    for table in closure.tables:
        if table.name == "lexicon_root_senses":
            frozen = tuple(FrozenRow(tuple(row.items())) if isinstance(row, dict) else row for row in rows)
            tables.append(LoadedTable(table.name, table.columns, frozen))
        else:
            tables.append(table)
    return CompilerClosure(closure.manifest_version, tuple(tables))


class LexiconSenseProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.result = project_lexicon_senses(cls.closure)

    def test_current_frontier_has_one_concept_per_stable_coordinate(self):
        self.assertEqual(len(self.closure.table("lexicon_root_senses").rows), LEXICON["sense_rows"])
        self.assertEqual(len(self.result.records), LEXICON["sense_rows"])
        self.assertEqual(len(self.result.emitted_source_ids), LEXICON["sense_rows"])
        self.assertEqual(self.result.held_source_ids, ())
        self.assertEqual(self.result.issues, ())
        self.assertEqual(len({record.identity for record in self.result.records}), LEXICON["sense_rows"])
        for record in self.result.records:
            self.assertIn((URIRef(record.identity.iri), RDF.type, SKOS.Concept), self.result.graph)
            self.assertEqual(record.evidence_statuses, ("official_source_observed",))

    def test_one_root_multiple_senses_remain_independently_addressable(self):
        root = Identity("root", ("NI-LEXICON-CURRICULUM", "LEXROOT-0bd881a56fac9e"))
        senses = [record for record in self.result.records if record.parent_root == root]
        self.assertEqual(len(senses), 12)
        self.assertEqual(len({record.identity.iri for record in senses}), 12)
        self.assertEqual({record.specification for record in senses}, {"BSC", "CTE", "CSV", "OBJ"})

    def test_identical_gloss_on_distinct_roots_does_not_merge(self):
        rows = [dict(row.values) for row in self.closure.table("lexicon_root_senses").rows]
        summary = "(to be) the act/process of choosing from one’s available options/alternatives"
        matching = [row for row in rows if row["sense_summary"] == summary]
        self.assertEqual(len(matching), 2)
        identities = {sense_from_source("lexicon_root_senses", row) for row in matching}
        self.assertEqual(len(identities), 2)
        for identity in identities:
            self.assertIn((URIRef(identity.iri), RDF.type, SKOS.Concept), self.result.graph)

    def test_legacy_gloss_hash_id_change_does_not_change_semantic_iri(self):
        rows = [dict(row.values) for row in self.closure.table("lexicon_root_senses").rows]
        target = next(row for row in rows if row["lexicon_sense_id"] == "LEXSENSE-e3f64d03c6f6ec")
        original = sense_from_source("lexicon_root_senses", target)
        target["lexicon_sense_id"] = "LEXSENSE-synthetic-id-drift"
        changed = project_lexicon_senses(replace_sense_rows(self.closure, rows))
        record = next(record for record in changed.records if "LEXSENSE-synthetic-id-drift" in record.source_sense_ids)
        self.assertEqual(record.identity, original)
        self.assertIn((URIRef(original.iri), RDF.type, SKOS.Concept), changed.graph)

    def test_duplicate_coordinate_equal_content_converges_but_conflict_holds(self):
        base = [dict(row.values) for row in self.closure.table("lexicon_root_senses").rows]
        target = next(row for row in base if row["lexicon_sense_id"] == "LEXSENSE-e3f64d03c6f6ec")
        duplicate = dict(target); duplicate["lexicon_sense_id"] = "LEXSENSE-synthetic-duplicate"
        same = project_lexicon_senses(replace_sense_rows(self.closure, [*base, duplicate]))
        identity = sense_from_source("lexicon_root_senses", target)
        record = next(record for record in same.records if record.identity == identity)
        self.assertEqual(set(record.source_sense_ids), {target["lexicon_sense_id"], duplicate["lexicon_sense_id"]})

        conflicting = dict(duplicate); conflicting["sense_summary"] = "source-conflicting meaning"
        held = project_lexicon_senses(replace_sense_rows(self.closure, [*base, conflicting]))
        self.assertIn(target["lexicon_sense_id"], held.held_source_ids)
        self.assertIn(conflicting["lexicon_sense_id"], held.held_source_ids)
        self.assertTrue(any(issue.code == "CONFLICTING_SEMANTIC_MEANING" for issue in held.issues))
        self.assertFalse(any(held.graph.triples((URIRef(identity.iri), None, None))))

    def test_reordering_is_canonically_invariant(self):
        other = project_lexicon_senses(
            replace_sense_rows(self.closure, reversed(self.closure.table("lexicon_root_senses").rows))
        )
        self.assertEqual(canonicalize(other.graph), canonicalize(self.result.graph))
        self.assertEqual(other.records, self.result.records)

    def test_case_folded_source_coordinates_keep_one_sense_and_both_raw_spellings(self):
        rows = [dict(row.values) for row in self.closure.table("lexicon_root_senses").rows]
        target = next(row for row in rows if row["lexicon_sense_id"] == "LEXSENSE-e3f64d03c6f6ec")
        duplicate = dict(target)
        duplicate["lexicon_sense_id"] = "LEXSENSE-case-fold-alias"
        duplicate["stem"] = target["stem"].lower()
        duplicate["specification"] = target["specification"].lower()
        result = project_lexicon_senses(replace_sense_rows(self.closure, [*rows, duplicate]))
        identity = sense_from_source("lexicon_root_senses", target)
        record = next(record for record in result.records if record.identity == identity)
        self.assertEqual(record.raw_stems, tuple(sorted({target["stem"], duplicate["stem"]})))
        self.assertEqual(record.source_sense_ids, tuple(sorted((target["lexicon_sense_id"], duplicate["lexicon_sense_id"]))))
        self.assertIn((URIRef(identity.iri), RDF.type, SKOS.Concept), result.graph)
        self.assertNotIn(target["lexicon_sense_id"], result.held_source_ids)

    def test_literal_sense_fixture_is_exact(self):
        expected = Graph().parse(FIXTURES / "skos_lexicon_sense_expected.nt", format="nt")
        identity = Identity("sense", (
            "NI-LEXICON-CURRICULUM", "LEXROOT-01e02023f505ec", "STEM 1", "BSC"
        ))
        subject = URIRef(identity.iri)
        actual = Graph()
        for triple in self.result.graph.triples((subject, None, None)):
            actual.add(triple)
        for locus in actual.objects(subject, DCTERMS.source):
            for triple in self.result.graph.triples((locus, None, None)):
                actual.add(triple)
            for source in self.result.graph.objects(locus, DCTERMS.source):
                for triple in self.result.graph.triples((source, None, None)):
                    actual.add(triple)
        self.assertEqual(canonicalize(actual), canonicalize(expected))


if __name__ == "__main__":
    unittest.main()
