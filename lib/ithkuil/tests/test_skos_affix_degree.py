from __future__ import annotations

import csv
import os
from pathlib import Path
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

import lib.ithkuil.src.skos as _skos
BASE_SKOS = Path(next(iter(_skos.__path__))).resolve()
_skos.__path__.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "skos"))

from lib.ithkuil.src.skos.affix_degree import (
    DEGREE_OF, affix_degree_iri, degrees_for_root, project_affix_degrees,
)
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.preflight import preflight


LIB = BASE_SKOS.parents[1]
DATA = LIB / "_data" / "csv"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def rows():
    with (DATA / "affix_degrees.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class AffixDegreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.rows = rows()
        cls.result = project_affix_degrees(cls.closure, cls.rows)

    def test_full_current_row_reconciliation(self):
        self.assertEqual(len(self.rows), 271)
        self.assertEqual(len(self.result.records), 271)
        self.assertEqual(len(self.result.emitted_source_ids), 271)
        self.assertEqual(self.result.held_source_ids, ())
        self.assertEqual(self.result.issues, ())
        self.assertEqual(len({record.iri for record in self.result.records}), 271)

    def test_meaning_hash_source_id_does_not_control_semantic_iri(self):
        target = next(row for row in self.rows if row["degree_id"] == "DEG-f700e59e3201ca")
        expected = affix_degree_iri(target["affix_root_atomic_id"], target["degree"])
        changed = [dict(row) for row in self.rows]
        mutated = next(row for row in changed if row["degree_id"] == target["degree_id"])
        mutated["degree_id"] = "DEG-synthetic-summary-hash-drift"
        result = project_affix_degrees(self.closure, changed)
        record = next(record for record in result.records
                      if "DEG-synthetic-summary-hash-drift" in record.source_degree_ids)
        self.assertEqual(record.iri, expected)

    def test_one_root_returns_degree_zero_through_nine_without_rdf_order(self):
        root_id = "ATOM-c413d0e6c8faa8"
        selected = degrees_for_root(self.result.records, root_id)
        self.assertEqual([record.degree for record in selected], list(range(10)))
        for record in selected:
            subject = URIRef(record.iri)
            self.assertIn((subject, RDF.value,
                           Literal(record.degree, datatype=XSD.nonNegativeInteger)), self.result.graph)
            self.assertIn((subject, DEGREE_OF, URIRef(record.affix_root_identity.iri)), self.result.graph)
        self.assertFalse(any(predicate in {SKOS.broader, SKOS.narrower, SKOS.related}
                             for _, predicate, _ in self.result.graph))

    def test_conflicting_duplicate_coordinate_is_held_not_guessed(self):
        changed = [dict(row) for row in self.rows]
        target = next(row for row in changed if row["degree_id"] == "DEG-f700e59e3201ca")
        duplicate = dict(target)
        duplicate["degree_id"] = "DEG-synthetic-conflict"
        duplicate["meaning_summary"] = "contradictory synthetic meaning"
        result = project_affix_degrees(self.closure, [*changed, duplicate])
        self.assertIn(target["degree_id"], result.held_source_ids)
        self.assertIn(duplicate["degree_id"], result.held_source_ids)
        self.assertTrue(any(issue.code == "AFFIX_DEGREE_MEANING_CONFLICT" for issue in result.issues))
        self.assertFalse(any(result.graph.triples((URIRef(affix_degree_iri(target["affix_root_atomic_id"], target["degree"])), None, None))))

    def test_unknown_affix_root_and_blank_meaning_are_held(self):
        for field, value, code in (
            ("affix_root_atomic_id", "ATOM-not-real", "AFFIX_DEGREE_ROOT_NOT_RESOLVED"),
            ("meaning_summary", "", "AFFIX_DEGREE_MEANING_CONFLICT"),
        ):
            with self.subTest(field=field):
                changed = [dict(row) for row in self.rows]
                target = changed[0]; target[field] = value
                result = project_affix_degrees(self.closure, changed)
                self.assertIn(target["degree_id"], result.held_source_ids)
                self.assertTrue(any(issue.code == code for issue in result.issues))

    def test_reordered_rows_canonicalize_identically(self):
        other = project_affix_degrees(self.closure, reversed(self.rows))
        self.assertEqual(canonicalize(other.graph), canonicalize(self.result.graph))
        self.assertEqual(other.records, self.result.records)

    def test_resolved_non_affix_resource_cannot_be_used_as_an_affix_root(self):
        changed = [dict(row) for row in self.rows]
        target = changed[0]
        target["affix_root_atomic_id"] = "ATOM-0055eaace0b70d"
        result = project_affix_degrees(self.closure, changed)
        self.assertIn(target["degree_id"], result.held_source_ids)
        self.assertTrue(any(issue.code == "AFFIX_DEGREE_ROOT_KIND_INVALID"
                            for issue in result.issues))
        subject = URIRef(affix_degree_iri(target["affix_root_atomic_id"], target["degree"]))
        self.assertFalse(any(result.graph.triples((subject, None, None))))

    def test_source_id_cannot_repeat_across_different_semantic_coordinates(self):
        changed = [dict(row) for row in self.rows]
        changed[1]["degree_id"] = changed[0]["degree_id"]
        with self.assertRaises(ProfileError) as caught:
            project_affix_degrees(self.closure, changed)
        self.assertEqual(caught.exception.code, "DUPLICATE_AFFIX_DEGREE_SOURCE_ID")
        self.assertEqual(caught.exception.details, (changed[0]["degree_id"],))
        changed[0]["degree_id"] = ""
        with self.assertRaises(ProfileError) as caught:
            project_affix_degrees(self.closure, changed)
        self.assertEqual(caught.exception.code, "AFFIX_DEGREE_SOURCE_ID_REQUIRED")

    def test_literal_multi_degree_fixture_is_exact(self):
        expected = Graph().parse(FIXTURES / "skos_affix_degree_expected.nt", format="nt")
        actual = Graph()
        for degree in (0, 1, 9):
            subject = URIRef(affix_degree_iri("ATOM-c413d0e6c8faa8", degree))
            for triple in self.result.graph.triples((subject, None, None)):
                actual.add(triple)
            for locus in list(actual.objects(subject, DCTERMS.source)):
                for triple in self.result.graph.triples((locus, None, None)):
                    actual.add(triple)
                for source in self.result.graph.objects(locus, DCTERMS.source):
                    for triple in self.result.graph.triples((source, None, None)):
                        actual.add(triple)
        self.assertEqual(canonicalize(actual), canonicalize(expected))


if __name__ == "__main__":
    unittest.main()
