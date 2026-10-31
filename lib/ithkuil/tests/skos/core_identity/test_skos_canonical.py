from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF, SKOS, XSD

from lib.ithkuil.src.skos.canonical import canonical_diff, canonicalize
from lib.ithkuil.src.skos.errors import ProfileError


ROOT = REPO_ROOT


def graph_with_list(prefix="first"):
    graph = Graph()
    head, tail = BNode(prefix + "-head"), BNode(prefix + "-tail")
    triples = [
        (URIRef("urn:collection"), SKOS.memberList, head),
        (head, RDF.first, URIRef("urn:concept:A")),
        (head, RDF.rest, tail),
        (tail, RDF.first, URIRef("urn:concept:B")),
        (tail, RDF.rest, RDF.nil),
        (URIRef("urn:concept:A"), SKOS.notation, Literal("C\u030c / ∅", datatype=URIRef("urn:notation"), normalize=False)),
    ]
    for triple in triples if prefix == "first" else reversed(triples):
        graph.add(triple)
    return graph


class CanonicalGraphTests(unittest.TestCase):
    def code(self, expected, function, *args):
        with self.assertRaises(ProfileError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, expected)

    def test_literal_single_triple_bytes_and_digest(self):
        graph = Graph().add((URIRef("urn:s"), URIRef("urn:p"), Literal("∅", datatype=URIRef("urn:d"), normalize=False)))
        expected = '<urn:s> <urn:p> "∅"^^<urn:d> .\n'.encode("utf-8")
        result = canonicalize(graph)
        self.assertEqual(result.payload, expected)
        self.assertEqual(result.sha256, hashlib.sha256(expected).hexdigest())
        self.assertEqual(result.triple_count, 1)
        self.assertEqual(result.metadata()["byte_count"], len(expected))

    def test_repeated_shuffled_and_renamed_blank_nodes_have_equal_bytes(self):
        first, second = graph_with_list(), graph_with_list("random-other-node-ids")
        self.assertTrue(isomorphic(first, second))
        expected = canonicalize(first)
        self.assertEqual(canonicalize(first), expected)
        self.assertEqual(canonicalize(second), expected)
        self.assertNotIn(b"first-head", expected.payload)
        self.assertEqual(expected.triple_count, 6)

    def test_nfc_and_nfd_are_distinct_and_survive_exact_roundtrip(self):
        for lexical in ("Č", "C\u030c", "a\n\r\"\\b\u0085c\u2028d"):
            graph = Graph().add((URIRef("urn:s"), SKOS.notation,
                                 Literal(lexical, datatype=URIRef("urn:d"), normalize=False)))
            result = canonicalize(graph)
            recovered = Graph().parse(data=result.payload, format="nt")
            self.assertEqual(str(next(recovered.objects())), lexical)
            self.assertEqual(canonicalize(recovered), result)
        left = Graph().add((URIRef("urn:s"), SKOS.notation, Literal("Č", datatype=URIRef("urn:d"), normalize=False)))
        right = Graph().add((URIRef("urn:s"), SKOS.notation, Literal("C\u030c", datatype=URIRef("urn:d"), normalize=False)))
        self.assertNotEqual(canonicalize(left).sha256, canonicalize(right).sha256)

    def test_known_datatype_lexical_value_is_not_canonicalized_away(self):
        graph = Graph().add((URIRef("urn:s"), URIRef("urn:p"), Literal("01", datatype=XSD.integer, normalize=False)))
        self.assertEqual(canonicalize(graph).payload,
                         b'<urn:s> <urn:p> "01"^^<http://www.w3.org/2001/XMLSchema#integer> .\n')

    def test_digest_covers_added_source_triple_and_ordered_list_change(self):
        graph = graph_with_list()
        baseline = canonicalize(graph)
        graph.add((URIRef("urn:concept:A"), URIRef("http://purl.org/dc/terms/source"), URIRef("https://ithkuil.net/03_morphology.html")))
        self.assertNotEqual(canonicalize(graph).sha256, baseline.sha256)
        self.assertEqual(canonicalize(graph).triple_count, 7)
        changed = graph_with_list()
        cell = next(changed.subjects(RDF.first, URIRef("urn:concept:A")))
        changed.set((cell, RDF.first, URIRef("urn:concept:C")))
        self.assertNotEqual(canonicalize(changed).sha256, baseline.sha256)

    def test_graph_identifier_prefix_and_insertion_order_do_not_enter_digest(self):
        original = graph_with_list()
        copied = Graph(identifier=URIRef("urn:process:random"))
        copied.bind("volatile", "https://unrelated.example/")
        for triple in reversed(list(original)):
            copied.add(triple)
        self.assertEqual(canonicalize(copied), canonicalize(original))

    def test_empty_graph_has_empty_byte_digest(self):
        result = canonicalize(Graph())
        self.assertEqual(result.payload, b"")
        self.assertEqual(result.sha256, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(result.triple_count, 0)

    def test_diff_reports_exact_changed_assertions(self):
        first = Graph().add((URIRef("urn:s"), URIRef("urn:p"), Literal("old")))
        second = Graph().add((URIRef("urn:s"), URIRef("urn:p"), Literal("new")))
        diff = canonical_diff(first, second)
        self.assertFalse(diff["equal"])
        self.assertEqual(diff["removed"], ['<urn:s> <urn:p> "old" .'])
        self.assertEqual(diff["added"], ['<urn:s> <urn:p> "new" .'])
        self.assertFalse(diff["truncated"])
        self.assertTrue(canonical_diff(first, second, limit=0)["truncated"])

    def test_datasets_relative_iris_and_bad_unicode_fail_without_partial_digest(self):
        dataset = Dataset()
        dataset.graph(URIRef("urn:g")).add((URIRef("urn:s"), URIRef("urn:p"), Literal("named graph")))
        self.code("CANONICALIZATION_REQUIRES_SINGLE_GRAPH", canonicalize, dataset)
        self.code("NON_ABSOLUTE_OR_INVALID_RDF_IRI", canonicalize,
                  Graph().add((URIRef("relative"), URIRef("urn:p"), Literal("value"))))
        self.code("INVALID_RDF_LITERAL_UNICODE", canonicalize,
                  Graph().add((URIRef("urn:s"), URIRef("urn:p"), Literal("\ud800", normalize=False))))

    def test_invalid_percent_escapes_and_iri_controls_fail_without_rewriting_valid_iri(self):
        for iri in (
            "http://example.org/%ZZ",
            "http://example.org/%",
            "urn:bad%GG",
            "urn:bad\x7f",
            "urn:bad\x85",
        ):
            with self.subTest(iri=repr(iri)):
                self.code("NON_ABSOLUTE_OR_INVALID_RDF_IRI", canonicalize,
                          Graph().add((URIRef(iri), URIRef("urn:p"), Literal("value"))))

        self.code(
            "NON_ABSOLUTE_OR_INVALID_RDF_IRI",
            canonicalize,
            Graph().add((URIRef("urn:s"), URIRef("urn:p"),
                         Literal("value", datatype=URIRef("urn:datatype%GG"), normalize=False))),
        )

        iri = "https://example.org/%2f/Č"
        result = canonicalize(Graph().add((URIRef(iri), URIRef("urn:p"), Literal("value"))))
        self.assertEqual(result.payload, f'<{iri}> <urn:p> "value" .\n'.encode("utf-8"))

    def test_canonicalizer_version_is_bound(self):
        with patch("lib.ithkuil.src.skos.canonical.rdflib.__version__", "future-unverified"):
            self.code("CANONICALIZER_VERSION_MISMATCH", canonicalize, Graph())

    def test_fresh_processes_workdirs_and_hash_seeds_produce_identical_bytes(self):
        script = '''from rdflib import Graph
from lib.ithkuil.src.skos.canonical import canonicalize
import sys
g = Graph().parse(data=sys.stdin.buffer.read(), format="nt")
sys.stdout.buffer.write(canonicalize(g).payload)
'''
        source = graph_with_list().serialize(format="nt", encoding="utf-8")
        results = []
        for seed in ("7", "91"):
            with tempfile.TemporaryDirectory() as directory:
                environment = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONHASHSEED": seed}
                result = subprocess.run([sys.executable, "-B", "-c", script], input=source,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=directory, env=environment, check=True)
                results.append(result.stdout)
        self.assertEqual(results, [canonicalize(graph_with_list()).payload] * 2)


if __name__ == "__main__":
    unittest.main()
