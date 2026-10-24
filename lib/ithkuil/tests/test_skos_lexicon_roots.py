from __future__ import annotations

import os
from pathlib import Path
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SKOS


STAGED = os.environ.get("BILQIS_STAGED_SKOS_PATH")
if STAGED:
    import lib.ithkuil.src.skos as _skos
    _skos.__path__.insert(0, STAGED)

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.lexicon_roots import project_lexicon_roots
from lib.ithkuil.src.skos.notation import NEW_ITHKUIL_DATATYPE_IRI
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable


LIB = Path(os.environ.get("BILQIS_ITHKUIL_LIB", Path(__file__).resolve().parents[1]))
DATA = LIB / "_data" / "csv"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def replace_table(closure: CompilerClosure, name: str, rows) -> CompilerClosure:
    tables = []
    for table in closure.tables:
        if table.name == name:
            frozen = tuple(FrozenRow(tuple(row.items())) if isinstance(row, dict) else row for row in rows)
            tables.append(LoadedTable(table.name, table.columns, frozen))
        else:
            tables.append(table)
    return CompilerClosure(closure.manifest_version, tuple(tables))


class LexiconRootProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.result = project_lexicon_roots(cls.closure)

    def test_current_frontier_projects_one_root_resource_per_source_root(self):
        self.assertEqual(len(self.closure.table("lexicon_roots").rows), 503)
        self.assertEqual(len(self.result.records), 503)
        self.assertEqual(len(self.result.emitted_ids), 503)
        self.assertEqual(self.result.held_ids, ())
        self.assertEqual(self.result.issues, ())
        roots = {record.identity.iri for record in self.result.records}
        self.assertEqual(len(roots), 503)
        for iri in roots:
            subject = URIRef(iri)
            self.assertIn((subject, RDF.type, RDFS.Resource), self.result.graph)
            self.assertNotIn((subject, RDF.type, SKOS.Concept), self.result.graph)

    def test_unicode_root_uses_exact_typed_notation_and_public_source_locus(self):
        identity = Identity("root", ("NI-LEXICON-CURRICULUM", "LEXROOT-0bd881a56fac9e"))
        subject = URIRef(identity.iri)
        notation = Literal("-Č-", datatype=URIRef(NEW_ITHKUIL_DATATYPE_IRI), normalize=False)
        self.assertIn((subject, SKOS.notation, notation), self.result.graph)
        self.assertNotIn((subject, SKOS.notation, Literal("č", datatype=notation.datatype)), self.result.graph)
        loci = tuple(self.result.graph.objects(subject, DCTERMS.source))
        self.assertEqual(len(loci), 1)
        self.assertIn(
            (loci[0], DCTERMS.source, URIRef("https://ithkuil.net/New_Ithkuil_Lexicon.pdf")),
            self.result.graph,
        )

    def test_repeated_supporting_evidence_does_not_duplicate_root_identity(self):
        record = next(item for item in self.result.records if item.source_root_id == "LEXROOT-0bd881a56fac9e")
        self.assertEqual(len(record.evidence_ids), 8)
        subject = URIRef(record.identity.iri)
        self.assertEqual(len(list(self.result.graph.triples((subject, RDF.type, RDFS.Resource)))), 1)

    def test_conflicting_evidence_form_holds_the_whole_root(self):
        rows = [dict(row.values) for row in self.closure.table("lexicon_root_evidence").rows]
        target = next(row for row in rows if row["lexicon_root_id"] == "LEXROOT-0bd881a56fac9e")
        target["root_form_raw"] = "-NOT-Č-"
        result = project_lexicon_roots(replace_table(self.closure, "lexicon_root_evidence", rows))
        self.assertIn("LEXROOT-0bd881a56fac9e", result.held_ids)
        self.assertTrue(any(issue.code == "LEXICON_ROOT_FORM_CONFLICT" for issue in result.issues))
        subject = URIRef(Identity("root", ("NI-LEXICON-CURRICULUM", "LEXROOT-0bd881a56fac9e")).iri)
        self.assertFalse(any(result.graph.triples((subject, None, None))))

    def test_row_order_does_not_change_canonical_root_graph(self):
        closure = replace_table(self.closure, "lexicon_roots", reversed(self.closure.table("lexicon_roots").rows))
        closure = replace_table(closure, "lexicon_root_evidence", reversed(closure.table("lexicon_root_evidence").rows))
        other = project_lexicon_roots(closure)
        self.assertEqual(canonicalize(other.graph), canonicalize(self.result.graph))
        self.assertEqual(other.records, self.result.records)

    def test_literal_fixture_for_unicode_root_is_exact(self):
        expected = Graph().parse(FIXTURES / "skos_lexicon_root_expected.nt", format="nt")
        subject = URIRef(Identity("root", ("NI-LEXICON-CURRICULUM", "LEXROOT-0bd881a56fac9e")).iri)
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
