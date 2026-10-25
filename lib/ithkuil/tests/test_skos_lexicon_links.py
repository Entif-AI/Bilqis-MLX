from __future__ import annotations

from dataclasses import replace
from lib.ithkuil.tests.source_expectations import LEXICON

import os
from pathlib import Path
import unittest

from rdflib import Graph, URIRef
from rdflib.namespace import SKOS


STAGED = os.environ.get("BILQIS_STAGED_SKOS_PATH")
if STAGED:
    import lib.ithkuil.src.skos as _skos
    for path in reversed(STAGED.split(os.pathsep)):
        _skos.__path__.insert(0, path)

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.lexicon_links import load_root_sense_term, project_root_sense_links
from lib.ithkuil.src.skos.lexicon_roots import project_lexicon_roots
from lib.ithkuil.src.skos.preflight import preflight
from lib.ithkuil.src.skos.relations import RelationDisposition, decide_relation


LIB = Path(os.environ.get("BILQIS_ITHKUIL_LIB", Path(__file__).resolve().parents[1]))
DATA = LIB / "_data" / "csv"
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TERM = ROOT / "src" / "skos" / "root_sense_extension.json"


class RootSenseLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.term = load_root_sense_term(
            TERM,
            source_csv_root=DATA,
            negative_fixture_path=FIXTURES / "skos_root_sense_negative.ttl",
        )
        cls.result = project_root_sense_links(cls.closure, cls.term)

    def test_existing_skos_matrix_remains_relational_ir_until_term_is_requalified(self):
        baseline = decide_relation("root_sense", source_attested=True, semantic_proof=True)
        self.assertEqual(
            (baseline.disposition, baseline.predicate, baseline.reason),
            (RelationDisposition.RELATIONAL_IR_ONLY, None, "LINGUISTIC_EXTENSION_NOT_ADMITTED"),
        )
        self.assertEqual(self.term.key, "hasSense")
        self.assertIsNone(self.term.subproperty_of)

    def test_current_frontier_emits_one_non_skos_link_per_sense(self):
        self.assertEqual(len(self.result.graph), LEXICON["sense_rows"])
        self.assertEqual(len(self.result.linked_sense_ids), LEXICON["sense_rows"])
        self.assertEqual(self.result.held_sense_ids, ())
        self.assertEqual(self.result.issues, ())
        self.assertEqual(
            {str(predicate) for _, predicate, _ in self.result.graph},
            {self.term.iri},
        )
        self.assertFalse(any(predicate in {SKOS.broader, SKOS.narrower, SKOS.related, SKOS.member}
                             for _, predicate, _ in self.result.graph))

    def test_multi_sense_root_literal_fixture_has_all_twelve_links(self):
        expected = Graph().parse(FIXTURES / "skos_root_sense_expected.nt", format="nt")
        root = URIRef(Identity("root", ("NI-LEXICON-CURRICULUM", "LEXROOT-0bd881a56fac9e")).iri)
        actual = Graph()
        for triple in self.result.graph.triples((root, None, None)):
            actual.add(triple)
        self.assertEqual(len(actual), 12)
        self.assertEqual(canonicalize(actual), canonicalize(expected))

    def test_negative_fixture_demonstrates_false_taxonomy(self):
        graph = Graph().parse(FIXTURES / "skos_root_sense_negative.ttl", format="turtle")
        root = URIRef(Identity("root", ("NI-LEXICON-CURRICULUM", "LEXROOT-01e02023f505ec")).iri)
        self.assertTrue(list(graph.triples((root, SKOS.broader, None))))
        self.assertFalse(list(self.result.graph.triples((root, SKOS.broader, None))))

    def test_missing_parent_root_holds_all_its_links_without_partial_edges(self):
        roots = project_lexicon_roots(self.closure)
        missing = "LEXROOT-0bd881a56fac9e"
        reduced = replace(
            roots,
            records=tuple(record for record in roots.records if record.source_root_id != missing),
            emitted_ids=tuple(value for value in roots.emitted_ids if value != missing),
        )
        result = project_root_sense_links(self.closure, self.term, roots=reduced)
        root = URIRef(Identity("root", ("NI-LEXICON-CURRICULUM", missing)).iri)
        self.assertFalse(any(result.graph.triples((root, None, None))))
        self.assertEqual(sum(issue.code == "ROOT_SENSE_PARENT_NOT_EMITTED" for issue in result.issues), 12)
        self.assertEqual(len(result.held_sense_ids), 12)

    def test_row_order_does_not_change_link_graph(self):
        # Resolver/projectors already prove row-order invariance; repeat #53 from the same
        # immutable closure to lock deterministic set semantics at the relation boundary.
        other = project_root_sense_links(self.closure, self.term)
        self.assertEqual(canonicalize(other.graph), canonicalize(self.result.graph))
        self.assertEqual(other.linked_sense_ids, self.result.linked_sense_ids)


if __name__ == "__main__":
    unittest.main()
